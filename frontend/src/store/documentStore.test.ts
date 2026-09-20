import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("@api/modules", () => ({
  documentApi: {
    getList: vi.fn(),
    getById: vi.fn(),
    upload: vi.fn(),
    delete: vi.fn(),
    triggerParse: vi.fn(),
  },
}));

import { useDocumentStore } from "./documentStore";
import { documentApi } from "@api/modules";

const mockGetList = documentApi.getList as unknown as ReturnType<typeof vi.fn>;
const mockGetById = documentApi.getById as unknown as ReturnType<typeof vi.fn>;
const mockUpload = documentApi.upload as unknown as ReturnType<typeof vi.fn>;
const mockDelete = documentApi.delete as unknown as ReturnType<typeof vi.fn>;
const mockTriggerParse = documentApi.triggerParse as unknown as ReturnType<typeof vi.fn>;

const resetState = () =>
  useDocumentStore.setState({
    documents: [],
    currentDocument: null,
    total: 0,
    page: 1,
    pageSize: 10,
    loading: false,
    filters: {},
  });

describe("useDocumentStore", () => {
  beforeEach(() => {
    resetState();
    vi.clearAllMocks();
  });

  it("fetchDocuments 拉取并写入列表", async () => {
    mockGetList.mockResolvedValue({
      items: [{ id: "d1", title: "Paper A" }],
      total: 1,
    });

    await useDocumentStore.getState().fetchDocuments();

    expect(mockGetList).toHaveBeenCalledWith({ page: 1, page_size: 10 });
    expect(useDocumentStore.getState().documents).toEqual([{ id: "d1", title: "Paper A" }]);
    expect(useDocumentStore.getState().total).toBe(1);
    expect(useDocumentStore.getState().loading).toBe(false);
  });

  it("fetchDocuments 兼容直接返回 data 的场景", async () => {
    mockGetList.mockResolvedValue({
      data: { items: [{ id: "d2", title: "Paper B" }], total: 1 },
    });

    await useDocumentStore.getState().fetchDocuments();

    expect(useDocumentStore.getState().documents).toEqual([{ id: "d2", title: "Paper B" }]);
  });

  it("fetchDocument 获取详情", async () => {
    mockGetById.mockResolvedValue({ id: "d1", title: "Detail" });

    await useDocumentStore.getState().fetchDocument("d1");

    expect(mockGetById).toHaveBeenCalledWith("d1");
    expect(useDocumentStore.getState().currentDocument).toEqual({
      id: "d1",
      title: "Detail",
    });
  });

  it("setFilters 合并过滤条件并重置页码", () => {
    useDocumentStore.getState().setFilters({ status: "parsed" });
    useDocumentStore.getState().setFilters({ keyword: "perovskite" });

    const state = useDocumentStore.getState();
    expect(state.filters).toEqual({ status: "parsed", keyword: "perovskite" });
    expect(state.page).toBe(1);
  });

  it("setPage 更新页码", () => {
    useDocumentStore.getState().setPage(3);
    expect(useDocumentStore.getState().page).toBe(3);
  });

  it("uploadDocument 上传后刷新列表", async () => {
    mockUpload.mockResolvedValue({ id: "d1" });
    mockGetList.mockResolvedValue({ items: [], total: 0 });

    await useDocumentStore.getState().uploadDocument(new File([], "a.pdf"), "Title");

    expect(mockUpload).toHaveBeenCalled();
    expect(mockGetList).toHaveBeenCalled();
  });

  it("deleteDocument 删除后刷新列表", async () => {
    mockDelete.mockResolvedValue(undefined);
    mockGetList.mockResolvedValue({ items: [], total: 0 });

    await useDocumentStore.getState().deleteDocument("d1");

    expect(mockDelete).toHaveBeenCalledWith("d1");
    expect(mockGetList).toHaveBeenCalled();
  });

  it("triggerParse 触发解析后刷新列表", async () => {
    mockTriggerParse.mockResolvedValue({ task_id: "t1" });
    mockGetList.mockResolvedValue({ items: [], total: 0 });

    await useDocumentStore.getState().triggerParse("d1");

    expect(mockTriggerParse).toHaveBeenCalledWith("d1");
    expect(mockGetList).toHaveBeenCalled();
  });
});
