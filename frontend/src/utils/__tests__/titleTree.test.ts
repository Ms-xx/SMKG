import { describe, expect, it } from "vitest";

import type { TitleTreeItem } from "@/types";

import { buildTitleTree } from "../titleTree";

const item = (level: number, title: string, page_number: number): TitleTreeItem => ({
  level,
  title,
  page_number,
});

describe("buildTitleTree", () => {
  it("空数组返回空树", () => {
    expect(buildTitleTree([])).toEqual([]);
  });

  it("单层：全部为根节点", () => {
    const flat = [item(1, "引言", 1), item(1, "方法", 2), item(1, "结论", 3)];
    const tree = buildTitleTree(flat);
    expect(tree.map((n) => n.title)).toEqual(["引言", "方法", "结论"]);
    expect(tree.every((n) => n.children.length === 0)).toBe(true);
  });

  it("多层嵌套：子级挂到最近父级", () => {
    const flat = [
      item(1, "方法", 2),
      item(2, "数据集", 2),
      item(2, "模型", 3),
      item(3, "损失函数", 3),
      item(1, "结论", 4),
    ];
    const tree = buildTitleTree(flat);
    expect(tree.length).toBe(2);
    expect(tree[0].title).toBe("方法");
    expect(tree[0].children.length).toBe(2);
    expect(tree[0].children[0].title).toBe("数据集");
    expect(tree[0].children[0].children.length).toBe(0);
    expect(tree[0].children[1].title).toBe("模型");
    expect(tree[0].children[1].children[0].title).toBe("损失函数");
    expect(tree[1].title).toBe("结论");
  });

  it("层级跳跃（1→3）：挂到最近合法父级，不插入伪节点", () => {
    const flat = [item(1, "方法", 2), item(3, "深度细节", 3)];
    const tree = buildTitleTree(flat);
    expect(tree.length).toBe(1);
    expect(tree[0].title).toBe("方法");
    expect(tree[0].children.length).toBe(1);
    expect(tree[0].children[0].title).toBe("深度细节");
    expect(tree[0].children[0].children).toEqual([]);
  });

  it("key 稳定唯一，page+level 相同也能区分", () => {
    const flat = [item(2, "小节A", 1), item(2, "小节B", 1)];
    const tree = buildTitleTree(flat);
    const keys = tree.map((n) => n.key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(tree[0].page).toBe(1);
    expect(tree[1].page).toBe(1);
  });

  it("同行更深（1→2→3）逐级折叠", () => {
    const flat = [item(1, "A", 1), item(2, "A1", 1), item(3, "A1a", 1)];
    const tree = buildTitleTree(flat);
    expect(tree[0].title).toBe("A");
    expect(tree[0].children[0].title).toBe("A1");
    expect(tree[0].children[0].children[0].title).toBe("A1a");
  });
});
