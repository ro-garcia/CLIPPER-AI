export const ruleTypes = [
  "KEYWORD",
  "KEY_PHRASE",
  "QUESTION_PATTERN",
  "STRONG_STATEMENT",
  "CONCLUSION",
  "REACTION",
  "TOPIC",
  "WARNING",
  "ANNOUNCEMENT",
  "CUSTOM",
] as const;
export const matchTypes = [
  "EXACT",
  "CONTAINS",
  "STARTS_WITH",
  "ENDS_WITH",
] as const;
export type RuleType = (typeof ruleTypes)[number];
export type MatchType = (typeof matchTypes)[number];
export interface RuleInput {
  name: string;
  pattern: string;
  rule_type: RuleType;
  category: string;
  weight: number;
  language: string;
  match_type: MatchType;
  case_sensitive: boolean;
  enabled: boolean;
  group_id: string | null;
}
export interface Rule extends RuleInput {
  id: string;
  created_at: string;
  updated_at: string;
}
export interface Group {
  id: string;
  name: string;
  enabled: boolean;
}
export interface ProfileInput {
  name: string;
  group_ids: string[];
  rule_ids: string[];
}
export interface Profile extends ProfileInput {
  id: string;
}
export interface Configuration {
  rules: Rule[];
  groups: Group[];
  profiles: Profile[];
  active_profile_id: string | null;
  revision: number;
  active_rule_ids: string[];
}
export interface Evaluation {
  detection_confidence: number;
  linguistic_weight: number;
  decision: string;
  creates_moment: boolean;
  creates_clip: boolean;
  revision: number;
  profile_id: string | null;
  profile_name: string | null;
  active_rule_count: number;
  matches: {
    rule_id: string;
    name: string;
    pattern: string;
    rule_type: string;
    category: string;
    weight: number;
  }[];
  has_audio?: boolean;
  window_seconds?: number;
  language: string;
}
export const labels: Record<string, string> = {
  KEYWORD: "Palabra clave",
  KEY_PHRASE: "Frase clave",
  QUESTION_PATTERN: "Pregunta",
  STRONG_STATEMENT: "Afirmación fuerte",
  CONCLUSION: "Conclusión",
  REACTION: "Reacción",
  TOPIC: "Tema",
  WARNING: "Advertencia",
  ANNOUNCEMENT: "Anuncio",
  CUSTOM: "Personalizada",
  EXACT: "Texto completo",
  CONTAINS: "Contiene",
  STARTS_WITH: "Empieza con",
  ENDS_WITH: "Termina con",
};
