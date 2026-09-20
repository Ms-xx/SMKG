import { create } from "zustand";
import { documentApi } from "@api/modules";
import type { Document } from "@/types";

interface DocumentState {
  documents: Document[];
  currentDocument: Document | null;
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  filters: { status?: string; keyword?: string };
  fetchDocuments: () => Promise<void>;
  fetchDocument: (id: string) => Promise<void>;
  uploadDocument: (file: File, title?: string) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  triggerParse: (id: string) => Promise<void>;
  setFilters: (filters: Partial<DocumentState["filters"]>) => void;
  setPage: (page: number) => void;
}

export const useDocumentStore = create<DocumentState>((set, get) => ({
  documents: [],
  currentDocument: null,
  total: 0,
  page: 1,
  pageSize: 10,
  loading: false,
  filters: {},
  fetchDocuments: async () => {
    set({ loading: true });
    try {
      const { page, pageSize, filters } = get();
      const response = await documentApi.getList({ page, page_size: pageSize, ...filters });
      set({ documents: response.items, total: response.total });
    } finally {
      set({ loading: false });
    }
  },
  fetchDocument: async (id: string) => {
    const document = await documentApi.getById(id);
    set({ currentDocument: document });
  },
  uploadDocument: async (file: File, title?: string) => {
    await documentApi.upload(file, title);
    get().fetchDocuments();
  },
  deleteDocument: async (id: string) => {
    set({ loading: true });
    try {
      await documentApi.delete(id);
    } finally {
      get().fetchDocuments();
    }
  },
  triggerParse: async (id: string) => {
    await documentApi.triggerParse(id);
    get().fetchDocuments();
  },
  setFilters: (filters) => set({ filters: { ...get().filters, ...filters }, page: 1 }),
  setPage: (page) => set({ page }),
}));
