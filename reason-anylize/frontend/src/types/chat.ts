export interface UIAttachment {
  attachment_id?: number;
  file_name: string;
  file_type: string;
  file_size: number;
  parse_status?: string;
}

export interface UIMessage {
  key: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  createdAt?: string;
  attachments?: UIAttachment[];
  toolName?: string;
  toolStatus?: string;
  toolSummary?: string;
  taskId?: number;
  streaming?: boolean;
  local?: boolean;
}
