import { useEffect, useState, useCallback } from "react";
import {
  List,
  Input,
  Button,
  Select,
  Space,
  Empty,
  Typography,
  Tag,
  message,
  Spin,
  Avatar,
  Popconfirm,
} from "antd";
import { SendOutlined, DeleteOutlined, UserOutlined } from "@ant-design/icons";
import { commentApi, userApi } from "@api/modules";
import { useAuthStore } from "@store/authStore";
import type { Annotation, AnnotationComment } from "@/types";
import dayjs from "dayjs";

const { Text } = Typography;
const { TextArea } = Input;

const typeLabelMap: Record<string, string> = {
  ner: "实体标注",
  relation: "关系标注",
  correction: "纠错标注",
};

function annotationLabel(a: Annotation) {
  const type = typeLabelMap[a.annotation_type] || a.annotation_type;
  const snippet = typeof a.content?.text === "string" ? a.content.text : "";
  return snippet ? `${type} · ${snippet}` : `${type} · ${a.id.slice(0, 8)}`;
}

// 高亮评论中的 @提及
function renderContent(text: string) {
  const parts = text.split(/(@[\w\u4e00-\u9fa5.-]+)/g);
  return parts.map((part, i) =>
    part.startsWith("@") ? (
      <Text key={i} type="success" strong>
        {part}
      </Text>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

interface CommentPanelProps {
  documentId: string;
  annotations: Annotation[];
}

export default function CommentPanel({ documentId, annotations }: CommentPanelProps) {
  const [comments, setComments] = useState<AnnotationComment[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [content, setContent] = useState("");
  const [targetAnnotationId, setTargetAnnotationId] = useState<string | undefined>(undefined);
  const [mentionable, setMentionable] = useState<
    { id: string; username: string; full_name?: string }[]
  >([]);
  const user = useAuthStore((s) => s.user);

  const fetchComments = useCallback(() => {
    if (!documentId) return;
    setLoading(true);
    commentApi
      .list({ document_id: documentId, page: 1, page_size: 100 })
      .then((res: any) => {
        const data = res.items || res.data?.items || [];
        setComments(data);
      })
      .catch(() => message.error("加载评论失败"))
      .finally(() => setLoading(false));
  }, [documentId]);

  useEffect(() => {
    fetchComments();
    userApi
      .mentionable()
      .then((res: any) => setMentionable(res || []))
      .catch(() => {});
  }, [fetchComments]);

  const annotationById = (id: string) => annotations.find((a) => a.id === id);

  const handleMention = (username: string) => {
    setContent((prev) => (prev ? `${prev} @${username} ` : `@${username} `));
  };

  const handleSubmit = async () => {
    if (!content.trim()) {
      message.warning("请输入评论内容");
      return;
    }
    if (!targetAnnotationId && annotations.length > 0) {
      message.warning("请选择要评论的标注");
      return;
    }
    setSubmitting(true);
    try {
      await commentApi.create({
        annotation_id: targetAnnotationId!,
        content: content.trim(),
      });
      message.success("评论已发布");
      setContent("");
      setTargetAnnotationId(undefined);
      fetchComments();
    } catch {
      message.error("评论发布失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await commentApi.remove(id);
      message.success("评论已删除");
      fetchComments();
    } catch {
      message.error("删除失败");
    }
  };

  return (
    <div style={{ padding: 16 }}>
      {/* 评论输入区 */}
      <Space direction="vertical" style={{ width: "100%" }} size={12}>
        {annotations.length > 0 && (
          <Select
            style={{ width: "100%" }}
            placeholder="选择要评论的标注结果"
            value={targetAnnotationId}
            onChange={setTargetAnnotationId}
            showSearch
            optionFilterProp="label"
            options={annotations.map((a) => ({ value: a.id, label: annotationLabel(a) }))}
          />
        )}
        <TextArea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={3}
          placeholder="输入评论，可 @用户名 提及成员..."
        />
        <Space wrap>
          <Select
            style={{ minWidth: 180 }}
            placeholder="@ 提及成员"
            value={null}
            onChange={(val: string) => {
              const u = mentionable.find((m) => m.id === val);
              if (u) handleMention(u.username);
            }}
            options={mentionable.map((m) => ({ value: m.id, label: m.full_name || m.username }))}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={submitting}
            onClick={handleSubmit}
          >
            发表评论
          </Button>
        </Space>
      </Space>

      {/* 评论列表 */}
      <Typography.Title level={5} style={{ marginTop: 24 }}>
        评论讨论（{comments.length}）
      </Typography.Title>
      {loading ? (
        <Spin style={{ display: "block", margin: "30px auto" }} />
      ) : comments.length === 0 ? (
        <Empty description="暂无评论" style={{ marginTop: 20 }} />
      ) : (
        <List
          dataSource={comments}
          renderItem={(c) => {
            const ann = annotationById(c.annotation_id);
            return (
              <List.Item
                key={c.id}
                actions={
                  c.user_id === user?.id
                    ? [
                        <Popconfirm
                          key="del"
                          title="确定删除这条评论？"
                          onConfirm={() => handleDelete(c.id)}
                        >
                          <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                        </Popconfirm>,
                      ]
                    : undefined
                }
              >
                <List.Item.Meta
                  avatar={<Avatar icon={<UserOutlined />} />}
                  title={
                    <Space size={8}>
                      <Text strong>{c.full_name || c.username || c.user_id}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {dayjs(c.created_at).format("YYYY-MM-DD HH:mm")}
                      </Text>
                      {ann && (
                        <Tag color="blue">
                          {typeLabelMap[ann.annotation_type] || ann.annotation_type}
                        </Tag>
                      )}
                    </Space>
                  }
                  description={
                    <div>
                      {ann && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          针对：{annotationLabel(ann)}
                        </Text>
                      )}
                      <div style={{ marginTop: 4, whiteSpace: "pre-wrap" }}>
                        {renderContent(c.content)}
                      </div>
                    </div>
                  }
                />
              </List.Item>
            );
          }}
        />
      )}
    </div>
  );
}
