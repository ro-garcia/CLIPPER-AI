from fastapi import APIRouter, HTTPException
from .repository import rules_repository as repo, RulesError
from .schemas import RuleInput, GroupInput, ProfileInput, ActiveProfile, RulesBundle, PreviewInput
from .extractor import evaluate_text

router = APIRouter(tags=['Moment detection rules'])

def call(operation, *args):
    try:
        return operation(*args)
    except RulesError as exc:
        raise HTTPException(exc.status, str(exc)) from exc

@router.get('/moment-rules/configuration')
def configuration():
    return repo.configuration()

@router.get('/moment-rules/export')
def export_rules():
    return repo.export()

@router.post('/moment-rules/import')
def import_rules(bundle: RulesBundle):
    return call(repo.import_bundle, bundle)

@router.post('/moment-rules/preview')
def preview_rules(payload: PreviewInput):
    return evaluate_text(payload.text, payload.language, repo.cache.snapshot)

@router.get('/moment-rules/groups')
def groups():
    return repo.configuration()['groups']

@router.post('/moment-rules/groups', status_code=201)
def create_group(payload: GroupInput):
    return call(repo.save, 'groups', payload)

@router.put('/moment-rules/groups/{identifier}')
def update_group(identifier: str, payload: GroupInput):
    return call(repo.save, 'groups', payload, identifier)

@router.delete('/moment-rules/groups/{identifier}')
def delete_group(identifier: str):
    return call(repo.delete, 'groups', identifier)

@router.get('/moment-rules')
def rules():
    return repo.configuration()['rules']

@router.post('/moment-rules', status_code=201)
def create_rule(payload: RuleInput):
    return call(repo.save, 'rules', payload)

@router.put('/moment-rules/{identifier}')
def update_rule(identifier: str, payload: RuleInput):
    return call(repo.save, 'rules', payload, identifier)

@router.delete('/moment-rules/{identifier}')
def delete_rule(identifier: str):
    return call(repo.delete, 'rules', identifier)

@router.post('/moment-rules/{identifier}/enable')
def enable_rule(identifier: str):
    return call(repo.set_enabled, 'rules', identifier, True)

@router.post('/moment-rules/{identifier}/disable')
def disable_rule(identifier: str):
    return call(repo.set_enabled, 'rules', identifier, False)

@router.get('/moment-profiles')
def profiles():
    return repo.configuration()['profiles']

@router.post('/moment-profiles', status_code=201)
def create_profile(payload: ProfileInput):
    return call(repo.save, 'profiles', payload)

@router.post('/moment-profiles/active')
def activate_profile(payload: ActiveProfile):
    return call(repo.activate, payload.profile_id)

@router.put('/moment-profiles/{identifier}')
def update_profile(identifier: str, payload: ProfileInput):
    return call(repo.save, 'profiles', payload, identifier)

@router.delete('/moment-profiles/{identifier}')
def delete_profile(identifier: str):
    return call(repo.delete, 'profiles', identifier)
