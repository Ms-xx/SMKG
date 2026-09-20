export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  role: "admin" | "annotator" | "reviewer" | "user";
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface Reference {
  index: number;
  authors: string;
  title: string;
  journal: string | null;
  year: string | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  doi: string | null;
  type: string;
  raw: string;
}

export interface Document {
  id: string;
  title: string;
  doi: string | null;
  authors: string[];
  abstract: string | null;
  keywords: string[];
  publication_date: string | null;
  journal: string | null;
  references: Reference[];
  file_path: string;
  file_size: number;
  page_count: number | null;
  status: "uploaded" | "parsing" | "parsed" | "failed";
  uploaded_by: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  page_size: number;
}

export interface Task {
  id: string;
  task_type: string;
  document_id: string | null;
  assigned_to: string | null;
  assigned_by: string | null;
  due_at: string | null;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  priority: number;
  progress: number;
  params: Record<string, any>;
  result: Record<string, any>;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
  page: number;
  page_size: number;
}

export interface Annotation {
  id: string;
  document_id: string;
  element_id: string | null;
  annotation_type: "ner" | "relation" | "correction";
  content: Record<string, any>;
  confidence: number | null;
  status: "draft" | "submitted" | "pending_final" | "approved" | "rejected";
  annotated_by: string;
  first_reviewed_by: string | null;
  first_review_comment: string | null;
  first_reviewed_at: string | null;
  final_reviewed_by: string | null;
  final_review_comment: string | null;
  final_reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OperationLog {
  id: string;
  user_id: string | null;
  action: "create" | "update" | "submit" | "first_review" | "final_review" | "delete" | string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, any>;
  ip_address: string | null;
  created_at: string;
}

export interface OperationLogListResponse {
  items: OperationLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface WorkloadStats {
  user_id: string;
  username: string | null;
  full_name: string | null;
  role: string | null;
  annotation_total: number;
  annotation_approved: number;
  annotation_rejected: number;
  annotation_pending: number;
  annotation_draft: number;
  accuracy_rate: number | null;
  task_total: number;
  task_completed: number;
  task_in_progress: number;
  task_failed: number;
}

export interface TeamDashboard {
  items: WorkloadStats[];
  total_users: number;
}

export interface AnnotationComment {
  id: string;
  annotation_id: string;
  parent_id: string | null;
  user_id: string;
  username: string | null;
  full_name: string | null;
  content: string;
  mentions: string[];
  created_at: string;
  updated_at: string;
}

export interface CommentListResponse {
  items: AnnotationComment[];
  total: number;
  page: number;
  page_size: number;
}

export interface AppNotification {
  id: string;
  type: "mention" | "reply" | "review" | string;
  title: string | null;
  content: string | null;
  sender_id: string | null;
  sender_name: string | null;
  resource_type: string;
  resource_id: string | null;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  items: AppNotification[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

export interface GraphEntity {
  id: string;
  labels: string[];
  properties: Record<string, any>;
}

export interface GraphRelation {
  id: string;
  type: string;
  startNode: string;
  endNode: string;
  properties: Record<string, any>;
}

export interface PermissionInfo {
  code: string;
  description: string;
}

export interface MyPermissions {
  role: string;
  permissions: string[];
}

export interface RoleItem {
  id: string;
  name: string;
  description: string;
  permissions: string[];
}

export interface RoleListResponse {
  items: RoleItem[];
  total: number;
}
