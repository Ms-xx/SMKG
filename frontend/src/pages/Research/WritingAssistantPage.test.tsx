import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const apiHolder = vi.hoisted(() => ({
  translate: vi.fn(),
  llmGenerate: vi.fn(),
}));

// antd 的 message 使用 ref 渲染，jsdom 下难以直接断言；
// 参照项目既有约定 mock antd 的 message，其余 antd 组件保持原样。
vi.mock("antd", async (importOriginal) => {
  const actual: any = await importOriginal();
  return {
    ...actual,
    message: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
  };
});

vi.mock("@api/modules", () => ({
  writingAssistantApi: { translate: apiHolder.translate, llmGenerate: apiHolder.llmGenerate },
}));

import WritingAssistantPage from "./WritingAssistantPage";

describe("WritingAssistantPage", () => {
  beforeAll(() => {
    // jsdom 未实现 Element.scrollIntoView
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      writable: true,
      value: () => {},
    });
  });

  beforeEach(() => {
    vi.clearAllMocks();
    apiHolder.translate.mockResolvedValue({
      backend: "mock",
      text: "翻译后的中文内容",
      target: "zh",
    });
    apiHolder.llmGenerate.mockResolvedValue({
      backend: "mock",
      content: "LLM 生成的内容",
    });
  });

  it("渲染「翻译」按钮与「LLM 生成」按钮", () => {
    render(
      <MemoryRouter>
        <WritingAssistantPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("中英翻译 + LLM 生成")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /翻\s*译/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /LLM\s*生\s*成/ })).toBeInTheDocument();
  });

  it("点击翻译后调用 translate 并展示返回 text", async () => {
    render(
      <MemoryRouter>
        <WritingAssistantPage />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("button", { name: /翻\s*译/ }));

    expect(await screen.findByText("翻译后的中文内容")).toBeInTheDocument();
    expect(apiHolder.translate).toHaveBeenCalledWith({
      text: "Graph neural networks enable materials property prediction.",
      target: "zh",
    });
  });

  it("点击 LLM 生成后调用 llmGenerate 并展示 content", async () => {
    render(
      <MemoryRouter>
        <WritingAssistantPage />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("button", { name: /LLM\s*生\s*成/ }));

    expect(await screen.findByText("LLM 生成的内容")).toBeInTheDocument();
    expect(apiHolder.llmGenerate).toHaveBeenCalledWith({
      prompt: "写一段关于能源材料研究的中文学术引言。",
    });
  });
});