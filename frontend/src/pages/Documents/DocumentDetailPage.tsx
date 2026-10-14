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
  InputNumber,
  Tree,
} from "antd";
import { ArrowLeftOutlined, DownloadOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { useDocumentStore } from "@store/documentStore";
import { citationLinkApi, documentApi, writingAssistantApi } from "@api/modules";
import type { CitationMapResult, InlineCitation, TitleTreeItem } from "@/types";
import LatexFormula from "@components/Formula/LatexFormula";
import dayjs from "dayjs";
import { buildTitleTree } from "@utils/titleTree";

const statusMap: Record<string, { color: string; text: string }> = {
  uploaded: { color: "default", text: "已上传" },
  parsing: { color: "processing", text: "解析中" },
  parsed: { color: "success", text: "已解析" },
  failed: { color: "error", text: "失败" },
};

const CITE_SPLIT_RE = /[,，\-\s、]+/;
const CITE_MATCH_RE = /\[([\d,，\-\s、]+)\]/g;

/** 页面公式元素（来自 GET /documents/{id}/pages/{n}/elements 的 formula 条目）。 */
interface DocumentFormulaItem {
  page_number: number;
  element: {
    id?: string;
    latex?: string | null;
    content?: string | null;
    is_display?: boolean | null;
    formula_number?: string | null;
    formula_source?: string | null;
    formula_normalized?: boolean | null;
  };
}

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
  const [titleTree, setTitleTree] = useState<TitleTreeItem[]>([]);
  const [titleTreeBackend, setTitleTreeBackend] = useState("");
  const [fulltextPages, setFulltextPages] = useState<{ page_number: number; text: string }[]>([]);
  const [citationMap, setCitationMap] = useState<CitationMapResult | null>(null);
  const [formulas, setFormulas] = useState<DocumentFormulaItem[]>([]);
  const [bilingual, setBilingual] = useState(false);
  const [translations, setTranslations] = useState<Record<number, string>>({});
  const [translateBackend, setTranslateBackend] = useState("");
  // 划词翻译
  const [selAnchor, setSelAnchor] = useState<{ text: string; x: number; y: number } | null>(null);
  const [selResult, setSelResult] = useState<{ text: string; backend: string } | null>(null);
  const [selLoading, setSelLoading] = useState(false);
  // ── 单页翻译缓存/在途守卫 ref（避免重复请求、避免回调闭包过期） ──
  const requestedRef = useRef<Set<number>>(new Set());
  const translationsRef = useRef<Record<number, string>>({});
  const [currentPage, setCurrentPageState] = useState(1);
  const [jumpInput, setJumpInput] = useState<number | null>(null);

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
        // 新文档全文重载：清空翻译缓存与在途集合，避免跨文档串页
        requestedRef.current.clear();
        translationsRef.current = {};
        setTranslations({});
        setCurrentPageState(1);
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

  // 加载全部页面的公式元素（统一 LaTeX 渲染），供「公式」卡片展示
  const pageCount = currentDocument?.page_count || 0;
  useEffect(() => {
    if (!id || currentDocument?.status !== "parsed" || !pageCount) {
      setFormulas([]);
      return;
    }
    let cancelled = false;
    Promise.all(
      Array.from({ length: pageCount }, (_, i) => i + 1).map((p) =>
        documentApi
          .getPageElements(id, p)
          .then((res: any) => ({ page: p, elements: res?.elements || [] }))
          .catch(() => ({ page: p, elements: [] as any[] })),
      ),
    ).then((results) => {
      if (cancelled) return;
      const collected: DocumentFormulaItem[] = [];
      results.forEach((r) => {
        (r.elements || [])
          .filter((el: any) => el?.element_type === "formula")
          .forEach((el: any) => collected.push({ page_number: r.page, element: el }));
      });
      setFormulas(collected);
    });
    return () => {
      cancelled = true;
    };
  }, [id, currentDocument?.status, currentDocument?.id, pageCount]);

  useEffect(() => {
    if (!id) return;
    const fallback = () => {
      if (currentDocument?.file_path) {
        citationLinkApi
          .titleTree(currentDocument.file_path)
          .then((res) => {
            setTitleTree(res.tree || []);
            setTitleTreeBackend("pdf");
          })
          .catch(() => setTitleTree([]));
      } else {
        setTitleTree([]);
      }
    };
    documentApi
      .getTitleTree(id)
      .then((res) => {
        if (res.tree?.length) {
          setTitleTree(res.tree);
          setTitleTreeBackend(res.backend || "elements");
        } else {
          fallback();
        }
      })
      .catch(() => fallback());
  }, [id, currentDocument?.file_path]);

  const treeData = useMemo(() => buildTitleTree(titleTree), [titleTree]);

  // 译文缓存同步到 ref，供翻译回调读取最新值，避免闭包过期
  useEffect(() => {
    translationsRef.current = translations;
  }, [translations]);

  const totalPages = Math.max(1, fulltextPages.length);
  const displayedPage = Math.min(currentPage, totalPages);

  const pageTextOf = useCallback(
    (pageNumber: number) => fulltextPages.find((p) => p.page_number === pageNumber)?.text || "",
    [fulltextPages],
  );

  // 翻译指定单页：未译且不在途才请求，写缓存；不预翻译其它页
  const translatePage = useCallback(
    (pageNumber: number) => {
      const text = pageTextOf(pageNumber).trim();
      if (!text || translationsRef.current[pageNumber] || requestedRef.current.has(pageNumber)) {
        return;
      }
      requestedRef.current.add(pageNumber);
      writingAssistantApi
        .translate({ text: pageTextOf(pageNumber), target: "zh" })
        .then((r) => {
          if (r && r.text && r.text.trim()) {
            translationsRef.current[pageNumber] = r.text;
            if (r.backend) setTranslateBackend(r.backend);
            setTranslations({ ...translationsRef.current });
          }
        })
        .catch(() => {
          /* 翻译失败保留占位，不阻塞 */
        })
        .finally(() => {
          requestedRef.current.delete(pageNumber);
        });
    },
    [pageTextOf],
  );

  // 翻页：钳制到 [1, totalPages]，切换当前页；对照模式下翻译新页
  const goPage = useCallback(
    (p: number) => {
      if (!totalPages) return;
      const raw = Number.isFinite(p) ? Math.floor(p) : 1;
      const next = Math.max(1, Math.min(totalPages, raw || 1));
      setCurrentPageState(next);
      if (bilingual) translatePage(next);
    },
    [totalPages, bilingual, translatePage],
  );

  const handlePrevPage = useCallback(() => goPage(displayedPage - 1), [goPage, displayedPage]);
  const handleNextPage = useCallback(() => goPage(displayedPage + 1), [goPage, displayedPage]);

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

  const handleExportJats = useCallback(async () => {
    if (!id) return;
    try {
      const blob = await documentApi.exportJats(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${currentDocument?.title || id}.jats.xml`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      /* 导出失败不阻塞页面 */
    }
  }, [id, currentDocument?.title]);

  const handleViewChange = useCallback(
    (v: string | number) => {
      const isBilingual = v === "zh";
      setBilingual(isBilingual);
      if (isBilingual) translatePage(displayedPage);
    },
    [translatePage, displayedPage],
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
          <Descriptions.Item label="文件大小" span={2}>
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

      {formulas.length > 0 && (
        <Card title={`公式（LaTeX 统一渲染，共 ${formulas.length} 个）`} style={{ marginTop: 16 }}>
          <List
            dataSource={formulas}
            renderItem={({ page_number, element }, i) => (
              <List.Item key={element.id || `formula-${i}`}>
                <List.Item.Meta
                  title={
                    <Space size={6} wrap>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        p{page_number}
                      </Typography.Text>
                      <Tag color="orange">公式</Tag>
                      {element.is_display === false ? <Tag>行内</Tag> : <Tag>行间</Tag>}
                      {element.formula_source ? <Tag>{element.formula_source}</Tag> : null}
                      {element.formula_normalized === false ? (
                        <Tag color="red">未转 LaTeX</Tag>
                      ) : null}
                    </Space>
                  }
                  description={
                    <LatexFormula
                      latex={element.latex ?? element.content}
                      display={element.is_display ?? true}
                      number={element.formula_number ?? null}
                      normalized={element.formula_normalized ?? null}
                    />
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}

      {titleTree.length > 0 && treeData.length > 0 && (
        <Card
          title="标题树（目录导航）"
          style={{ marginTop: 16 }}
          extra={
            <Typography.Text type="secondary">
              来源 {titleTreeBackend === "pdf" ? "PDF" : "elements"}
            </Typography.Text>
          }
        >
          <Tree
            showLine
            defaultExpandAll
            treeData={treeData}
            onSelect={(_keys, info) => {
              const page = (info.node as { page?: number })?.page;
              if (typeof page === "number") goPage(page);
            }}
            titleRender={(node) => {
              const n = node as unknown as {
                title: string;
                page?: number;
              };
              return (
                <Space size={6}>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    p{n.page}
                  </Typography.Text>
                  <span>{n.title}</span>
                </Space>
              );
            }}
          />
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
                  data-testid="body-original"
                  style={{
                    flex: 1,
                    lineHeight: 1.8,
                    paddingRight: 8,
                    borderRight: bilingual ? "1px solid #f0f0f0" : "none",
                  }}
                >
                  <Typography.Text type="secondary" style={{ fontWeight: 600 }}>
                    — 第 {displayedPage} 页 —
                  </Typography.Text>
                  <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                    <BodyPageText
                      pageNumber={displayedPage}
                      text={pageTextOf(displayedPage)}
                      citations={byPageCites(displayedPage)}
                      renderTooltip={(n) => `跳转到参考文献 [${n}]`}
                    />
                  </Typography.Paragraph>
                </div>
                {bilingual && (
                  <div
                    data-testid="body-translation"
                    style={{
                      flex: 1,
                      lineHeight: 1.8,
                      paddingLeft: 8,
                      borderLeft: "1px solid #f0f0f0",
                    }}
                  >
                    <Typography.Text type="secondary" style={{ fontWeight: 600 }}>
                      — 第 {displayedPage} 页 —
                    </Typography.Text>
                    <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                      {translations[displayedPage] ?? "（翻译中…）"}
                    </Typography.Paragraph>
                  </div>
                )}
              </div>
              <div
                data-testid="page-jumper"
                style={{
                  marginTop: 12,
                  paddingTop: 12,
                  borderTop: "1px solid #f0f0f0",
                  display: "flex",
                  justifyContent: "center",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "4px 8px",
                    borderRadius: 8,
                    border: "1px solid #d9d9d9",
                    background: "#fafafa",
                    boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                  }}
                >
                  <Button size="small" onClick={handlePrevPage} disabled={displayedPage <= 1}>
                    上一页
                  </Button>
                  <Typography.Text
                    style={{
                      minWidth: 70,
                      textAlign: "center",
                      color: "rgba(0,0,0,0.65)",
                    }}
                    data-testid="page-info"
                  >
                    {displayedPage} / {totalPages}
                  </Typography.Text>
                  <Button
                    size="small"
                    onClick={handleNextPage}
                    disabled={displayedPage >= totalPages}
                  >
                    下一页
                  </Button>
                  <InputNumber
                    size="small"
                    min={1}
                    max={totalPages}
                    value={jumpInput ?? displayedPage}
                    onChange={setJumpInput}
                    onPressEnter={() => goPage(jumpInput ?? displayedPage)}
                    controls={false}
                    placeholder={"页码"}
                    style={{ width: 76 }}
                    aria-label="跳转页码"
                  />
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => goPage(jumpInput ?? displayedPage)}
                    data-testid="jump-btn"
                  >
                    跳转
                  </Button>
                </div>
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
        <Space style={{ marginTop: 16, display: "flex" }}>
          <Button type="primary" onClick={() => navigate(`/annotation/${doc.id}`)}>
            进入标注工作台
          </Button>
          <Button icon={<DownloadOutlined />} onClick={handleExportJats}>
            导出 JATS
          </Button>
        </Space>
      )}
    </div>
  );
}
