export type UserRole = 'analyst' | 'admin' | string;
export type ConversationStatus = 'active' | 'archived' | 'deleted' | string;
export type ParseStatus = 'pending' | 'parsing' | 'parsed' | 'failed' | string;
export type TaskStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled' | string;

export interface User {
  user_id: number;
  username: string;
  display_name: string;
  role: UserRole;
  status: string;
}

export interface Conversation {
  conversation_id: number;
  title: string;
  status: ConversationStatus;
  last_message_at: string | null;
}

export interface AttachmentMeta {
  attachment_id: number;
  conversation_id: number;
  message_id: number | null;
  file_name: string;
  file_type: string;
  file_size: number;
  parse_status: ParseStatus;
  created_at: string;
}

export interface MessageAttachment {
  attachment_id: number;
  file_name: string;
  file_type: string;
  file_size: number;
  parse_status: ParseStatus;
}

export interface ChatMessageRecord {
  message_id: number;
  role: 'user' | 'assistant' | 'tool' | string;
  content: string;
  message_type: string;
  tool_name: string | null;
  tool_status: string | null;
  seq_no: number;
  attachments: MessageAttachment[];
  created_at: string;
}

export interface TaskInfo {
  task_id: number;
  conversation_id: number;
  task_status: TaskStatus;
  current_step: string;
  input_text: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

export interface KeyMetric {
  metric_name: string;
  metric_value: string | number;
  metric_unit: string;
  metric_period: string;
}

export interface EvidenceItem {
  source_type: string;
  source_name: string;
  evidence_text: string;
  related_metric: string;
  confidence: 'high' | 'medium' | 'low' | string;
}

export interface AnalysisResult {
  result_id: number;
  task_id: number;
  problem_definition: string;
  key_metrics: KeyMetric[];
  evidence_list: EvidenceItem[];
  conclusion_text: string;
  missing_data_text: string;
  next_action_text: string[];
  result_markdown: string;
  result_file_path: string | null;
  created_at: string;
}

export interface SystemConfigItem {
  config_key: string;
  config_value: string;
  config_group: string;
  updated_at: string;
}

export interface FeatureResponse {
  features: Record<string, string>;
}

export interface LogsResponse {
  logs: string;
  lines: number;
}

export interface DataSourceInfo {
  current: {
    type: string;
    conn: string;
  };
  database_url: string;
}

export interface DataSourceTestResult {
  ok: boolean;
  message: string;
}

export interface WsTokenResponse {
  websocket_token: string;
  expires_in: number;
}

export interface AttachmentUploadResponse {
  attachment_id: number;
  file_name: string;
  file_path: string;
}
