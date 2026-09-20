import { useState } from "react";
import { Table, Select, Input, Space, Button, Popconfirm, Tag, Card, Typography } from "antd";
import { PlusOutlined, DeleteOutlined, ArrowRightOutlined } from "@ant-design/icons";
import type { Annotation } from "@/types";

const { TextArea } = Input;

const RELATION_TYPES = [
  { value: "HAS_PROPERTY", label: "具有性能", color: "blue" },
  { value: "PRODUCED_BY", label: "由...制备", color: "green" },
  { value: "IMPROVES", label: "改善", color: "orange" },
  { value: "CORRELATES_WITH", label: "相关于", color: "purple" },
];

const relationColorMap: Record<string, string> = Object.fromEntries(
  RELATION_TYPES.map((t) => [t.value, t.color]),
);

interface RelationEditorProps {
  annotations: Annotation[];
  onChange: (annotations: Annotation[]) => void;
}

export default function RelationEditor({ annotations, onChange }: RelationEditorProps) {
  const [newSourceType, setNewSourceType] = useState<string | undefined>(undefined);
  const [newRelationType, setNewRelationType] = useState<string | undefined>(undefined);
  const [newTargetType, setNewTargetType] = useState<string | undefined>(undefined);
  const [newContext, setNewContext] = useState("");

  const nerAnnotations = annotations.filter((a) => a.annotation_type === "ner");
  const relationAnnotations = annotations.filter((a) => a.annotation_type === "relation");
  const [filterType, setFilterType] = useState<string | null>(null);

  const filtered = filterType
    ? relationAnnotations.filter((a) => a.content?.relation_type === filterType)
    : relationAnnotations;

  // 从NER标注中构建实体选项列表
  const entityOptions = nerAnnotations.map((a) => ({
    value: a.id,
    label: `${a.content?.text || "未知"} (${a.content?.entity_type || "?"})`,
    text: a.content?.text || "",
    entityType: a.content?.entity_type || "",
  }));

  const handleAdd = () => {
    if (!newSourceType || !newRelationType || !newTargetType) return;
    const source = entityOptions.find((e) => e.value === newSourceType);
    const target = entityOptions.find((e) => e.value === newTargetType);
    if (!source || !target) return;

    const newAnnotation: Annotation = {
      id: `temp_${Date.now()}`,
      document_id: annotations[0]?.document_id || "",
      element_id: null,
      annotation_type: "relation",
      content: {
        source: source.text,
        source_type: source.entityType,
        target: target.text,
        target_type: target.entityType,
        relation_type: newRelationType,
        context: newContext.trim() || undefined,
      },
      confidence: 0.7,
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
    setNewSourceType(undefined);
    setNewRelationType(undefined);
    setNewTargetType(undefined);
    setNewContext("");
  };

  const handleDelete = (id: string) => {
    onChange(annotations.filter((a) => a.id !== id));
  };

  const columns = [
    {
      title: "关系",
      key: "relation",
      render: (_: any, record: Annotation) => {
        const c = record.content;
        return (
          <Space size={4}>
            <Tag color="blue">{c?.source}</Tag>
            <ArrowRightOutlined style={{ color: "#999" }} />
            <Tag color={relationColorMap[c?.relation_type] || "default"}>
              {RELATION_TYPES.find((t) => t.value === c?.relation_type)?.label || c?.relation_type}
            </Tag>
            <ArrowRightOutlined style={{ color: "#999" }} />
            <Tag color="green">{c?.target}</Tag>
          </Space>
        );
      },
    },
    {
      title: "上下文",
      dataIndex: ["content", "context"],
      key: "context",
      ellipsis: true,
      render: (t: string) => t || "-",
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      key: "confidence",
      width: 80,
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
        <Typography.Text type="secondary">筛选：</Typography.Text>
        <Tag.CheckableTag checked={filterType === null} onChange={() => setFilterType(null)}>
          全部 ({relationAnnotations.length})
        </Tag.CheckableTag>
        {RELATION_TYPES.map((t) => {
          const count = relationAnnotations.filter(
            (a) => a.content?.relation_type === t.value,
          ).length;
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

      {/* 新增关系 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Typography.Text strong>新建关系</Typography.Text>
          <Space wrap>
            <Select
              placeholder="源实体"
              value={newSourceType}
              onChange={setNewSourceType}
              style={{ width: 200 }}
              options={entityOptions}
              showSearch
              optionFilterProp="label"
              notFoundContent="请先在实体标注中添加实体"
            />
            <Select
              placeholder="关系类型"
              value={newRelationType}
              onChange={setNewRelationType}
              style={{ width: 140 }}
              options={RELATION_TYPES.map((t) => ({ value: t.value, label: t.label }))}
            />
            <Select
              placeholder="目标实体"
              value={newTargetType}
              onChange={setNewTargetType}
              style={{ width: 200 }}
              options={entityOptions}
              showSearch
              optionFilterProp="label"
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleAdd}
              disabled={!newSourceType || !newRelationType || !newTargetType}
            >
              添加
            </Button>
          </Space>
          <TextArea
            placeholder="上下文（可选，如：钙钛矿具有高光电转换效率）"
            value={newContext}
            onChange={(e) => setNewContext(e.target.value)}
            rows={2}
            style={{ maxWidth: 600 }}
          />
        </Space>
      </Card>

      {/* 关系列表 */}
      <Table
        dataSource={filtered}
        columns={columns}
        rowKey="id"
        size="small"
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: "暂无关系标注，请先在实体标注Tab中添加实体后创建关系" }}
      />
    </div>
  );
}
