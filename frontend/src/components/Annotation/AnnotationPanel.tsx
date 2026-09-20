import { List, Tag, Typography } from "antd";

interface AnnotationPanelProps {
  elements: any[];
  selectedElement: any | null;
  onElementSelect: (element: any) => void;
  onAnnotationChange: (annotation: any) => void;
}

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
        renderItem={(item: any) => (
          <List.Item
            style={{
              cursor: "pointer",
              background: selectedElement?.id === item.id ? "#e6f7ff" : "transparent",
            }}
            onClick={() => onElementSelect(item)}
          >
            <Tag
              color={
                item.element_type === "heading"
                  ? "blue"
                  : item.element_type === "table"
                    ? "green"
                    : item.element_type === "formula"
                      ? "orange"
                      : "default"
              }
            >
              {item.element_type}
            </Tag>
            <Typography.Text ellipsis style={{ maxWidth: 200 }}>
              {item.content || "[无文本内容]"}
            </Typography.Text>
          </List.Item>
        )}
      />
    </div>
  );
}
