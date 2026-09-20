import { useEffect, useState } from "react";
import { Tag, Spin, Empty, Typography, Collapse, Descriptions, Space } from "antd";
import {
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { annotationApi } from "@api/modules";
import type { Annotation } from "@/types";
import dayjs from "dayjs";

const { Text } = Typography;

const statusIconMap: Record<string, React.ReactNode> = {
  draft: <EditOutlined style={{ color: "#999" }} />,
  submitted: <SendOutlined style={{ color: "#1890ff" }} />,
  approved: <CheckCircleOutlined style={{ color: "#52c41a" }} />,
  rejected: <CloseCircleOutlined style={{ color: "#ff4d4f" }} />,
};

const statusColorMap: Record<string, string> = {
  draft: "gray",
  submitted: "blue",
  approved: "green",
  rejected: "red",
};

const typeLabelMap: Record<string, string> = {
  ner: "实体标注",
  relation: "关系标注",
  correction: "纠错标注",
};

function AnnotationContent({ annotation }: { annotation: Annotation }) {
  const content = annotation.content;

  if (annotation.annotation_type === "ner") {
    return (
      <Descriptions size="small" column={1} style={{ marginTop: 8 }}>
        <Descriptions.Item label="实体文本">{content?.text}</Descriptions.Item>
        <Descriptions.Item label="实体类型">{content?.entity_type}</Descriptions.Item>
        {content?.start != null && (
          <Descriptions.Item label="位置">
            {content.start} - {content.end}
          </Descriptions.Item>
        )}
        <Descriptions.Item label="置信度">
          {annotation.confidence != null ? `${(annotation.confidence * 100).toFixed(0)}%` : "-"}
        </Descriptions.Item>
      </Descriptions>
    );
  }

  if (annotation.annotation_type === "relation") {
    return (
      <Descriptions size="small" column={1} style={{ marginTop: 8 }}>
        <Descriptions.Item label="源实体">
          {content?.source} ({content?.source_type})
        </Descriptions.Item>
        <Descriptions.Item label="关系类型">{content?.relation_type}</Descriptions.Item>
        <Descriptions.Item label="目标实体">
          {content?.target} ({content?.target_type})
        </Descriptions.Item>
        {content?.context && (
          <Descriptions.Item label="上下文">{content.context}</Descriptions.Item>
        )}
        <Descriptions.Item label="置信度">
          {annotation.confidence != null ? `${(annotation.confidence * 100).toFixed(0)}%` : "-"}
        </Descriptions.Item>
      </Descriptions>
    );
  }

  return <Text type="secondary">纠错内容：{JSON.stringify(content)}</Text>;
}

export default function AnnotationHistory({ documentId }: { documentId: string }) {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    annotationApi
      .getByDocument(documentId)
      .then((res) => {
        setAnnotations(Array.isArray(res.data) ? res.data : res);
      })
      .catch((err) => setError(err.message || "加载失败"))
      .finally(() => setLoading(false));
  }, [documentId]);

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Empty description={error} />;

  if (annotations.length === 0) {
    return <Empty description="暂无标注历史记录" style={{ marginTop: 40 }} />;
  }

  const items = annotations.map((a) => ({
    key: a.id,
    label: (
      <Space>
        {statusIconMap[a.status] || <ClockCircleOutlined />}
        <Tag color={statusColorMap[a.status] || "default"}>
          {a.status === "draft"
            ? "草稿"
            : a.status === "submitted"
              ? "已提交"
              : a.status === "approved"
                ? "已通过"
                : "已驳回"}
        </Tag>
        <Text>{typeLabelMap[a.annotation_type] || a.annotation_type}</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {dayjs(a.created_at).format("MM-DD HH:mm")}
        </Text>
      </Space>
    ),
    children: <AnnotationContent annotation={a} />,
  }));

  return (
    <div style={{ padding: 16 }}>
      <Typography.Title level={5} style={{ marginBottom: 16 }}>
        标注历史（共 {annotations.length} 条）
      </Typography.Title>
      <Collapse items={items} accordion />
    </div>
  );
}
