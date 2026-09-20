import { useState } from "react";
import {
  Table,
  Tag,
  Input,
  Select,
  InputNumber,
  Space,
  Button,
  Popconfirm,
  Typography,
} from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import type { Annotation } from "@/types";

const { Text } = Typography;

const ENTITY_TYPES = [
  { value: "Material", label: "材料类", color: "blue" },
  { value: "Property", label: "性能类", color: "green" },
  { value: "Method", label: "方法类", color: "orange" },
  { value: "Parameter", label: "参数类", color: "purple" },
  { value: "Result", label: "结果类", color: "red" },
];

const typeColorMap: Record<string, string> = Object.fromEntries(
  ENTITY_TYPES.map((t) => [t.value, t.color]),
);

interface EntityExtractorProps {
  annotations: Annotation[];
  onChange: (annotations: Annotation[]) => void;
  documentId: string;
}

export default function EntityExtractor({
  annotations,
  onChange,
  documentId,
}: EntityExtractorProps) {
  const [newText, setNewText] = useState("");
  const [newType, setNewType] = useState<string | undefined>(undefined);
  const [newConfidence, setNewConfidence] = useState<number>(0.85);

  const nerAnnotations = annotations.filter((a) => a.annotation_type === "ner");
  const [filterType, setFilterType] = useState<string | null>(null);

  const filtered = filterType
    ? nerAnnotations.filter((a) => a.content?.entity_type === filterType)
    : nerAnnotations;

  const handleAdd = () => {
    if (!newText.trim() || !newType) return;
    const newAnnotation: Annotation = {
      id: `temp_${Date.now()}`,
      document_id: documentId,
      element_id: null,
      annotation_type: "ner",
      content: { text: newText.trim(), entity_type: newType },
      confidence: newConfidence,
      status: "draft",
      annotated_by: "",
      first_reviewed_by: null,
      first_review_comment: null,
      first_reviewed_at: null,
      final_reviewed_by: null,
      final_review_comment: null,
      final_reviewed_at: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    onChange([...annotations, newAnnotation]);
    setNewText("");
    setNewType(undefined);
    setNewConfidence(0.85);
  };

  const handleDelete = (id: string) => {
    onChange(annotations.filter((a) => a.id !== id));
  };

  const columns = [
    {
      title: "实体文本",
      dataIndex: ["content", "text"],
      key: "text",
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: "实体类型",
      dataIndex: ["content", "entity_type"],
      key: "entity_type",
      render: (type: string) => (
        <Tag color={typeColorMap[type] || "default"}>
          {ENTITY_TYPES.find((t) => t.value === type)?.label || type}
        </Tag>
      ),
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      key: "confidence",
      width: 100,
      render: (v: number | null) => (v != null ? `${(v * 100).toFixed(0)}%` : "-"),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 80,
      render: (s: string) => {
        const map: Record<string, { color: string; text: string }> = {
          draft: { color: "default", text: "草稿" },
          submitted: { color: "processing", text: "待审" },
          approved: { color: "success", text: "通过" },
          rejected: { color: "error", text: "驳回" },
        };
        const info = map[s] || { color: "default", text: s };
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    {
      title: "操作",
      key: "action",
      width: 70,
      render: (_: any, record: Annotation) => (
        <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
          <Button type="link" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      {/* 筛选栏 */}
      <Space style={{ marginBottom: 12 }} wrap>
        <Text type="secondary">筛选：</Text>
        <Tag.CheckableTag checked={filterType === null} onChange={() => setFilterType(null)}>
          全部 ({nerAnnotations.length})
        </Tag.CheckableTag>
        {ENTITY_TYPES.map((t) => {
          const count = nerAnnotations.filter((a) => a.content?.entity_type === t.value).length;
          return (
            <Tag.CheckableTag
              key={t.value}
              checked={filterType === t.value}
              onChange={() => setFilterType(filterType === t.value ? null : t.value)}
            >
              {t.label} ({count})
            </Tag.CheckableTag>
          );
        })}
      </Space>

      {/* 新增实体 */}
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="实体文本"
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          style={{ width: 180 }}
          onPressEnter={handleAdd}
        />
        <Select
          placeholder="实体类型"
          value={newType}
          onChange={setNewType}
          style={{ width: 130 }}
          options={ENTITY_TYPES.map((t) => ({ value: t.value, label: t.label }))}
        />
        <InputNumber
          placeholder="置信度"
          value={newConfidence}
          onChange={(v) => setNewConfidence(v || 0.85)}
          min={0}
          max={1}
          step={0.05}
          style={{ width: 100 }}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加
        </Button>
      </Space>

      {/* 实体列表 */}
      <Table
        dataSource={filtered}
        columns={columns}
        rowKey="id"
        size="small"
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: "暂无实体标注，请在上方添加" }}
      />
    </div>
  );
}
