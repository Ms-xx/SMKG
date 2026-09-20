import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { message } from "antd";
import CommentPanel from "./CommentPanel";
import { commentApi, userApi } from "@api/modules";
import { useAuthStore } from "@store/authStore";

vi.mock("@api/modules", () => ({
  commentApi: { create: vi.fn(), list: vi.fn(), remove: vi.fn() },
  userApi: { mentionable: vi.fn() },
}));

const annotation = {
  id: "a1",
  document_id: "d1",
  annotation_type: "ner",
  content: { text: "钛酸钡", entity_type: "Material" },
} as any;

const comment = {
  id: "c1",
  annotation_id: "a1",
  user_id: "u1",
  username: "alice",
  full_name: "张三",
  content: "hi @bob 看看这条",
  mentions: ["bob"],
  created_at: "2026-01-01T10:00:00",
  updated_at: "2026-01-01T10:00:00",
} as any;

describe("CommentPanel", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: { id: "u1", username: "alice" } } as any);
    vi.mocked(commentApi.list)
      .mockReset()
      .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    vi.mocked(commentApi.create)
      .mockReset()
      .mockResolvedValue({} as any);
    vi.mocked(commentApi.remove).mockReset().mockResolvedValue({});
    vi.mocked(userApi.mentionable)
      .mockReset()
      .mockResolvedValue([{ id: "u2", username: "bob", full_name: "李四" }]);
  });

  afterEach(() => {
    message.destroy();
  });

  it("空评论显示空态", async () => {
    render(<CommentPanel documentId="d1" annotations={[]} />);
    expect(await screen.findByText("暂无评论")).toBeInTheDocument();
    expect(screen.getByText("评论讨论（0）")).toBeInTheDocument();
  });

  it("渲染评论列表与提及高亮", async () => {
    vi.mocked(commentApi.list).mockResolvedValue({
      items: [comment],
      total: 1,
      page: 1,
      page_size: 20,
    });
    render(<CommentPanel documentId="d1" annotations={[annotation]} />);
    expect(await screen.findByText("评论讨论（1）")).toBeInTheDocument();
    expect(screen.getByText("张三")).toBeInTheDocument();
    expect(screen.getByText("@bob")).toBeInTheDocument();
    expect(screen.getByText(/针对：实体标注/)).toBeInTheDocument();
  });

  it("提交空内容时提示", async () => {
    render(<CommentPanel documentId="d1" annotations={[]} />);
    fireEvent.click(await screen.findByText("发表评论"));
    expect(await screen.findByText("请输入评论内容")).toBeInTheDocument();
  });

  it("有标注但未选择时提示选择标注", async () => {
    render(<CommentPanel documentId="d1" annotations={[annotation]} />);
    fireEvent.change(screen.getByPlaceholderText("输入评论，可 @用户名 提及成员..."), {
      target: { value: "内容" },
    });
    fireEvent.click(screen.getByText("发表评论"));
    expect(await screen.findByText("请选择要评论的标注")).toBeInTheDocument();
  });

  it("删除自己的评论", async () => {
    vi.mocked(commentApi.list).mockResolvedValue({
      items: [comment],
      total: 1,
      page: 1,
      page_size: 20,
    });
    render(<CommentPanel documentId="d1" annotations={[annotation]} />);
    await screen.findByText("张三");
    const deleteBtn = document.querySelector(".ant-btn-dangerous");
    expect(deleteBtn).toBeTruthy();
    fireEvent.click(deleteBtn!);
    fireEvent.click(await screen.findByText("OK"));
    await waitFor(() => expect(vi.mocked(commentApi.remove)).toHaveBeenCalledWith("c1"));
    expect(await screen.findByText("评论已删除")).toBeInTheDocument();
  });
});
