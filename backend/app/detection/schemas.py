from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RuleType = Literal['KEYWORD', 'KEY_PHRASE', 'QUESTION_PATTERN', 'STRONG_STATEMENT',
                   'CONCLUSION', 'REACTION', 'TOPIC', 'WARNING', 'ANNOUNCEMENT', 'CUSTOM']
MatchType = Literal['EXACT', 'CONTAINS', 'STARTS_WITH', 'ENDS_WITH']

class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)

class GroupInput(InputModel):
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True

class RuleInput(InputModel):
    name: str = Field(min_length=1, max_length=100)
    pattern: str = Field(min_length=1, max_length=500)
    rule_type: RuleType = 'KEYWORD'
    category: str = Field(default='', max_length=100)
    weight: float = Field(default=0.1, ge=-1, le=1)
    language: str = Field(default='*', pattern=r'^(\*|[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*)$', max_length=35)
    match_type: MatchType = 'CONTAINS'
    case_sensitive: bool = False
    enabled: bool = True
    group_id: str | None = Field(default=None, max_length=64)

    @field_validator('language')
    @classmethod
    def normalize_language(cls, value: str) -> str:
        return value.lower()

class ProfileInput(InputModel):
    name: str = Field(min_length=1, max_length=100)
    group_ids: list[str] = Field(default_factory=list, max_length=100)
    rule_ids: list[str] = Field(default_factory=list, max_length=1000)

    @field_validator('group_ids', 'rule_ids')
    @classmethod
    def unique_ids(cls, values: list[str]) -> list[str]:
        if any(len(value) > 64 for value in values):
            raise ValueError('Identificador demasiado largo.')
        return list(dict.fromkeys(values))

class ActiveProfile(InputModel):
    profile_id: str | None = Field(default=None, max_length=64)

class PreviewInput(InputModel):
    text: str = Field(min_length=1, max_length=20000)
    language: str = Field(default='*', pattern=r'^(\*|[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*)$', max_length=35)

class ExportGroup(GroupInput):
    id: str = Field(min_length=1, max_length=64)

class ExportRule(RuleInput):
    id: str = Field(min_length=1, max_length=64)

class ExportProfile(ProfileInput):
    id: str = Field(min_length=1, max_length=64)

class RulesBundle(InputModel):
    schema_version: Literal[1] = 1
    groups: list[ExportGroup] = Field(default_factory=list, max_length=100)
    rules: list[ExportRule] = Field(default_factory=list, max_length=1000)
    profiles: list[ExportProfile] = Field(default_factory=list, max_length=100)
    active_profile_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode='after')
    def references(self):
        groups, rules, profiles = (set(item.id for item in items) for items in (self.groups, self.rules, self.profiles))
        if any(len(ids) != len(items) for ids, items in ((groups,self.groups),(rules,self.rules),(profiles,self.profiles))):
            raise ValueError('El archivo contiene identificadores duplicados.')
        if any(rule.group_id is not None and rule.group_id not in groups for rule in self.rules):
            raise ValueError('Una regla hace referencia a un grupo inexistente.')
        if any(set(p.group_ids) - groups or set(p.rule_ids) - rules for p in self.profiles):
            raise ValueError('Un perfil hace referencia a reglas o grupos inexistentes.')
        if self.active_profile_id is not None and self.active_profile_id not in profiles:
            raise ValueError('El perfil activo del archivo no existe.')
        return self
