import { useEffect } from "react";
import { Table, Button, Space, Input, Select, Tag, Popconfirm, message, Upload } from "antd";
import {
  DeleteOutlined,
  PlayCircleOutlined,
  EyeOutlined,
  UploadOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useDocumentStore } from "@store/documentStore";
import { usePagination } from "@hooks/usePagination";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";

const statusMap: Record<string, { color: string; text: string }> = {
  uploaded: { color: "default", text: "已上传" },
  parsing: { color: "processing", text: "解析中" },
  parsed: { color: "success", text: "已解析" },
  failed: { color: "error", text: "失败" },
};

export default function DocumentListPage() {
  const navigate = useNavigate();
  const {
    documents,
    total,
    loading,
    filters,
    fetchDocuments,
    deleteDocument,
    triggerParse,
    uploadDocument,
    setFilters,
  } = useDocumentStore();
  const { page, pageSize } = usePagination();

  useEffect(() => {
    fetchDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, filters]);

  const handleUpload = async (file: File) => {
    try {
      await uploadDocument(file);
      message.success("上传成功");
    } catch {
      message.error("上传失败");
    }
    return false;
  };

  const columns = [
    {
      title: "标题",
      dataIndex: "title",
      ellipsis: true,
      render: (text: string, r: any) => (
        <a onClick={() => navigate(`/documents/${r.id}`)}>{text}</a>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.text}</Tag>,
    },
    { title: "页数", dataIndex: "page_count", width: 80, align: "center" as const },
    {
      title: "上传时间",
      dataIndex: "created_at",
      width: 160,
      render: (d: string) => dayjs(d).format("YYYY-MM-DD HH:mm"),
    },
    {
      title: "操作",
      key: "action",
      width: 200,
      render: (_: any, r: any) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/documents/${r.id}`)}
          />
          {r.status === "uploaded" && (
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => triggerParse(r.id)}
              title="开始解析"
            />
          )}
          {r.status === "failed" && (
            <Button
              type="link"
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => triggerParse(r.id)}
              title="重新解析"
            />
          )}
          <Popconfirm title="确认删除？" onConfirm={() => deleteDocument(r.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between" }}>
        <Space>
          <Input.Search
            placeholder="搜索文档"
            style={{ width: 200 }}
            onSearch={(v) => setFilters({ keyword: v })}
          />
          <Select
            placeholder="状态筛选"
            allowClear
            style={{ width: 120 }}
            options={Object.entries(statusMap).map(([v, { text }]) => ({ value: v, label: text }))}
            onChange={(v) => setFilters({ status: v })}
          />
        </Space>
        <Upload beforeUpload={handleUpload} accept=".pdf" showUploadList={false}>
          <Button type="primary" icon={<UploadOutlined />}>
            上传文档
          </Button>
        </Upload>
      </div>
      <Table
        columns={columns}
        dataSource={documents}
        rowKey="id"
        loading={loading}
        pagination={{
          total,
          current: page,
          pageSize,
          showSizeChanger: true,
          showTotal: (t: number) => `共 ${t} 条`,
        }}
      />
    </div>
  );
}
