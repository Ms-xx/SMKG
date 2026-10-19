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
  affiliations: string[];
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

export interface TitleTreeItem {
  level: number;
  title: string;
  page_number: number;
}

export interface TitleTreeResponse {
  backend: string;
  tree: TitleTreeItem[];
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

export interface ActiveLearningSuggestionItem {
  rank: number;
  element_id: string;
  document_id: string;
  document_title: string | null;
  element_type: string;
  page_number: number | null;
  confidence: number;
  score: number;
  method: string;
  text: string;
}

export interface AgentDescriptor {
  name: string;
  description: string;
  kind: "text" | "items";
}

export interface AgentResult {
  agent: string;
  description: string;
  content: string;
  items: { text: string; type: string; confidence?: number }[] | null;
  confidence: number;
  backend: string;
}

export interface MultiAgentConflict {
  type: string;
  agents?: string[];
  description?: string;
  text?: string;
  types?: string[];
  answers?: { agent: string; answer: string; confidence: number }[];
}

export interface MultiAgentRunResult {
  session_id: string;
  query: string;
  mode: string;
  backend: string;
  agents: string[];
  agent_results: AgentResult[];
  conflicts: MultiAgentConflict[];
  resolution: {
    mode: string;
    final_text: string | null;
    final_items: { text: string; type: string }[] | null;
    unresolved: { type: string; description?: string }[];
  };
  created_at: number;
}

// ── 10.2 缺失功能模块类型 ──────────────────────────────────────────

export interface DedupClusterDoc {
  id: string | null;
  title: string | null;
  version: string | null;
}

export interface DedupCluster {
  size: number;
  document_ids: (string | null)[];
  documents: DedupClusterDoc[];
  suggestion: { keep: string | null; reason: string };
}

export interface DedupDetectResult {
  backend: string;
  threshold: number;
  total_documents: number;
  duplicate_pairs: { a_id: string | null; b_id: string | null; similarity: number }[];
  cluster_count: number;
  clusters: DedupCluster[];
}

export interface SourceAnchorItem {
  document_id: string;
  page_number: number | null;
  chunk_index?: number | null;
  snippet: string;
  score: number;
}

export interface SourcePerspective {
  document_id: string;
  title: string;
  best_score: number;
}

export interface SourceCompareResult {
  backend: string;
  question: string;
  candidate_count: number;
  perspectives: SourcePerspective[];
  top_chunks: { document_id: string; title: string; snippet: string; score: number }[];
  conclusion: string;
}

export interface InlineCitation {
  ref_index: number | null;
  start: number;
  end: number;
  kind: string;
  raw: string;
  snippet: string;
  page_index?: number;
  page_number?: number;
}

export interface CitationMapResult {
  backend: string;
  total_citations: number;
  references_count: number;
  citations: InlineCitation[];
  by_reference: Record<string, InlineCitation[]>;
}

export interface PaperResult {
  title: string;
  summary: string;
  authors: string[];
  arxiv_id?: string;
  pubmed_id?: string;
  published: string;
  source: string;
}

export interface PaperSearchResult {
  backend: string;
  query: string;
  count: number;
  results: PaperResult[];
  error?: string;
}

export interface PaperRecommendation {
  title: string | null;
  source: string | null;
  score: number;
  reason: string;
}

export interface CitationNode {
  id: string;
  label: string;
  year?: string;
  doi?: string;
  ref_index?: number;
}

export interface CitationEdge {
  source: string;
  target: string;
  type?: string;
}

export interface CitationNetwork {
  backend: string;
  node_count: number;
  edge_count: number;
  nodes: CitationNode[];
  edges: CitationEdge[];
}

export interface KeyPaper {
  id: string;
  label?: string;
  year?: string;
  page_rank: number;
  betweenness: number;
}

export interface SurveyResult {
  backend: string;
  reference_count: number;
  timeline: { year: string; count: number }[];
  top_papers: string[];
  survey: string;
}

export interface OutlineSection {
  title: string;
  content: string;
}

export interface OutlineResult {
  backend: string;
  idea: string;
  sections: OutlineSection[];
  references: { index: number | null; text: string }[];
  reference_count: number;
  note: string;
}

// ── 步骤 21：GitHub 开源复现性优先推荐 ────────────────────────────────

export interface RepoMeta {
  repo: string;
  html_url: string | null;
  source: "online" | "offline";
  star_count: number | null;
  license: string | null;
  latest_push: string | null;
  open_issues: number | null;
  updated_at: string | null;
  error?: string | null;
}

export interface RepoRecommendation {
  title: string | null;
  source: string | null;
  arxiv_id?: string | null;
  open_source: boolean;
  repos: RepoMeta[];
  correlation_score: number;
  reproducibility_score: number;
  feedback_score: number;
  feedback_net: number;
  total_score: number;
  reason: string;
}

export interface RepoRecommendResult {
  backend: string;
  github_online: boolean;
  count: number;
  recommendations: RepoRecommendation[];
  records: Record<string, any>[];
}

// ── 步骤 19：跨文献结构化演进对比矩阵 ──────────────────────────────────

export interface CompareMatrixAnchor {
  document_id: string;
  page: number | null;
  chunk: number | null;
  snippet: string;
}

export interface CompareMatrixCell {
  document_id: string;
  title: string | null;
  value: string | null;
  anchored: boolean;
  anchors: CompareMatrixAnchor[];
  note?: string;
}

export interface CompareMatrixRow {
  dimension: string;
  cells: CompareMatrixCell[];
}

export interface CompareMatrixInsight {
  backend: string;
  matrix_backend?: string | null;
  insight: string;
  note: string;
}

export interface CompareMatrixResult {
  backend: string;
  dimension_count: number;
  document_count: number;
  dimensions: string[];
  document_columns: { index: number; document_id: string; title: string | null }[];
  rows: CompareMatrixRow[];
  anchor_coverage: { total_cells: number; anchored_cells: number; coverage_pct: number };
  insight?: CompareMatrixInsight;
}

// ── 步骤 20：引用含金量筛选 ────────────────────────────────────────────

export interface CitationQualitySignal {
  signal: string;
  level?: number | string;
  hit?: boolean;
  detail?: string;
}

export interface CitationQualityRef {
  index: number | string | null;
  title: string;
  score: number;
  label: "core" | "supporting" | "perfunctory";
  signals: CitationQualitySignal[];
  position?: string;
  occurrences?: number;
}

export interface CitationQualityDoc {
  document_id: string;
  title: string | null;
  total: number;
  core_count: number;
  supporting_count: number;
  perfunctory_count: number;
  thresholds: { perfunctory_threshold: number; supporting_threshold: number };
  refs: CitationQualityRef[];
}

export interface CitationQualityResult {
  backend: string;
  document_count: number;
  total_refs: number;
  perfunctory_count: number;
  core_count: number;
  documents: CitationQualityDoc[];
}

// ── 步骤 22：Future Work 前沿探索 ──────────────────────────────────────

export interface FutureWorkIdea {
  document_id: string;
  title: string | null;
  year: number | null;
  keyword: string | null;
  idea: string;
  snippet: string;
  resolved: boolean;
  confidence: number;
  resolved_by: string[];
  evidence: { document_id: string; title: string | null; year: number | null }[];
  reason: string;
}

export interface FutureWorkResult {
  backend: string;
  idea_count: number;
  excluded_count: number;
  candidate_count: number;
  time_buckets: { year: number; count: number }[];
  excluded: FutureWorkIdea[];
  candidates: FutureWorkIdea[];
  filtered?: {
    domain: string | null;
    min_year: number | null;
    max_year: number | null;
    applied_document_count: number;
  };
}
