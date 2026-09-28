import { List, Tag, Typography } from "antd";
import LatexFormula from "../Formula/LatexFormula";

interface AnnotationPanelProps {
  elements: any[];
  selectedElement: any | null;
  onElementSelect: (element: any) => void;
  onAnnotationChange: (annotation: any) => void;
}

/** 元素类型 → 标签颜色（公式单独标色，便于在列表中区分）。 */
const TYPE_COLORS: Record<string, string> = {
  heading: "blue",
  title: "blue",
  table: "green",
  formula: "orange",
};

export default function AnnotationPanel({
  elements,
  selectedElement,
  onElementSelect,
}: AnnotationPanelProps) {
  return (
    <div style={{ padding: 16, overflow: "auto", height: "100%" }}>
      <Typography.Title level={5}>解析元素</Typography.Title>
      <List
        dataSource={elements}
        renderItem={(item: any) => {
          const isFormula = item.element_type === "formula";
          return (
            <List.Item
              style={{
                cursor: "pointer",
                background: selectedElement?.id === item.id ? "#e6f7ff" : "transparent",
              }}
              onClick={() => onElementSelect(item)}
            >
              <Tag color={TYPE_COLORS[item.element_type] || "default"}>{item.element_type}</Tag>
              {isFormula ? (
                // 公式统一走 LaTeX 渲染（行内/行间、编号、复制与降级由组件负责）
                <LatexFormula
                  latex={item.latex ?? item.content}
                  display={item.is_display ?? true}
                  number={item.formula_number ?? null}
                  normalized={item.formula_normalized ?? null}
                />
              ) : (
                <Typography.Text ellipsis style={{ maxWidth: 200 }}>
                  {item.content || "[无文本内容]"}
                </Typography.Text>
              )}
            </List.Item>
          );
        }}
      />
    </div>
  );
}
