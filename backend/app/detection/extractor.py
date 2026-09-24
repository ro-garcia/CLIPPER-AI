"""Pure linguistic signals. No vocabulary, regex, database or clip creation."""
from dataclasses import dataclass, asdict
from .cache import RulesSnapshot, normalize

@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    name: str
    pattern: str
    rule_type: str
    category: str
    weight: float

class FeatureExtractor:
    def extract(self, text: str, language: str, snapshot: RulesSnapshot) -> list[RuleMatch]:
        normalized = {False: normalize(text), True: normalize(text, True)}
        matches = []
        for rule in snapshot.for_language(language):
            value, pattern = normalized[rule.case_sensitive], rule.normalized_pattern
            hit = (value == pattern if rule.match_type == 'EXACT' else
                   pattern in value if rule.match_type == 'CONTAINS' else
                   value.startswith(pattern) if rule.match_type == 'STARTS_WITH' else
                   value.endswith(pattern) if rule.match_type == 'ENDS_WITH' else False)
            if hit:
                # Each rule contributes once per window, even if repeated many times.
                matches.append(RuleMatch(rule.id, rule.name, rule.pattern, rule.rule_type, rule.category, rule.weight))
        return matches

class HeuristicEvaluator:
    def evaluate(self, matches: list[RuleMatch]) -> dict:
        total = sum(match.weight for match in matches)
        return {'linguistic_weight': round(total, 4),
                'detection_confidence': round(max(0, min(1, total)), 4),
                'decision': 'SIGNALS_ONLY', 'creates_moment': False, 'creates_clip': False,
                'matches': [asdict(match) for match in matches]}

def evaluate_text(text: str, language: str, snapshot: RulesSnapshot) -> dict:
    return {**HeuristicEvaluator().evaluate(FeatureExtractor().extract(text, language, snapshot)),
            'revision': snapshot.revision, 'profile_id': snapshot.profile_id,
            'profile_name': snapshot.profile_name, 'language': language,
            'active_rule_count': len(snapshot.for_language(language))}
