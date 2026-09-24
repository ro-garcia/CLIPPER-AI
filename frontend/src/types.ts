export interface StreamInfo {
  title: string;
  platform: string;
  thumbnail?: string;
  height?: number;
  fps?: number;
  is_live: boolean;
  source_url: string;
}
export interface StreamState {
  state: string;
  error: string;
  stream_id: string | null;
  info: StreamInfo | null;
  elapsed: number;
  buffer_seconds: number;
  buffer_capacity: number;
  transcription_status: string;
  transcription_error: string;
  transcription_queue: number;
  dropped_segments?: number;
  capture_mode?: string;
}
export interface Clip {
  id: string;
  title: string;
  status: string;
  duration: number;
  created_at: string;
  error: string;
  source_start: number | null;
  source_end: number | null;
  render_status: "NOT_RENDERED" | "QUEUED" | "PROCESSING" | "READY" | "FAILED";
  render_progress: number;
  render_stage: string;
  render_error: string;
  render_settings: RenderSettings | null;
  output_width: number | null;
  output_height: number | null;
  rendered_at: string;
  metadata_status: "METADATA_PENDING" | "METADATA_GENERATING" | "METADATA_READY" | "METADATA_FAILED";
  metadata_error: string;
}

export interface GeneralMetadata {
  title: string;
  description: string;
  caption: string;
  cover_text: string;
  hashtags: string[];
  keywords: string[];
  category: string;
  content_type: string;
  topic: string;
  language: string;
  title_variants: string[];
  caption_variants: string[];
  cover_text_variants: string[];
}

export interface CaptionPlatform { caption: string; hashtags: string[] }
export interface YouTubeMetadata { title: string; description: string; hashtags: string[] }
export interface ContentMetadata {
  clip_id: string;
  status: Clip["metadata_status"];
  publication_status: "READY_TO_PUBLISH" | "NOT_READY";
  error: string;
  general: GeneralMetadata | null;
  platforms: {
    tiktok: CaptionPlatform;
    youtube_shorts: YouTubeMetadata;
    instagram_reels: CaptionPlatform;
    facebook_reels: CaptionPlatform;
  } | null;
  ai_model?: string;
}

export interface RenderSettings {
  subtitles_enabled: boolean;
  subtitle_style: "STANDARD" | "DYNAMIC";
  font: string;
  font_size: number;
  font_color: string;
  outline_size: number;
  background: boolean;
  subtitle_position: "TOP" | "MIDDLE" | "BOTTOM";
  max_lines: number;
  max_chars_per_line: number;
  min_subtitle_duration: number;
  max_subtitle_duration: number;
  highlight_words: boolean;
  animation_enabled: boolean;
  output_width: number;
  output_height: number;
  video_codec: "libx264";
  audio_codec: "aac";
  crf: number;
  fps: number;
  reframing_mode: "CENTER_CROP" | "SMART_CROP" | "SUBJECT_TRACKING";
  background_mode: "CROP" | "BLUR" | "BLACK";
  safe_area_top: number;
  safe_area_bottom: number;
  safe_area_left: number;
  safe_area_right: number;
  max_concurrent_renders: 1;
}

export interface RenderStatus {
  status: "READY" | "PROCESSING" | "ERROR";
  queued: number;
  active: string | null;
  active_count: number;
  max_concurrent_renders: number;
  error: string;
  processing_local: boolean;
}
export interface Transcript {
  id: number;
  start: number;
  end: number;
  text: string;
}
export interface System {
  capture_mode?: string;
  whisper_threads?: number;
  capture_max_height?: number;
  backend: string;
  ffmpeg: string;
  whisper: string;
  model: string;
  device: string;
  database: string;
}
export interface Resources {
  cpu: number;
  ram_used: number;
  ram_total: number;
  storage_free: number;
  gpu: number | null;
}

export type SocialPlatform = "youtube" | "tiktok" | "instagram" | "facebook";
export interface SocialAccount {
  id: string; platform: SocialPlatform; display_name: string; external_account_id: string;
  status: string; scopes: string[]; permissions: string[]; expires_at: string;
  last_validation: string; provider_mode: "mock" | "real"; has_secure_token: boolean;
}
export interface PlatformCapability {
  platform: SocialPlatform; support: string; configured: boolean; configuration_required: string;
  capabilities: { publish_now: boolean; schedule: boolean; delete: boolean; status_check: boolean; analytics: boolean; cancel_upload: boolean };
}
export interface PublicationJob {
  id: string; clip_id: string; platform: SocialPlatform; account_id: string; account_name: string;
  account_mode: string; status: string; scheduled_at: string; started_at: string; published_at: string;
  platform_media_id: string; publication_url: string; attempt_count: number; error_code: string;
  last_error: string; overrides: Record<string, string | string[]>; progress: number | null;
  stage: string; created_at: string; updated_at: string;
}
export interface PublishingStatus {
  status: string; safe_publish_mode: boolean; publishing_mode: "mock" | "real";
  active: string[]; active_count: number; queued: number; scheduled: number; max_concurrent_publications: number;
}
export interface PublishingConfig {
  social_publishing_enabled: boolean; publishing_mode: "mock" | "real"; safe_publish_mode: boolean;
  publication_workflow: "MANUAL" | "REVIEW" | "AUTOMATIC"; max_concurrent_publications: number;
  max_retry_attempts: number; missed_schedule_policy: "PUBLISH_WHEN_AVAILABLE" | "ASK_USER" | "CANCEL";
  youtube_enabled: boolean; tiktok_enabled: boolean; instagram_enabled: boolean; facebook_enabled: boolean;
  youtube_privacy_status: "private" | "unlisted" | "public"; auto_publish: boolean;
  minimum_score: number; auto_publish_platforms: SocialPlatform[]; allowed_content_types: string[]; blocked_content_types: string[];
}
