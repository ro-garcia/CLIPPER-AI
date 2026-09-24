from copy import deepcopy
from threading import RLock
from uuid import uuid4
from sqlalchemy import select
from ..database import Session, serialize
from .cache import RulesCache
from .models import DetectionRule, RuleGroup, DetectionProfile, DetectionState, now
from .schemas import RuleInput, GroupInput, ProfileInput, RulesBundle

class RulesError(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status

class RulesRepository:
    models = {'rules': DetectionRule, 'groups': RuleGroup, 'profiles': DetectionProfile}

    def __init__(self):
        self.cache = RulesCache()
        self.lock = RLock()
        self._configuration: dict = {}

    def load(self):
        with self.lock, Session.begin() as db:
            if db.get(DetectionState, 1) is None:
                db.add(DetectionState(id=1, active_profile_id=None))
        with self.lock:
            self._reload()

    def _reload(self):
        with Session() as db:
            data = {key: [serialize(row) for row in db.scalars(select(model).order_by(model.created_at, model.id))]
                    for key, model in self.models.items()}
            data['active_profile_id'] = db.get(DetectionState, 1).active_profile_id
        self.cache.publish(data['rules'], data['groups'], data['profiles'], data['active_profile_id'])
        data['revision'] = self.cache.snapshot.revision
        data['active_rule_ids'] = [rule.id for rule in self.cache.snapshot.rules]
        self._configuration = data

    def configuration(self) -> dict:
        with self.lock:
            return deepcopy(self._configuration)

    def _write(self, operation):
        with self.lock:
            with Session.begin() as db:
                result = operation(db)
            self._reload()
            return result

    @staticmethod
    def require(db, model, identifier):
        row = db.get(model, identifier)
        if row is None:
            raise RulesError('No se encontró el elemento solicitado.', 404)
        return row

    def save(self, kind: str, payload: RuleInput | GroupInput | ProfileInput, identifier: str | None = None):
        def operation(db):
            values = payload.model_dump()
            if kind == 'rules' and values['group_id'] is not None:
                self.require(db, RuleGroup, values['group_id'])
            if kind == 'profiles':
                for group_id in values['group_ids']:
                    self.require(db, RuleGroup, group_id)
                for rule_id in values['rule_ids']:
                    self.require(db, DetectionRule, rule_id)
            if identifier:
                row = self.require(db, self.models[kind], identifier)
                for key, value in values.items():
                    setattr(row, key, value)
                row.updated_at = now()
            else:
                row = self.models[kind](id=uuid4().hex, **values)
                db.add(row)
            db.flush()
            return serialize(row)
        return self._write(operation)

    def set_enabled(self, kind: str, identifier: str, enabled: bool):
        def operation(db):
            row = self.require(db, self.models[kind], identifier)
            row.enabled, row.updated_at = enabled, now()
            db.flush()
            return serialize(row)
        return self._write(operation)

    def delete(self, kind: str, identifier: str):
        def operation(db):
            row = self.require(db, self.models[kind], identifier)
            if kind == 'groups':
                for rule in db.scalars(select(DetectionRule).where(DetectionRule.group_id == identifier)):
                    rule.group_id, rule.enabled, rule.updated_at = None, False, now()
            if kind in ('groups', 'rules'):
                field = 'group_ids' if kind == 'groups' else 'rule_ids'
                for profile in db.scalars(select(DetectionProfile)):
                    ids = getattr(profile, field)
                    if identifier in ids:
                        setattr(profile, field, [value for value in ids if value != identifier])
                        profile.updated_at = now()
            if kind == 'profiles':
                state = db.get(DetectionState, 1)
                if state.active_profile_id == identifier:
                    # Do not unexpectedly activate all rules by deleting the selected profile.
                    raise RulesError('Selecciona otro perfil o Todas las reglas antes de eliminar este perfil.', 409)
            db.delete(row)
            return {'deleted': identifier}
        return self._write(operation)

    def activate(self, identifier: str | None):
        def operation(db):
            if identifier is not None:
                self.require(db, DetectionProfile, identifier)
            db.get(DetectionState, 1).active_profile_id = identifier
            return {'active_profile_id': identifier}
        return self._write(operation)

    def export(self) -> dict:
        data = self.configuration()
        schemas = {'rules': RuleInput, 'groups': GroupInput, 'profiles': ProfileInput}
        return {'schema_version': 1, 'active_profile_id': data['active_profile_id'],
                **{kind: [{key: value for key, value in row.items() if key == 'id' or key in schema.model_fields}
                          for row in data[kind]] for kind, schema in schemas.items()}}

    def import_bundle(self, bundle: RulesBundle):
        def operation(db):
            group_map = {group.id: uuid4().hex for group in bundle.groups}
            rule_map = {rule.id: uuid4().hex for rule in bundle.rules}
            for group in bundle.groups:
                db.add(RuleGroup(id=group_map[group.id], **group.model_dump(exclude={'id'})))
            for rule in bundle.rules:
                values = rule.model_dump(exclude={'id', 'group_id'})
                db.add(DetectionRule(id=rule_map[rule.id], group_id=group_map.get(rule.group_id), **values))
            for profile in bundle.profiles:
                db.add(DetectionProfile(id=uuid4().hex, name=profile.name,
                                        group_ids=[group_map[key] for key in profile.group_ids],
                                        rule_ids=[rule_map[key] for key in profile.rule_ids]))
            return {'imported_rules': len(bundle.rules), 'imported_groups': len(bundle.groups),
                    'imported_profiles': len(bundle.profiles), 'active_profile_changed': False}
        return self._write(operation)

rules_repository = RulesRepository()
