import type { MessagePart } from './messageParts';

export interface MessageResponse {
  message: string;
}

// Auth
export interface AuthLoginRequest {
  email: string;
  password: string;
}

export interface AuthRegisterRequest {
  email: string;
  name: string;
  password: string;
}

export interface GoogleLoginRequest {
  credential: string;
}

export interface LoginResponse {
  token: string;
}

export interface UserProfileRead {
  id: number;
  email: string;
  name?: string | null;
  profile_image_url?: string | null;
  ai_moments_default: boolean;
  credits_balance: number;
  created_at?: string | null;
}

export interface UserProfileUpdate {
  name?: string;
  ai_moments_default?: boolean;
}

export interface ApiTokenRead {
  id: number;
  name: string;
  token_hint: string;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiTokenCreated extends ApiTokenRead {
  /** Shown once; only its hash is stored. */
  token: string;
}

// Payments
export interface CreditProduct {
  product_id: string;
  credits: number;
  name: string;
  price_inr: number;
  price_per_credit: number;
}

export interface CreditProductListResponse {
  products: CreditProduct[];
}

// Videos
export interface VideoMetadata {
  title?: string;
  uploader?: string;
  channel_url?: string;
  duration?: number;
  thumbnail?: string;
  view_count?: number;
  like_count?: number;
  upload_date?: string;
}

export interface KeyPoint {
  text: string;
  start_seconds: number;
  end_seconds: number;
}

export interface VideoRead {
  id: number;
  video_id: string;
  title: string | null;
  transcript_status: TranscriptStatus;
  metadata: VideoMetadata | null;
  summary: string | null;
  overview_status: OverviewStatus;
  suggested_questions: string[] | null;
  key_points: KeyPoint[] | null;
  overview_model?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TranscriptSegment {
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export type TranscriptStatus = 'pending' | 'ready' | 'unavailable';

/** pending waits for the transcript; no_transcript means there will be none. */
export type OverviewStatus = 'pending' | 'queued' | 'ready' | 'failed' | 'no_transcript';

export interface TranscriptRead {
  video_id: string;
  status: TranscriptStatus;
  segments: TranscriptSegment[];
}

// Moments
export type AiStatus =
  | 'not_requested'
  | 'waiting_transcript'
  | 'queued'
  | 'ready'
  | 'failed'
  | 'no_transcript'
  | 'insufficient_credits';

export type ResolveStatus = 'resolving' | 'resolved' | 'unresolved';

export type CaptureSource = 'phone' | 'extension' | 'web' | 'api' | 'legacy';

export interface ResolveCandidate {
  video_id: string;
  title: string | null;
  channel: string | null;
}

export interface MomentRead {
  id: number;
  video_id: string | null;
  at_seconds: number;
  quote: string | null;
  quote_start_seconds: number | null;
  ai_text: string | null;
  /** The model that wrote ai_text. */
  ai_model?: string | null;
  note: string | null;
  ai_status: AiStatus;
  resolve_status: ResolveStatus;
  source: CaptureSource;
  pending_title: string | null;
  resolve_candidates: ResolveCandidate[] | null;
  created_at: string;
  updated_at: string;
}

export interface FeedMoment extends MomentRead {
  video_title: string | null;
  video_metadata: VideoMetadata | null;
}

export interface MomentFeed {
  moments: FeedMoment[];
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface CaptureCreate {
  video?: string;
  title?: string;
  channel?: string;
  at: number | string;
  note?: string | null;
  ai?: boolean;
  source: Exclude<CaptureSource, 'legacy'>;
}

export interface CaptureResponse {
  moment: MomentRead;
  merged: boolean;
}

export interface MomentUpdate {
  note?: string | null;
  ai_text?: string | null;
}

export interface PassageSave {
  video_id: string;
  start_seconds: number;
  end_seconds: number;
  note?: string | null;
}

export type ResurfaceResponse = { state: 'found'; moment: FeedMoment } | { state: 'none' };

// Library
export type LibrarySort = 'activity_desc' | 'added_desc' | 'title_asc' | 'title_desc' | 'moments_desc' | 'chats_desc';
export type LibraryView = 'all' | 'with_moments' | 'with_chats';

export interface LibraryVideo {
  video_id: string;
  title: string | null;
  metadata: VideoMetadata | null;
  transcript_status: TranscriptStatus;
  overview_status: OverviewStatus;
  moment_count: number;
  chat_count: number;
  latest_moment: { text: string; kind: 'note' | 'ai' | 'quote' } | null;
  added_at: string;
  last_activity_at: string;
}

export interface LibraryResponse {
  counts: Record<LibraryView, number>;
  videos: LibraryVideo[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// Search
export interface VideoBrief {
  video_id: string;
  title: string | null;
  thumbnail_url: string;
}

export interface SnippetPart {
  text: string;
  highlight: boolean;
}

export interface MomentResult {
  kind: 'moment';
  video: VideoBrief;
  moment: MomentRead;
  start_seconds: number;
  snippet: SnippetPart[];
  score: number;
}

export interface PassageResult {
  kind: 'passage';
  video: VideoBrief;
  chunk_id: number;
  start_seconds: number;
  end_seconds: number;
  snippet: SnippetPart[];
  score: number;
}

export type SearchResult = MomentResult | PassageResult;

export interface SearchResponse {
  query: string;
  match: 'exact' | 'fuzzy' | 'none';
  results: SearchResult[];
  page: number;
  per_page: number;
  has_more: boolean;
}

// Conversations
export type ConversationScope = 'video' | 'library';

export interface ConversationRead {
  id: number;
  scope: ConversationScope;
  video_id: string | null;
  created_at: string;
  updated_at: string;
}

export type ConversationCreate =
  | { scope: 'video'; video_id: string }
  | { scope: 'library' };

export interface ConversationSummary {
  id: number;
  scope: ConversationScope;
  video_id: string | null;
  video_title: string | null;
  title: string;
  message_count: number;
  last_message_at: string;
}

export interface ConversationList {
  conversations: ConversationSummary[];
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface MessageRead {
  parts: MessagePart[];
  id: number;
  conversation_id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}
