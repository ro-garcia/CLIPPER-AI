export type AIConfig = {
  enabled: boolean; provider: 'ollama'; model: string; endpoint: string;
  evaluation_mode: 'MANUAL'|'AUTOMATIC'; pre_context_seconds: number;
  max_pre_context_seconds: number; post_context_seconds: number; max_context_chars: number;
  temperature: number; max_concurrent: number; max_retries: number; timeout_seconds: number;
  per_stream_limit: number; create_clip_threshold: number; review_threshold: number;
  high_potential_threshold: number; good_threshold: number; medium_threshold: number;
  weights: Record<string,number>;
};
export type AIResult = {
  interest_score:number; clarity_score:number; virality_score:number; standalone_score:number;
  hook_score:number; ending_score:number; information_value_score:number;
  context_dependency_score:number; completeness_score:number; overall_score:number;
  quality_level:'HIGH_POTENTIAL'|'GOOD'|'MEDIUM'|'LOW';
  moment_summary:string; evaluation_reason:string; detected_topic:string; content_type:string;
  emotional_tone:string; requires_context:boolean; recommended_action:'CREATE_CLIP'|'REVIEW'|'DISCARD';
};
export type AIEvaluation = {id:string; moment_id:string; status:string; provider:string; model:string;
  evaluation_version:string; result:AIResult|null; latency_ms:number; attempts:number;
  error_message:string; error_code:string; created_at:string; input_tokens:number|null; output_tokens:number|null};
export type Moment = {id:string; stream_id:string; start:number; end:number; transcript_excerpt:string;
  language:string; moment_type:string; detection_confidence:number; status:string; media_status:string;
  media_error:string; clip_id:string|null; created_at:string; detection_reasons:Record<string,unknown>[]};
export type AIStatus = {status:string; queued:number; active:string|null; active_count:number; model:string;
  error:string; provider:string; evaluation_mode:'MANUAL'|'AUTOMATIC'; processing_local:boolean;
  completed:number; failed:number};
export type AIStatistics = {candidates:number; evaluated:number; high_potential:number; good:number; medium:number;
  low:number; failed:number; queued:number; evaluating:number; average_score:number|null; average_latency_ms:number|null};
export type RankingMoment = {rank:number; moment_id:string; overall_score:number; quality_level:string;
  moment_summary:string; start_time:number; created_at:string};
export const scoreNames = {
  interest_score:'Interés', clarity_score:'Claridad', virality_score:'Potencial de compartir',
  standalone_score:'Independencia', hook_score:'Inicio', ending_score:'Cierre',
  information_value_score:'Valor informativo', context_dependency_score:'Dependencia de contexto',
  completeness_score:'Completitud',
} as const;
