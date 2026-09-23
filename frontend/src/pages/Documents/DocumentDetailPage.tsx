import { Fragment, useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Descriptions, Button, Card, Tag, Spin, List, Typography } from "antd";
import { ArrowLeftOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { useDocumentStore } from "@store/documentStore";
import { citationLinkApi } from "@api/modules";
import dayjs from "dayjs";

const statusMap: Record<string, { color: string; text: string }> = {
  uploaded: { color: "default", text: "已上传" },
  parsing: { color: "processing", text: "解析中" },
  parsed: { color: "success", text: "已解析" },
  failed: { color: "error", text: "失败" },
};

const CITE_SPLIT_RE = /[,，\-\s、]+/;
const CITE_MATCH_RE = /\[([\d,，\-\s、]+)\]/g;

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function extractCiteNumbers(text: string): number[] {
  const nums: number[] = [];
  const re = new RegExp(CITE_MATCH_RE.source, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    m[1]
      .split(CITE_SPLIT_RE)
      .filter(Boolean)
      .map(Number)
      .forEach((n) => nums.push(n));
  }
  return nums;
}

function CitationLinks({ text, refSet }: { text: string; refSet: Set<number> }) {
  const parts = text.split(CITE_MATCH_RE);
  return (
    <>
      {parts.map((part, i) => {
        if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>;
        const nums = part.split(CITE_SPLIT_RE).filter(Boolean).map(Number);
        return (
          <Fragment key={i}>
            [
            {nums.map((n, j) => (
              <Fragment key={n}>
                {j > 0 ? ", " : ""}
                {refSet.has(n) ? (
                  <Typography.Link
                    id={`cite-${n}`}
                    href={`#ref-${n}`}
                    onClick={(e) => {
                      e.preventDefault();
                      scrollToId(`ref-${n}`);
                    }}
                  >
                    {n}
                  </Typography.Link>
                ) : (
                  <span>{n}</span>
                )}
              </Fragment>
            ))}
            ]
          </Fragment>
        );
      })}
    </>
  );
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentDocument, fetchDocument, triggerParse } = useDocumentStore();
  const [titleTree, setTitleTree] = useState<
    { level: number; title: string; page_number: number }[]
  >([]);

  useEffect(() => {
    if (id) fetchDocument(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (currentDocument?.file_path) {
      citationLinkApi
        .titleTree(currentDocument.file_path)
        .then((res) => setTitleTree(res.tree || []))
        .catch(() => setTitleTree([]));
    } else {
      setTitleTree([]);
    }
  }, [currentDocument?.file_path]);

  if (!currentDocument)
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;

  const doc = currentDocument;

  const refSet = useMemo(
    () =>
      new Set(
        (doc.references || [])
          .map((r) => r.index)
          .filter((n): n is number => typeof n === "number"),
      ),
    [doc.references],
  );

  const citedSet = useMemo(
    () => new Set(extractCiteNumbers(doc.abstract || "")),
    [doc.abstract],
  );

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
          <Descriptions.Item label="机构">
            {doc.affiliations?.join("；") || "-"}
          </Descriptions.Item>
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
            {doc.abstract ? (
              <Typography.Paragraph style={{ marginBottom: 0 }}>
                <CitationLinks text={doc.abstract} refSet={refSet} />
              </Typography.Paragraph>
            ) : (
              "-"
            )}
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
            renderItem={(ref, i) => {
              const idx = ref.index ?? i + 1;
              const authors = Array.isArray(ref.authors)
                ? ref.authors.join(", ")
                : ref.authors;
              const volIssue = ref.volume
                ? `${ref.volume}${ref.issue ? `(${ref.issue})` : ""}`
                : ref.issue;
              const detail = [
                authors,
                ref.journal,
                ref.year,
                volIssue,
                ref.pages,
                ref.doi,
              ]
                .filter(Boolean)
                .join(" · ");
              return (
                <List.Item
                  key={idx}
                  id={`ref-${idx}`}
                  extra={
                    citedSet.has(idx) && (
                      <Typography.Link
                        onClick={() => scrollToId(`cite-${idx}`)}
                        style={{ fontSize: 12 }}
                      >
                        回到正文
                      </Typography.Link>
                    )
                  }
                >
                  <List.Item.Meta
                    title={
                      <Typography.Text strong>
                        [{idx}] {ref.title || ref.raw}
                      </Typography.Text>
                    }
                    description={
                      <Typography.Text type="secondary">
                        {detail || ref.raw}
                      </Typography.Text>
                    }
                  />
                </List.Item>
              );
            }}
          />
        </Card>
      )}
      {titleTree.length > 0 && (
        <Card title="标题树（版式联动阅读）" style={{ marginTop: 16 }}>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {titleTree.map((t, i) => (
              <li key={i} style={{ padding: "4px 0", paddingLeft: (t.level - 1) * 20 }}>
                <Typography.Text type="secondary" style={{ marginRight: 8 }}>
                  p{t.page_number}
                </Typography.Text>
                {t.title}
              </li>
            ))}
          </ul>
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
