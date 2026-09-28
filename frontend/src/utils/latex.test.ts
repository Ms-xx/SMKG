import { describe, it, expect } from "vitest";
import { formulaDirectionLabel, toLatexBody, wrapLatex } from "./latex";

describe("toLatexBody", () => {
  it("剥离各种定界符", () => {
    expect(toLatexBody("$$E=mc^{2}$$")).toBe("E=mc^{2}");
    expect(toLatexBody("$E=mc^{2}$")).toBe("E=mc^{2}");
    expect(toLatexBody("\\[E=mc^{2}\\]")).toBe("E=mc^{2}");
    expect(toLatexBody("\\(a_i\\)")).toBe("a_i");
    expect(toLatexBody("E=mc^{2}")).toBe("E=mc^{2}");
  });

  it("剥离数学环境", () => {
    expect(toLatexBody("\\begin{equation}x+y=z\\end{equation}")).toBe("x+y=z");
    expect(toLatexBody("\\begin{align*}a&=b\\end{align*}")).toBe("a&=b");
  });

  it("处理 pix2tex 多重残留", () => {
    expect(toLatexBody("[[START_SOLUTION]]\\[E=mc^{2}\\]$$")).toBe("E=mc^{2}");
  });

  it("空值与异常入参安全返回空串", () => {
    expect(toLatexBody("")).toBe("");
    expect(toLatexBody(null)).toBe("");
    expect(toLatexBody(undefined)).toBe("");
    expect(toLatexBody("   ")).toBe("");
  });
});

describe("wrapLatex", () => {
  it("按方向加统一定界符", () => {
    expect(wrapLatex("E=mc^{2}", true)).toBe("$$E=mc^{2}$$");
    expect(wrapLatex("a_i", false)).toBe("$a_i$");
    expect(wrapLatex("", true)).toBe("");
  });
});

describe("formulaDirectionLabel", () => {
  it("返回统一术语", () => {
    expect(formulaDirectionLabel(true)).toBe("行间公式");
    expect(formulaDirectionLabel(false)).toBe("行内公式");
  });
});
