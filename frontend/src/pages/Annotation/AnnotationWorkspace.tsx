import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Tabs, Button, Space, message, Spin } from "antd";
import { SaveOutlined, SendOutlined } from "@ant-design/icons";
import DualPaneView from "./components/DualPaneView";
import EntityExtractor from "./components/EntityExtractor";
import RelationEditor from "./components/RelationEditor";
import AnnotationHistory from "./components/AnnotationHistory";
import CommentPanel from "./components/CommentPanel";
import { annotationApi } from "@api/modules";
import type { Annotation } from "@/types";

export default function AnnotationWorkspace() {
  const { documentId } = useParams<{ documentId: string }>();
  const [selectedElement, setSelectedElement] = useState<any>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // 加载已有标注
  useEffect(() => {
    if (!documentId) return;
    setLoading(true);
    annotationApi
      .getByDocument(documentId)
      .then((res) => {
        const data = Array.isArray(res.data) ? res.data : res;
        setAnnotations(data);
      })
      .catch(() => {
        // 404 等情况，可能是还没有标注
        setAnnotations([]);
      })
      .finally(() => setLoading(false));
  }, [documentId]);

  // 保存所有标注到后端
  const handleSave = async () => {
    const toSave = annotations.filter((a) => a.id.startsWith("temp_"));
    if (toSave.length === 0) {
      message.info("没有新的标注需要保存");
      return;
    }
    setSaving(true);
    try {
      const savedIds: string[] = [];
      for (const annotation of toSave) {
        const res = await annotationApi.create({
          document_id: documentId!,
          element_id: annotation.element_id ?? undefined,
          annotation_type: annotation.annotation_type,
          content: annotation.content,
          confidence: annotation.confidence ?? undefined,
        });
        const saved = res.data?.id || res.id;
        if (saved) savedIds.push({ tempId: annotation.id, realId: saved } as any);
      }
      // 替换临时ID为真实ID
      const updated = annotations.map((a) => {
        const match = (savedIds as any).find((m: any) => m.tempId === a.id);
        return match ? { ...a, id: match.realId } : a;
      });
      setAnnotations(updated);
      message.success(`已保存 ${toSave.length} 条标注`);
    } catch {
      message.error("保存失败，请重试");
    } finally {
      setSaving(false);
    }
  };

  // 提交所有draft状态的标注
  const handleSubmit = async () => {
    const toSubmit = annotations.filter((a) => a.status === "draft" && !a.id.startsWith("temp_"));
    const unsaved = annotations.filter((a) => a.id.startsWith("temp_"));
    if (unsaved.length > 0) {
      message.warning("请先保存新标注再提交");
      return;
    }
    if (toSubmit.length === 0) {
      message.info("没有待提交的标注");
      return;
    }
    setSubmitting(true);
    try {
      let successCount = 0;
      for (const annotation of toSubmit) {
        await annotationApi.submit(annotation.id);
        successCount++;
      }
      // 更新本地状态
      setAnnotations((prev) =>
        prev.map((a) =>
          toSubmit.some((t) => t.id === a.id) ? { ...a, status: "submitted" as const } : a,
        ),
      );
      message.success(`已提交 ${successCount} 条标注审核`);
    } catch {
      message.error("提交失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <Spin style={{ display: "block", margin: "60px auto" }} />;

  const items = [
    {
      key: "entities",
      label: "实体标注",
      children: (
        <EntityExtractor
          annotations={annotations}
          onChange={setAnnotations}
          documentId={documentId!}
        />
      ),
    },
    {
      key: "relations",
      label: "关系标注",
      children: <RelationEditor annotations={annotations} onChange={setAnnotations} />,
    },
    {
      key: "comments",
      label: "评论讨论",
      children: <CommentPanel documentId={documentId!} annotations={annotations} />,
    },
    { key: "history", label: "历史记录", children: <AnnotationHistory documentId={documentId!} /> },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "flex-end" }}>
        <Space>
          <Button icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
            保存
          </Button>
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSubmit}
            loading={submitting}
          >
            提交审核
          </Button>
        </Space>
      </div>
      <DualPaneView
        documentId={documentId!}
        fileUrl={`/api/v1/documents/${documentId}/file`}
        elements={[]}
        selectedElement={selectedElement}
        onElementSelect={setSelectedElement}
        onAnnotationChange={(a) => setAnnotations((prev) => [...prev, a])}
      />
      <Tabs items={items} style={{ marginTop: 16 }} />
    </div>
  );
}
