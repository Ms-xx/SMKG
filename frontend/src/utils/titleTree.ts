import type { TitleTreeItem } from "@/types";

export interface TitleTreeNode {
  title: string;
  key: string;
  page: number;
  children: TitleTreeNode[];
}

/**
 * 把扁平的 title 元素列表（level/title/page，已按页位置有序）折叠成嵌套树。
 *
 * 采用栈折叠，key 为稳定唯一值 ``p{page}-{level}-{index}``。
 * 层级跳级时（如 1→3）直接挂到最近合法父级，不插入伪占位节点。
 */
export function buildTitleTree(flat: TitleTreeItem[]): TitleTreeNode[] {
  const roots: TitleTreeNode[] = [];
  const stack: { level: number; node: TitleTreeNode }[] = [];

  flat.forEach((item, index) => {
    const level = Number.isFinite(item.level) ? item.level : 3;
    const node: TitleTreeNode = {
      title: item.title,
      key: `p${item.page_number}-${level}-${index}`,
      page: item.page_number,
      children: [],
    };
    while (stack.length && stack[stack.length - 1].level >= level) {
      stack.pop();
    }
    const parent = stack[stack.length - 1];
    if (parent) {
      parent.node.children.push(node);
    } else {
      roots.push(node);
    }
    stack.push({ level, node });
  });

  return roots;
}
