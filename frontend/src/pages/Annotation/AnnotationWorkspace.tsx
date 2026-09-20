import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { Tabs, Button, Space, message, Spin, Badge } from "antd";
import { SaveOutlined, SendOutlined } from "@ant-design/icons";
import DualPaneView from "./components/DualPaneView";
import EntityExtractor from "./components/EntityExtractor";
import RelationEditor from "./components/RelationEditor";
import AnnotationHistory from "./components/AnnotationHistory";
import CommentPanel from "./components/CommentPanel";
import { annotationApi } from "@api/modules";
import { buildAnnotationWsUrl } from "@api/ws";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAuthStore } from "@/store/authStore";
import type { Annotation } from "@/types";

export default function AnnotationWorkspace() {
  const { documentId } = useParams<{ documentId: string }>();
  const [selectedElement, setSelectedElement] = useState<any>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // ── 实时协作：WebSocket 订阅文档频道，接收他人标注变更并实时同步 ──
  const meId = useAuthStore((s) => s.user?.id);
  const [onlineUsers, setOnlineUsers] = useState<string[]>([]);

  const applyRemoteAnnotation = useCallback((incoming: Annotation) => {
    setAnnotations((prev) => {
      const exists = prev.some((a) => a.id === incoming.id);
      if (exists) {
        return prev.map((a) => (a.id === incoming.id ? incoming : a));
      }
      return [...prev, incoming];
    });
  }, []);

  const handleWsMessage = useCallback(
    (data: any) => {
      const type: string | undefined = data?.type;
      const ann = data?.annotation as Annotation | undefined;
      const actorId = data?.user_id as string | undefined;
      const annId = data?.annotation_id as string | undefined;
      switch (type) {
        case "subscribed":
          setOnlineUsers(data?.online_users || []);
          break;
        case "presence.joined":
          if (actorId && actorId !== meId) {
            setOnlineUsers((prev) => (prev.includes(actorId) ? prev : [...prev, actorId]));
          }
          break;
        case "presence.left":
          setOnlineUsers((prev) => prev.filter((id) => id !== actorId));
          break;
        case "annotation.created":
          if (ann && actorId !== meId) {
            applyRemoteAnnotation(ann);
            message.info("收到他人的新标注");
          }
          break;
        case "annotation.updated":
          if (ann) {
            applyRemoteAnnotation(ann);
            if (actorId !== meId) message.info("标注已被他人更新");
          }
          break;
        case "annotation.submitted":
        case "annotation.reviewed":
          if (ann) applyRemoteAnnotation(ann);
          break;
        case "annotation.deleted":
          if (annId) setAnnotations((prev) => prev.filter((a) => a.id !== annId));
          break;
        case "annotation.locked":
          if (actorId !== meId) message.info("标注已被他人锁定");
          break;
        case "annotation.unlocked":
          if (actorId !== meId) message.info("标注已解锁");
          break;
        default:
          break;
      }
    },
    [meId, applyRemoteAnnotation],
  );

  const { isConnected } = useWebSocket({
    url: documentId ? buildAnnotationWsUrl(documentId) : "",
    onMessage: handleWsMessage,
  });

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
      <div
        style={{
          marginBottom: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Badge
          status={isConnected ? "success" : "default"}
          text={
            isConnected
              ? `实时协作已连接（${Math.max(0, onlineUsers.length - 1)} 位协作者）`
              : "实时协作未连接"
          }
        />
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
