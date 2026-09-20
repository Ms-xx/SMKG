import api from "./index";
import type {
  User,
  Document,
  DocumentListResponse,
  OperationLogListResponse,
  WorkloadStats,
  TeamDashboard,
  AnnotationComment,
  CommentListResponse,
  NotificationListResponse,
  PermissionInfo,
  MyPermissions,
  RoleItem,
  RoleListResponse,
} from "@/types";

export const authApi = {
  login: async (username: string, password: string) => {
    return api.post("/auth/login", { username, password });
  },
  register: async (data: {
    username: string;
    email: string;
    password: string;
    full_name?: string;
  }) => {
    return api.post("/auth/register", data);
  },
  logout: async () => api.post("/auth/logout"),
  getCurrentUser: async (): Promise<User> => api.get("/auth/me"),
};

export const documentApi = {
  upload: async (file: File, title?: string): Promise<Document> => {
    const formData = new FormData();
    formData.append("file", file);
    if (title) formData.append("title", title);
    return api.post("/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  getList: async (params: {
    page: number;
    page_size: number;
    status?: string;
    keyword?: string;
  }): Promise<DocumentListResponse> => {
    return api.get("/documents/", { params });
  },
  getById: async (id: string): Promise<Document> => api.get(`/documents/${id}`),
  delete: async (id: string): Promise<void> => api.delete(`/documents/${id}`, { timeout: 120000 }),
  triggerParse: async (id: string): Promise<{ task_id: string }> =>
    api.post(`/documents/${id}/parse`),
  getPageElements: async (documentId: string, pageNumber: number) =>
    api.get(`/documents/${documentId}/pages/${pageNumber}/elements`),
};

export const taskApi = {
  getList: async (params: {
    page: number;
    page_size: number;
    status?: string;
    task_type?: string;
  }) => api.get("/tasks/", { params }),
  getById: async (id: string) => api.get(`/tasks/${id}`),
  getProgress: async (id: string) => api.get(`/tasks/${id}/progress`),
  create: async (data: {
    task_type: string;
    document_id?: string;
    assigned_to?: string;
    priority?: number;
    due_at?: string;
    params?: Record<string, any>;
  }) => api.post("/tasks/", data),
  assign: async (id: string, data: { assigned_to: string; priority?: number; due_at?: string }) =>
    api.post(`/tasks/${id}/assign`, data),
  cancel: async (id: string) => api.post(`/tasks/${id}/cancel`),
  pause: async (id: string) => api.post(`/tasks/${id}/pause`),
  resume: async (id: string) => api.post(`/tasks/${id}/resume`),
  retry: async (id: string) => api.post(`/tasks/${id}/retry`),
  terminate: async (id: string) => api.delete(`/tasks/${id}/terminate`),
};

export const userApi = {
  getList: async (params?: { page?: number; page_size?: number }) => api.get("/users/", { params }),
  mentionable: async (): Promise<{ id: string; username: string; full_name?: string }[]> =>
    api.get("/users/mentionable"),
  updateProfile: async (
    userId: string,
    data: { full_name?: string; email?: string; avatar_url?: string },
  ) => api.put(`/users/${userId}`, data),
  changePassword: async (oldPassword: string, newPassword: string) =>
    api.post("/auth/change-password", { old_password: oldPassword, new_password: newPassword }),
};

export const annotationApi = {
  create: async (data: {
    document_id: string;
    element_id?: string;
    annotation_type: string;
    content: Record<string, any>;
    confidence?: number;
  }) => api.post("/annotations/", data),
  getByDocument: async (documentId: string) => api.get(`/annotations/document/${documentId}`),
  update: async (
    id: string,
    data: { content?: Record<string, any>; confidence?: number; base_updated_at?: string },
  ) => api.put(`/annotations/${id}`, data),
  submit: async (id: string) => api.post(`/annotations/${id}/submit`),
  firstReview: async (id: string, approved: boolean, comment?: string) =>
    api.post(`/annotations/${id}/first-review`, { approved, comment }),
  finalReview: async (id: string, approved: boolean, comment?: string) =>
    api.post(`/annotations/${id}/final-review`, { approved, comment }),
  getVersions: async (id: string) => api.get(`/annotations/${id}/versions`),
  lock: async (id: string) => api.post(`/annotations/${id}/lock`),
  unlock: async (id: string) => api.post(`/annotations/${id}/unlock`),
};

export const operationLogApi = {
  getList: async (params: {
    page: number;
    page_size: number;
    user_id?: string;
    action?: string;
    resource_type?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<OperationLogListResponse> => api.get("/operation-logs/", { params }),
};

export const statisticsApi = {
  getPersonal: async (): Promise<WorkloadStats> => api.get("/statistics/personal"),
  getTeam: async (): Promise<TeamDashboard> => api.get("/statistics/team"),
};

export const commentApi = {
  create: async (data: {
    annotation_id: string;
    content: string;
    parent_id?: string;
  }): Promise<AnnotationComment> => api.post("/comments/", data),
  list: async (params: {
    annotation_id?: string;
    document_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<CommentListResponse> => api.get("/comments/", { params }),
  remove: async (id: string) => api.delete(`/comments/${id}`),
};

export const notificationApi = {
  list: async (params: {
    page?: number;
    page_size?: number;
    unread_only?: boolean;
  }): Promise<NotificationListResponse> => api.get("/notifications/", { params }),
  unreadCount: async (): Promise<{ count: number }> => api.get("/notifications/unread-count"),
  markRead: async (id: string) => api.post(`/notifications/${id}/read`),
  markAllRead: async () => api.post("/notifications/read-all"),
};

export const permissionApi = {
  getMy: async (): Promise<MyPermissions> => api.get("/permissions/me"),
  getDefinitions: async (): Promise<{ items: PermissionInfo[]; total: number }> =>
    api.get("/permissions/definitions"),
  getRoles: async (): Promise<RoleListResponse> => api.get("/permissions/roles"),
  updateRolePermissions: async (roleName: string, permissions: string[]): Promise<RoleItem> =>
    api.put(`/permissions/roles/${roleName}`, { permissions }),
};

export const graphApi = {
  // ── Neo4j 图谱查询 (主系统) - 需要认证
  search: async (query: string, entityType?: string, limit = 20) =>
    api.get("/knowledge-graph/search", { params: { query, entity_type: entityType, limit } }),
  getEntity: async (entityId: string) => api.get(`/knowledge-graph/entities/${entityId}`),
  getEntityRelations: async (entityId: string, depth = 1) =>
    api.get(`/knowledge-graph/entities/${entityId}/relations`, { params: { depth } }),
  executeCypher: async (cypher: string, params?: Record<string, any>) =>
    api.post("/knowledge-graph/query", { cypher, params }),
  getStatistics: async () => api.get("/knowledge-graph/statistics"),
  // ── GraphRAG 集成 (代理到 GraphRAGTest :8001) - 需要认证
  ragHealth: async () => api.get("/knowledge-graph/rag/health"),
  ragStatus: async () => api.get("/knowledge-graph/rag/llm/status"),
  ragListModels: async () => api.get("/knowledge-graph/rag/llm/models"),
  ragLoadModel: async (model?: string) =>
    api.post("/knowledge-graph/rag/llm/load", model ? { model } : {}),
  ragQuery: async (question: string, returnContext = false) =>
    api.post("/knowledge-graph/rag/query", { question, return_context: returnContext }),
  ragGraphStats: async () => api.get("/knowledge-graph/rag/graph/stats"),
  ragNodesByLabel: async (label: string, limit = 50) =>
    api.get(`/knowledge-graph/rag/graph/nodes/${label}`, { params: { limit } }),
  ragSearchNodes: async (keyword: string, limit = 20) =>
    api.get(`/knowledge-graph/rag/graph/search/${keyword}`, { params: { limit } }),
  ragGraphSearch: async (relType: string, limit = 20) =>
    api.get(`/knowledge-graph/rag/graph/relations/type/${relType}`, { params: { limit } }),
  ragIndexDocument: async (data: {
    doc_id: string;
    doc_title: string;
    entities: any[];
    relations: any[];
    metadata?: any;
  }) => api.post("/knowledge-graph/rag/index/document", data),
  ragAddNode: async (label: string, id: string, properties: Record<string, any> = {}) =>
    api.post("/knowledge-graph/rag/graph/nodes", { label, id, properties }),
  ragAddRelation: async (
    source_label: string,
    source_id: string,
    target_label: string,
    target_id: string,
    rel_type: string,
    properties: Record<string, any> = {},
  ) =>
    api.post("/knowledge-graph/rag/graph/relations", {
      source_label,
      source_id,
      target_label,
      target_id,
      rel_type,
      properties,
    }),
  ragClearGraph: async () => api.post("/knowledge-graph/rag/graph/clear"),
  ragSeedDemoData: async () => api.post("/knowledge-graph/rag/graph/seed"),
};
