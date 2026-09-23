import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Descriptions,
  Button,
  Card,
  Tag,
  Spin,
  List,
  Typography,
  Space,
  Segmented,
  Tooltip,
  Alert,
} from "antd";
import { ArrowLeftOutlined, PlayCircleOutlined, SwapOutlined } from "@ant-design/icons";
import { useDocumentStore } from "@store/documentStore";
import { citationLinkApi, documentApi, writingAssistantApi } from "@api/modules";
import type { CitationMapResult, InlineCitation } from "@/types";
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

function scrollWithRatio(source: HTMLDivElement, target: HTMLDivElement) {
  const srcRange = source.scrollHeight - source.clientHeight;
  const dstRange = target.scrollHeight - target.clientHeight;
  if (srcRange <= 0) return;
  target.scrollTop = (source.scrollTop / srcRange) * dstRange;
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

/** 渲染单页正文文本：把 citationMap 定位到的 [n] 数字转为指向参考文献的锚点链接。 */
function BodyPageText({
  pageNumber,
  text,
  citations,
  renderTooltip,
}: {
  pageNumber: number;
  text: string;
  citations: InlineCitation[];
  renderTooltip: (n: number) => string;
}) {
  const nodes: JSX.Element[] = [];
  const numeric = (citations || [])
    .filter((c) => c.ref_index !== null && typeof c.start === "number")
    .sort((a, b) => a.start - b.start);
  let cursor = 0;
  numeric.forEach((c) => {
    if (c.start < cursor) return;
    if (c.start > cursor) {
      nodes.push(<span key={`t-${cursor}`}>{text.slice(cursor, c.start)}</span>);
    }
    const raw = c.raw;
    const nums = (raw.match(/\d{1,3}/g) || []).map(Number);
    nodes.push(
      <Tooltip key={`c-${c.start}`} title={renderTooltip(nums[0])}>
        <sup
          id={`body-cite-${pageNumber}-${c.start}`}
          className="body-cite"
          style={{ cursor: "pointer" }}
        >
          {nums.map((n, j) => (
            <span key={n} style={{ display: "inline" }}>
              {j > 0 ? ", " : ""}
              <a
                href={`#ref-${n}`}
                style={{ color: "inherit" }}
                onClick={(e) => {
                  e.preventDefault();
                  const el = document.getElementById(`body-cite-${pageNumber}-${c.start}`);
                  el?.classList.add("body-cite-flash");
                  window.setTimeout(() => el?.classList.remove("body-cite-flash"), 1200);
                  scrollToId(`ref-${n}`);
                }}
              >
                {n}
              </a>
            </span>
          ))}
        </sup>
      </Tooltip>,
    );
    cursor = c.end;
  });
  if (cursor < text.length) nodes.push(<span key={`t-${cursor}`}>{text.slice(cursor)}</span>);
  return <>{nodes}</>;
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentDocument, fetchDocument, triggerParse } = useDocumentStore();
  const [titleTree, setTitleTree] = useState<
    { level: number; title: string; page_number: number }[]
  >([]);
  const [fulltextPages, setFulltextPages] = useState<{ page_number: number; text: string }[]>([]);
  const [citationMap, setCitationMap] = useState<CitationMapResult | null>(null);
  const [bilingual, setBilingual] = useState(false);
  const [translations, setTranslations] = useState<Record<number, string>>({});
  const [translateBackend, setTranslateBackend] = useState("");
  const [translating, setTranslating] = useState(false);
  // 划词翻译
  const [selAnchor, setSelAnchor] = useState<{ text: string; x: number; y: number } | null>(null);
  const [selResult, setSelResult] = useState<{ text: string; backend: string } | null>(null);
  const [selLoading, setSelLoading] = useState(false);
  const leftScrollRef = useRef<HTMLDivElement | null>(null);
  const rightScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (id) fetchDocument(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const refSet = useMemo(
    () =>
      new Set(
        (currentDocument?.references || [])
          .map((r) => r.index)
          .filter((n): n is number => typeof n === "number"),
      ),
    [currentDocument?.references],
  );

  const citedSet = useMemo(
    () => new Set(extractCiteNumbers(currentDocument?.abstract || "")),
    [currentDocument?.abstract],
  );

  // 加载正文全文并建立引用↔参考文献双向映射（5.1）
  useEffect(() => {
    if (!id || currentDocument?.status !== "parsed") return;
    let cancelled = false;
    documentApi
      .getFullText(id)
      .then((res) => {
        if (cancelled) return;
        setFulltextPages(res.pages || []);
        const refs = currentDocument.references || [];
        if (res.pages?.length && refs.length) {
          return citationLinkApi
            .map({
              pages_text: res.pages.map((p) => p.text),
              references: refs,
            })
            .then((m) => {
              if (!cancelled) setCitationMap(m);
            })
            .catch(() => {
              /* map 失败不影响正文展示 */
            });
        }
        return undefined;
      })
      .catch(() => {
        /* fulltext 失败静默 */
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, currentDocument?.status, currentDocument?.id]);

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

  // 整篇翻译（5.3）：逐页并行调 /translate，写缓存并开启对照视图
  const translateAll = useCallback(
    async (target = "zh") => {
      if (!fulltextPages.length) return;
      setTranslating(true);
      try {
        const results = await Promise.all(
          fulltextPages.map((p) =>
            writingAssistantApi.translate({ text: p.text, target }).catch(() => null),
          ),
        );
        const map: Record<number, string> = {};
        let backend = "rule";
        fulltextPages.forEach((p, i) => {
          const r = results[i];
          if (r && r.text && r.text.trim()) {
            map[p.page_number] = r.text;
            if (r.backend) backend = r.backend;
          }
        });
        setTranslations(map);
        setTranslateBackend(backend);
        setBilingual(true);
      } finally {
        setTranslating(false);
      }
    },
    [fulltextPages],
  );

  const handleBodyMouseUp = useCallback((e: React.MouseEvent) => {
    const sel = window.getSelection();
    const text = sel ? sel.toString().trim() : "";
    if (!text) {
      setSelAnchor(null);
      return;
    }
    // 仅当选区落在正文卡内才触发划词翻译
    const bodyEl = document.getElementById("body-section");
    if (bodyEl && sel && sel.anchorNode && bodyEl.contains(sel.anchorNode)) {
      setSelAnchor({ text, x: e.clientX, y: e.clientY - 90 });
      setSelResult(null);
    }
  }, []);

  const translateSelection = useCallback(async () => {
    if (!selAnchor) return;
    setSelLoading(true);
    try {
      const res = await writingAssistantApi.translate({ text: selAnchor.text, target: "zh" });
      setSelResult(res);
    } catch {
      setSelResult({ text: selAnchor.text, backend: "rule" });
    } finally {
      setSelLoading(false);
    }
  }, [selAnchor]);

  const syncScroll = useCallback((source: "left" | "right") => {
    const left = leftScrollRef.current;
    const right = rightScrollRef.current;
    if (!left || !right) return;
    if (source === "left") scrollWithRatio(left, right);
    else scrollWithRatio(right, left);
  }, []);

  const handleViewChange = useCallback(
    (v: string | number) => {
      const targetBilingual = v === "zh";
      setBilingual(targetBilingual);
      if (
        targetBilingual &&
        !translating &&
        fulltextPages.length &&
        Object.keys(translations).length === 0
      ) {
        translateAll("zh");
      }
    },
    [fulltextPages, translating, translations, translateAll],
  );

  const effectiveBackToBody = useMemo(() => {
    const s = new Set<number>();
    Object.entries(citationMap?.by_reference || {}).forEach(([k, v]) => {
      if (v?.length) s.add(Number(k));
    });
    return s;
  }, [citationMap]);

  if (!currentDocument)
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;

  const doc = currentDocument;
  const byPageCites = (pageNumber: number): InlineCitation[] =>
    (citationMap?.citations || []).filter((c) => (c.page_number ?? 0) === pageNumber);

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
          <Descriptions.Item label="机构">{doc.affiliations?.join("；") || "-"}</Descriptions.Item>
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
              const authors = Array.isArray(ref.authors) ? ref.authors.join(", ") : ref.authors;
              const volIssue = ref.volume
                ? `${ref.volume}${ref.issue ? `(${ref.issue})` : ""}`
                : ref.issue;
              const detail = [authors, ref.journal, ref.year, volIssue, ref.pages, ref.doi]
                .filter(Boolean)
                .join(" · ");
              const bodyHits: InlineCitation[] = citationMap?.by_reference?.[String(idx)] || [];
              const inAbstract = citedSet.has(idx);
              const inBody = effectiveBackToBody.has(idx);
              const goBack = () => {
                if (inBody && bodyHits.length) {
                  const hit = bodyHits[0];
                  const el = document.getElementById(`body-cite-${hit.page_number}-${hit.start}`);
                  el?.classList.add("body-cite-flash");
                  window.setTimeout(() => el?.classList.remove("body-cite-flash"), 1200);
                  scrollToId(`body-cite-${hit.page_number}-${hit.start}`);
                } else if (inAbstract) {
                  scrollToId(`cite-${idx}`);
                }
              };
              return (
                <List.Item
                  key={idx}
                  id={`ref-${idx}`}
                  extra={
                    (inAbstract || inBody) && (
                      <Typography.Link onClick={goBack} style={{ fontSize: 12 }}>
                        {inBody ? "回到正文引用" : "回到正文"}
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
                      <Typography.Text type="secondary">{detail || ref.raw}</Typography.Text>
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
        <Card
          title="正文（版式联动阅读）"
          style={{ marginTop: 16 }}
          extra={
            <Space>
              <Segmented
                value={bilingual ? "zh" : "org"}
                onChange={handleViewChange}
                options={[
                  { label: "原文", value: "org" },
                  { label: "中英对照", value: "zh" },
                ]}
              />
              <Button
                icon={<SwapOutlined />}
                loading={translating}
                disabled={!fulltextPages.length}
                onClick={() => translateAll("zh")}
              >
                整篇翻译
              </Button>
            </Space>
          }
        >
          {!fulltextPages.length && <Typography.Text type="secondary">暂无正文。</Typography.Text>}
          {fulltextPages.length > 0 && (
            <div id="body-section" onMouseUp={handleBodyMouseUp}>
              {bilingual && translateBackend === "rule" && (
                <Alert
                  style={{ marginBottom: 12 }}
                  type="warning"
                  showIcon
                  message="翻译端未配置或调用失败，译文为原文回显（backend=rule）。"
                />
              )}
              <div style={{ display: "flex", gap: 16 }}>
                <div
                  ref={leftScrollRef}
                  onScroll={() => syncScroll("left")}
                  data-testid="body-original"
                  style={{
                    flex: 1,
                    maxHeight: 560,
                    overflow: "auto",
                    paddingRight: 8,
                    lineHeight: 1.8,
                  }}
                >
                  {fulltextPages.map((p) => (
                    <div key={p.page_number} style={{ marginBottom: 16 }}>
                      <Typography.Text type="secondary" style={{ fontWeight: 600 }}>
                        — 第 {p.page_number} 页 —
                      </Typography.Text>
                      <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                        <BodyPageText
                          pageNumber={p.page_number}
                          text={p.text}
                          citations={byPageCites(p.page_number)}
                          renderTooltip={(n) => `跳转到参考文献 [${n}]`}
                        />
                      </Typography.Paragraph>
                    </div>
                  ))}
                </div>
                {bilingual && (
                  <div
                    ref={rightScrollRef}
                    onScroll={() => syncScroll("right")}
                    data-testid="body-translation"
                    style={{
                      flex: 1,
                      maxHeight: 560,
                      overflow: "auto",
                      paddingLeft: 8,
                      borderLeft: "1px solid #f0f0f0",
                      lineHeight: 1.8,
                    }}
                  >
                    {fulltextPages.map((p) => (
                      <div key={p.page_number} style={{ marginBottom: 16 }}>
                        <Typography.Text type="secondary" style={{ fontWeight: 600 }}>
                          — 第 {p.page_number} 页 —
                        </Typography.Text>
                        <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                          {translations[p.page_number] ?? "（翻译中…）"}
                        </Typography.Paragraph>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
          {selAnchor && (
            <div
              style={{
                position: "fixed",
                zIndex: 10,
                left: selAnchor.x || 16,
                top: selAnchor.y || 120,
              }}
            >
              <Space direction="vertical" size={4}>
                <Button size="small" loading={selLoading} onClick={translateSelection}>
                  翻译选中文本
                </Button>
                {selResult && (
                  <Tooltip title={selResult.backend === "llm" ? "LLM 翻译" : "规则回显"}>
                    <Card size="small" style={{ maxWidth: 360 }}>
                      <Typography.Paragraph style={{ marginBottom: 0 }}>
                        {selResult.text}
                      </Typography.Paragraph>
                    </Card>
                  </Tooltip>
                )}
              </Space>
            </div>
          )}
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
