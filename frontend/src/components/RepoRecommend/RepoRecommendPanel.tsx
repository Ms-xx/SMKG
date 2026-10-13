import { useState } from "react";
import { Alert, Button, Card, Space, Table, Tag, Typography, message } from "antd";
import { BulbOutlined, DislikeOutlined, LikeOutlined } from "@ant-design/icons";
import { repoRecommendApi } from "@api/modules";
import type { PaperResult, RepoMeta, RepoRecommendation } from "@/types";

const { Text } = Typography;

type Sentiment = "like" | "dislike";

interface RepoRecommendPanelProps {
  candidates: PaperResult[];
  localRefsRaw: string;
}

/**
 * 步骤 21.4：GitHub 开源复现性优先推荐面板。
 * - 调用 /repo-recommend/recommend，展示「开源可复现」标识、推荐理由与复现性分；
 * - 显示后端离/在线抓取状态（真实 star vs 离线不编造）；
 * - 提供点赞/踩，调用 /repo-recommend/feedback 持久化，本地即时高亮反馈状态。
 */
export default function RepoRecommendPanel({ candidates, localRefsRaw }: RepoRecommendPanelProps) {
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<RepoRecommendation[]>([]);
  const [githubOnline, setGithubOnline] = useState<boolean | null>(null);
  const [feedback, setFeedback] = useState<Record<string, Sentiment | undefined>>({});
  const [submittingRepo, setSubmittingRepo] = useState<string | null>(null);

  const parseRefs = (): Record<string, any>[] => {
    if (!localRefsRaw.trim()) return [];
    try {
      const parsed = JSON.parse(localRefsRaw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      message.error("本地文献库 JSON 解析失败，已按空库处理");
      return [];
    }
  };

  const runRecommend = async () => {
    if (candidates.length === 0) {
      message.warning("请先检索获取候选论文");
      return;
    }
    setLoading(true);
    try {
      const res = await repoRecommendApi.recommend({
        local_references: parseRefs(),
        candidates,
      });
      setRecommendations(res.recommendations || []);
      setGithubOnline(res.github_online);
    } catch {
      message.error("复现性推荐请求失败，请检查权限/网络");
    } finally {
      setLoading(false);
    }
  };

  const toggleFeedback = async (repo: string, sentiment: Sentiment) => {
    setSubmittingRepo(repo);
    try {
      await repoRecommendApi.feedback({ repo, sentiment });
      setFeedback((prev) => ({ ...prev, [repo]: sentiment }));
      message.success(`已记录${sentiment === "like" ? "点赞" : "踩"}：${repo}`);
    } catch {
      message.error("点赞/踩提交失败，请检查权限/网络");
    } finally {
      setSubmittingRepo(null);
    }
  };

  const repoTag = (r: RepoMeta) => {
    const label =
      r.source === "online"
        ? `${r.repo} ⭐${r.star_count ?? 0}${r.license ? ` · ${r.license}` : ""}`
        : `${r.repo}（离线，不编造 star）`;
    const href = r.html_url || `https://github.com/${r.repo}`;
    return (
      <Tag
        key={r.repo}
        color={r.source === "online" ? "green" : "orange"}
        style={{ marginBottom: 4 }}
      >
        <a href={href} target="_blank" rel="noreferrer">
          {label}
        </a>
      </Tag>
    );
  };

  const columns = [
    {
      title: "标题",
      dataIndex: "title",
      ellipsis: true,
      render: (v: string) => <Text strong>{v || "-"}</Text>,
    },
    {
      title: "开源可复现",
      dataIndex: "open_source",
      width: 220,
      render: (_: boolean, item: RepoRecommendation) =>
        item.open_source && item.repos?.length ? (
          <div>{item.repos.map(repoTag)}</div>
        ) : (
          <Tag color="default">未检出开源仓库</Tag>
        ),
    },
    {
      title: "推荐理由",
      dataIndex: "reason",
      ellipsis: true,
      render: (v: string) => <Text type="secondary">{v || "-"}</Text>,
    },
    {
      title: "复现性分",
      dataIndex: "reproducibility_score",
      width: 100,
      render: (v: number) => (v == null ? "-" : v.toFixed(3)),
    },
    {
      title: "点赞 / 踩",
      key: "feedback",
      width: 150,
      render: (_: unknown, item: RepoRecommendation) => {
        const repo = item.repos?.[0]?.repo || "";
        const state = repo ? feedback[repo] : undefined;
        const disabled = !repo || submittingRepo === repo;
        return (
          <Space size={4}>
            <Button
              size="small"
              icon={<LikeOutlined />}
              type={state === "like" ? "primary" : "text"}
              disabled={disabled}
              onClick={() => repo && toggleFeedback(repo, "like")}
            >
              赞
            </Button>
            <Button
              size="small"
              icon={<DislikeOutlined />}
              type={state === "dislike" ? "primary" : "text"}
              danger={state === "dislike"}
              disabled={disabled}
              onClick={() => repo && toggleFeedback(repo, "dislike")}
            >
              踩
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <Card
      size="small"
      title="复现性优先推荐（开源可复现）"
      style={{ marginTop: 16, borderRadius: 12 }}
    >
      <Space direction="vertical" style={{ width: "100%" }}>
        <Button
          type="primary"
          ghost
          icon={<BulbOutlined />}
          onClick={runRecommend}
          loading={loading}
        >
          生成复现性推荐
        </Button>
        {githubOnline != null &&
          (githubOnline ? (
            <Alert
              type="success"
              showIcon
              message="已连接 GitHub REST API，展示真实仓库元数据（star / license）"
            />
          ) : (
            <Alert
              type="warning"
              showIcon
              message="GitHub 在线抓取不可用——已降级为离线标注，不编造 star 数"
            />
          ))}
        {recommendations.length > 0 && (
          <Table
            columns={columns}
            dataSource={recommendations}
            rowKey={(r) => r.title || r.source || r.reason}
            pagination={false}
            size="small"
            scroll={{ x: 900 }}
          />
        )}
      </Space>
    </Card>
  );
}
