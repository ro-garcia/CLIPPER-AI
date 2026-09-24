"""Candidate detection composes configurable lexical signals with structural evidence."""
from dataclasses import dataclass
from ..detection.cache import RulesSnapshot, normalize
from ..detection.extractor import FeatureExtractor

@dataclass(frozen=True)
class Candidate:
    start: float
    end: float
    text: str
    language: str
    confidence: float
    reasons: list[dict]
    kind: str
    revision: int

def detect(parts: list[dict], language: str, snapshot: RulesSnapshot, threshold=.65) -> Candidate | None:
    if not parts:
        return None
    end = parts[-1]['end']
    selected = [part for part in parts if part['end'] > end - 45]
    start = selected[0]['start']
    duration = end - start
    text = ' '.join(part['text'] for part in selected).strip()
    words = text.split()
    if not 20 <= duration <= 90 or len(words) < 15:
        return None
    matches = FeatureExtractor().extract(text, language, snapshot)
    if not matches:
        return None
    # No vocabulary here: duration, lexical diversity, speech density and closure.
    density = len(words) / duration
    diversity = len(set(normalize(word) for word in words)) / len(words)
    if not .4 <= density <= 5 or diversity < .2:
        return None
    lexical = max(0, min(.55, sum(match.weight for match in matches)))
    structural = .15 + .1 + (.1 if text.endswith(('.', '?', '!', '…', '。', '？', '！')) else 0)
    structural += .1 if len({match.rule_type for match in matches}) >= 2 else 0
    confidence = round(min(1, lexical + structural), 4)
    if confidence < threshold:
        return None
    reasons = [{'kind':'RULE','rule_id':match.rule_id,'name':match.name,'weight':match.weight}
               for match in matches]
    reasons.append({'kind':'STRUCTURE','duration':round(duration,2),
                    'words_per_second':round(density,2),'lexical_diversity':round(diversity,2),
                    'weight':round(structural,2)})
    return Candidate(start,end,text,language,confidence,reasons,matches[0].rule_type,snapshot.revision)

def duplicate(candidate: Candidate, previous: list[dict]) -> bool:
    tokens = set(normalize(candidate.text).split())
    for old in previous:
        overlap = max(0, min(candidate.end,old['end']) - max(candidate.start,old['start']))
        union = max(candidate.end,old['end']) - min(candidate.start,old['start'])
        if union and overlap / union >= .45:
            return True
        other = set(normalize(old['transcript_excerpt']).split())
        if tokens and len(tokens & other) / len(tokens | other) >= .88:
            return True
    return False
