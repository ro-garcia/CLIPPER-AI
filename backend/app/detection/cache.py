from dataclasses import dataclass
import unicodedata

def normalize(text: str, case_sensitive: bool = False) -> str:
    text = ' '.join(unicodedata.normalize('NFC', text).split())
    return text if case_sensitive else text.casefold()

@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    pattern: str
    rule_type: str
    category: str
    weight: float
    language: str
    match_type: str
    case_sensitive: bool
    normalized_pattern: str

@dataclass(frozen=True)
class RulesSnapshot:
    revision: int = 0
    profile_id: str | None = None
    profile_name: str | None = None
    rules: tuple[Rule, ...] = ()

    def for_language(self, language: str) -> tuple[Rule, ...]:
        language = language.lower()
        # Unknown language only uses language-independent rules, never guesses Spanish.
        return tuple(rule for rule in self.rules if rule.language == '*' or
                     rule.language == language or rule.language == language.split('-')[0])

class RulesCache:
    def __init__(self):
        self.snapshot = RulesSnapshot()

    def publish(self, rules: list[dict], groups: list[dict], profiles: list[dict], active_id: str | None):
        enabled_groups = {group['id'] for group in groups if group['enabled']}
        profile = next((p for p in profiles if p['id'] == active_id), None)
        selected = []
        for row in rules:
            if not row['enabled'] or (row['group_id'] is not None and row['group_id'] not in enabled_groups):
                continue
            if profile and row['id'] not in profile['rule_ids'] and row['group_id'] not in profile['group_ids']:
                continue
            selected.append(Rule(**{key: row[key] for key in (
                'id','name','pattern','rule_type','category','weight','language','match_type','case_sensitive')},
                normalized_pattern=normalize(row['pattern'], row['case_sensitive'])))
        # Readers see either the complete old snapshot or the complete new snapshot.
        self.snapshot = RulesSnapshot(self.snapshot.revision + 1, active_id,
                                      profile['name'] if profile else None, tuple(selected))
