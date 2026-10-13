import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PaperResult, RepoRecommendation } from "@/types";

const apiHolder = vi.hoisted(() => ({
  recommend: vi.fn(),
  feedback: vi.fn(),
  message: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
}));

vi.mock("antd", async (importOriginal) => {
  const actual: any = await importOriginal();
  return { ...actual, message: apiHolder.message };
});

vi.mock("@api/modules", () => ({
  repoRecommendApi: {
    recommend: apiHolder.recommend,
    feedback: apiHolder.feedback,
  },
}));

import RepoRecommendPanel from "./RepoRecommendPanel";

const mockCandidate: PaperResult = {
  title: "Attention Is All You Need",
  summary: "github.com/hf/transformers",
  authors: ["Vaswani"],
  arxiv_id: "1706.03762",
  published: "2017-06-12",
  source: "arxiv",
};

const mockRec: RepoRecommendation = {
  title: "Attention Is All You Need",
  source: "arxiv",
  arxiv_id: "1706.03762",
  open_source: true,
  repos: [
    {
      repo: "hf/transformers",
      html_url: "https://github.com/hf/transformers",
      source: "online",
      star_count: 167636,
      license: "Apache-2.0",
      latest_push: null,
      open_issues: null,
      updated_at: null,
    },
  ],
  correlation_score: 0.9,
  reproducibility_score: 0.8,
  feedback_score: 0.5,
  feedback_net: 0,
  total_score: 1.3,
  reason: "相关且含开源实现",
};

beforeAll(() => {
  Object.defineProperty(Element.prototype, "scrollIntoView", {
    writable: true,
    value: () => {},
  });
});

describe("RepoRecommendPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiHolder.recommend.mockResolvedValue({
      backend: "builtin",
      github_online: true,
      count: 1,
      recommendations: [mockRec],
      records: [],
    });
    apiHolder.feedback.mockResolvedValue({
      ok: true,
      feedback: { repo: "hf/transformers", sentiment: "like" },
    });
  });

  it("点击生成复现性推荐：调用 recommend（空库）并渲染开源可复现标识与在线提示", async () => {
    render(<RepoRecommendPanel candidates={[mockCandidate]} localRefsRaw="" />);
    await userEvent.click(screen.getByRole("button", { name: /生成复现性推荐/ }));

    expect(apiHolder.recommend).toHaveBeenCalledWith({
      local_references: [],
      candidates: [mockCandidate],
    });
    expect(await screen.findByText(/已连接 GitHub REST API/)).toBeInTheDocument();
    expect(screen.getByText(/复现性优先推荐/)).toBeInTheDocument();
  });

  it("localRefsRaw 为合法 JSON 时透传为 local_references", async () => {
    const refs = JSON.stringify([{ title: "Transformer", journal: "NIPS" }]);
    render(<RepoRecommendPanel candidates={[mockCandidate]} localRefsRaw={refs} />);
    await userEvent.click(screen.getByRole("button", { name: /生成复现性推荐/ }));
    expect(apiHolder.recommend).toHaveBeenCalledWith({
      local_references: [{ title: "Transformer", journal: "NIPS" }],
      candidates: [mockCandidate],
    });
  });

  it("展示真实 star 与 license", async () => {
    render(<RepoRecommendPanel candidates={[mockCandidate]} localRefsRaw="" />);
    await userEvent.click(screen.getByRole("button", { name: /生成复现性推荐/ }));
    expect(await screen.findByText(/hf\/transformers ⭐167636 · Apache-2.0/)).toBeInTheDocument();
  });

  it("github_online=false 时显示离线降级警告且不编造 star", async () => {
    apiHolder.recommend.mockResolvedValue({
      backend: "builtin",
      github_online: false,
      count: 1,
      recommendations: [
        {
          ...mockRec,
          repos: [
            {
              repo: "hf/transformers",
              html_url: "https://github.com/hf/transformers",
              source: "offline",
              star_count: null,
              license: null,
            },
          ],
        },
      ],
      records: [],
    });
    render(<RepoRecommendPanel candidates={[mockCandidate]} localRefsRaw="" />);
    await userEvent.click(screen.getByRole("button", { name: /生成复现性推荐/ }));
    expect(await screen.findByText(/离线，不编造 star/)).toBeInTheDocument();
    expect(screen.getByText(/已降级为离线标注，不编造 star 数/)).toBeInTheDocument();
  });

  it("点击「赞」调用 feedback 并持久化", async () => {
    render(<RepoRecommendPanel candidates={[mockCandidate]} localRefsRaw="" />);
    await userEvent.click(screen.getByRole("button", { name: /生成复现性推荐/ }));
    await userEvent.click(await screen.findByRole("button", { name: /赞/ }));

    expect(apiHolder.feedback).toHaveBeenCalledWith({ repo: "hf/transformers", sentiment: "like" });
    expect(apiHolder.message.success).toHaveBeenCalled();
  });

  it("candidates 为空时提示无需请求接口", async () => {
    render(<RepoRecommendPanel candidates={[]} localRefsRaw="" />);
    await userEvent.click(screen.getByRole("button", { name: /生成复现性推荐/ }));
    expect(apiHolder.recommend).not.toHaveBeenCalled();
    expect(apiHolder.message.warning).toHaveBeenCalled();
  });
});
