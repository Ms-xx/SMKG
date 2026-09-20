import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Descriptions, Button, Card, Tag, Spin, List, Typography } from "antd";
import { ArrowLeftOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { useDocumentStore } from "@store/documentStore";
import dayjs from "dayjs";

const statusMap: Record<string, { color: string; text: string }> = {
  uploaded: { color: "default", text: "已上传" },
  parsing: { color: "processing", text: "解析中" },
  parsed: { color: "success", text: "已解析" },
  failed: { color: "error", text: "失败" },
};

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentDocument, fetchDocument, triggerParse } = useDocumentStore();

  useEffect(() => {
    if (id) fetchDocument(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!currentDocument)
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;

  const doc = currentDocument;

  return (
    <div>
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate("/documents")}
        style={{ marginBottom: 16 }}
      >
        返回
      </Button>
      <Card
        title="文档详情"
        extra={
          doc.status === "uploaded" && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => triggerParse(doc.id)}
            >
              开始解析
            </Button>
          )
        }
      >
        <Descriptions column={2} bordered>
          <Descriptions.Item label="标题">{doc.title}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={statusMap[doc.status]?.color}>{statusMap[doc.status]?.text}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="DOI">{doc.doi || "-"}</Descriptions.Item>
          <Descriptions.Item label="期刊">{doc.journal || "-"}</Descriptions.Item>
          <Descriptions.Item label="作者">{doc.authors?.join(", ") || "-"}</Descriptions.Item>
          <Descriptions.Item label="发表日期">
            {doc.publication_date ? dayjs(doc.publication_date).format("YYYY-MM-DD") : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="页数">{doc.page_count || "-"}</Descriptions.Item>
          <Descriptions.Item label="文件大小">
            {doc.file_size ? `${(doc.file_size / 1024 / 1024).toFixed(2)} MB` : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="关键词" span={2}>
            {doc.keywords?.join(", ") || "-"}
          </Descriptions.Item>
          <Descriptions.Item label="摘要" span={2}>
            {doc.abstract || "-"}
          </Descriptions.Item>
          <Descriptions.Item label="上传时间">
            {dayjs(doc.created_at).format("YYYY-MM-DD HH:mm")}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {dayjs(doc.updated_at).format("YYYY-MM-DD HH:mm")}
          </Descriptions.Item>
        </Descriptions>
      </Card>
      {doc.references?.length > 0 && (
        <Card title={`参考文献（${doc.references.length}）`} style={{ marginTop: 16 }}>
          <List
            dataSource={doc.references}
            renderItem={(ref) => (
              <List.Item key={ref.index}>
                <List.Item.Meta
                  title={
                    <Typography.Text strong>
                      [{ref.index}] {ref.title || ref.raw}
                    </Typography.Text>
                  }
                  description={
                    <Typography.Text type="secondary">
                      {[ref.authors, ref.journal, ref.year, ref.doi].filter(Boolean).join(" · ")}
                    </Typography.Text>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}
      {doc.status === "parsed" && (
        <Button
          type="primary"
          style={{ marginTop: 16 }}
          onClick={() => navigate(`/annotation/${doc.id}`)}
        >
          进入标注工作台
        </Button>
      )}
    </div>
  );
}
