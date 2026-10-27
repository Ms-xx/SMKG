#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""论文数据重置与切换运维脚本

对旧用户上传数据、MinIO 论文对象与 MySQL/Neo4j 论文数据执行清单预演、定向删除、
全量清空，并将新数据源目录（如 ``download_data/Paper``）下的 PDF 批量入库。

四个子命令：
    inventory    只读清单预演（不产生任何删除副作用）
    delete-user  定向删除指定用户（--user-uuid）的旧数据
    clear-all    全量清空 MinIO 论文对象 + MySQL 论文七表 + Neo4j 全图
    ingest       批量入库 --dir 下的新 PDF（上传→解析→抽取→建图）

示例：
    python backend/scripts/paper_data_switch.py inventory --user-uuid 462111b8-37f5-11f1-98d0-b025aa39c5bf
    python backend/scripts/paper_data_switch.py delete-user --user-uuid 462111b8-37f5-11f1-98d0-b025aa39c5bf --yes
    python backend/scripts/paper_data_switch.py clear-all --yes
    python backend/scripts/paper_data_switch.py ingest --dir "D:\\work\\VSCodeWork\\LX\\download_data\\Paper" --resume outputs/paper_data_switch_ingest.json

注意：
    - 删除/清空为不可逆操作，执行前请先备份（见 --help 与 design 回滚方案）。
    - 本脚本涉及 MySQL / Neo4j(bootstrap) / MinIO / 后端 HTTP，需在可直连这些
      服务的本机终端运行（沙箱禁止 Python socket）。
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# 把 backend 目录加入 sys.path，复用 app.core.config / app.utils / app.services
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Windows 下 neo4j async driver 的 bolt socket 与默认 Proactor loop 不兼容，
# 须切换 Selector loop（否则 sendall 时 _proactor 为 None 崩溃）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REPO_ROOT = os.path.abspath(os.path.join(_BACKEND_DIR, ".."))
_OUTPUTS_DIR = os.path.join(_REPO_ROOT, "outputs")
_AUDIT_LOG = os.path.join(_OUTPUTS_DIR, "paper_data_switch_audit.log")

import requests  # noqa: E402

from app.core.config import settings  # noqa: E402

# MinIO 不可用时的本地回退目录（与 minio_client.LOCAL_STORAGE_DIR 保持一致）
_LOCAL_STORAGE_DIR = os.path.join(_BACKEND_DIR, "storage", "uploads")

# 论文相关七张 MySQL 表（按外键依赖「先子后主」顺序）
_MYSQL_TABLES_ORDERED = [
    "annotation_versions",
    "annotation_comments",
    "annotations",
    "tasks",
    "document_elements",
    "document_pages",
    "documents",
]

PDF_NAME_RE = re.compile(r"^\d{3}_.*\.pdf$", re.IGNORECASE)


# ──────────────────────────────────────────────────────────────────────
# 纯函数（可单元测试）
# ──────────────────────────────────────────────────────────────────────
def derive_title(filename: str) -> str:
    """由 ``001_xxx.pdf`` 派生标题 ``xxx``（去掉 3 位序号前缀与扩展名）。"""
    stem = os.path.splitext(os.path.basename(filename))[0]
    return re.sub(r"^\d{3}_", "", stem)


def filter_pdfs(directory: str) -> list[str]:
    r"""扫描目录，返回匹配形如 ``001_xxx.pdf``（3 位序号前缀）的文件绝对路径（按名称排序）。"""
    d = Path(directory)
    if not d.is_dir():
        return []
    return sorted(str(p) for p in d.glob("*.pdf") if PDF_NAME_RE.match(p.name))


def flatten_fulltext(ft) -> str:
    """兼容 fulltext 接口多种返回形状，拼出纯文本。"""
    if isinstance(ft, str):
        return ft
    if not ft:
        return ""
    if isinstance(ft, dict) and ft.get("text"):
        return ft["text"]
    pages = ft.get("pages") or ft.get("data") or [] if isinstance(ft, dict) else []
    parts = []
    for p in pages:
        if isinstance(p, str):
            parts.append(p)
        elif isinstance(p, dict):
            for k in ("text", "content", "full_text"):
                v = p.get(k) or p.get(k + "_content")
                if v:
                    parts.append(v)
                    break
    return " ".join(p for p in parts if p)


def build_chunks(text: str, size: int = 1200) -> list:
    return [text[i : i + size] for i in range(0, len(text), size)]


# ──────────────────────────────────────────────────────────────────────
# 报告数据结构
# ──────────────────────────────────────────────────────────────────────
@dataclass
class InventoryReport:
    started_at: str = ""
    user_uuid: str = ""
    doc_ids: list = field(default_factory=list)
    local_files: list = field(default_factory=list)
    minio_objects: list = field(default_factory=list)
    minio_image_objects: list = field(default_factory=list)
    mysql_counts: dict = field(default_factory=dict)
    neo4j_total_nodes: int = 0
    neo4j_matched_nodes: int = 0


@dataclass
class DeleteReport:
    started_at: str = ""
    user_uuid: str = ""
    doc_ids: list = field(default_factory=list)
    deleted_local: int = 0
    deleted_minio: int = 0
    deleted_mysql: dict = field(default_factory=dict)
    deleted_neo4j: int = 0
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)


@dataclass
class ClearReport:
    started_at: str = ""
    minio_removed: int = 0
    mysql_cleared: dict = field(default_factory=dict)
    neo4j_cleared: int = 0
    neo4j_after: int = 0
    snapshot_invalidated: bool = False


@dataclass
class IngestRecord:
    filename: str = ""
    title: str = ""
    document_id: str = ""
    parse_status: str = ""
    entity_count: int = 0
    relation_count: int = 0
    success: bool = False
    error: str = ""


@dataclass
class IngestReport:
    started_at: str = ""
    dir: str = ""
    total: int = 0
    ok_count: int = 0
    fail_count: int = 0
    skipped: int = 0
    records: list = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────
# 报告落盘与审计
# ──────────────────────────────────────────────────────────────────────
def write_report(report, out_path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
    return out_path


def default_report_path(kind: str) -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(_OUTPUTS_DIR, f"paper_data_switch_{kind}_{ts}.json")


def audit_log(action: str, operator: str, scope: str, result: str) -> None:
    os.makedirs(_OUTPUTS_DIR, exist_ok=True)
    line = json.dumps(
        {
            "ts": datetime.now().isoformat(),
            "action": action,
            "operator": operator,
            "scope": scope,
            "result": result,
        },
        ensure_ascii=False,
    )
    with open(_AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ──────────────────────────────────────────────────────────────────────
# MySQL 辅助
# ──────────────────────────────────────────────────────────────────────
def _mysql_engine():
    from sqlalchemy import create_engine

    sync_url = settings.DATABASE_URL.replace("+aiomysql", "+pymysql")
    return create_engine(sync_url, echo=False, future=True)


def _in_clause(items):
    if not items:
        return None, None
    placeholders = ",".join(f":p{i}" for i in range(len(items)))
    params = {f"p{i}": v for i, v in enumerate(items)}
    return placeholders, params


def _fetch_col(conn, sql, params=None):
    from sqlalchemy import text

    rows = conn.execute(text(sql), params or {}).fetchall()
    return [r[0] for r in rows]


def resolve_doc_ids(engine, user_uuid: str) -> set:
    """双口径反查该用户关联的 document id 集合（交叉取并集）。"""
    from sqlalchemy import text

    ids: set = set()
    with engine.connect() as conn:
        # 口径 A：上传者字段
        ids.update(_fetch_col(conn, "SELECT id FROM documents WHERE uploaded_by = :u", {"u": user_uuid}))
        # 口径 B：file_path 前缀匹配（MinIO 对象与本地回退双前缀）
        ids.update(
            _fetch_col(
                conn,
                "SELECT id FROM documents WHERE file_path LIKE :p1 OR file_path LIKE :p2",
                {"p1": f"original/{user_uuid}/%", "p2": f"local://original/{user_uuid}/%"},
            )
        )
    return ids


# MySQL 级联删除（先子后主），返回各表受影响行数
def mysql_delete_by_docs(engine, doc_ids: list) -> dict:
    from sqlalchemy import text

    if not doc_ids:
        return {}
    doc_ids = list(doc_ids)
    dph, dparams = _in_clause(doc_ids)
    counts: dict = {}

    with engine.begin() as conn:
        ann_ids = [
            r[0]
            for r in conn.execute(
                text(f"SELECT id FROM annotations WHERE document_id IN ({dph})"), dparams
            )
        ]
        page_ids = [
            r[0]
            for r in conn.execute(
                text(f"SELECT id FROM document_pages WHERE document_id IN ({dph})"), dparams
            )
        ]

        if ann_ids:
            aph, aparams = _in_clause(ann_ids)
            counts["annotation_versions"] = conn.execute(
                text(f"DELETE FROM annotation_versions WHERE annotation_id IN ({aph})"), aparams
            ).rowcount
            counts["annotation_comments"] = conn.execute(
                text(f"DELETE FROM annotation_comments WHERE annotation_id IN ({aph})"), aparams
            ).rowcount
        else:
            counts["annotation_versions"] = 0
            counts["annotation_comments"] = 0

        counts["annotations"] = conn.execute(
            text(f"DELETE FROM annotations WHERE document_id IN ({dph})"), dparams
        ).rowcount
        counts["tasks"] = conn.execute(
            text(f"DELETE FROM tasks WHERE document_id IN ({dph})"), dparams
        ).rowcount

        if page_ids:
            pph, pparams = _in_clause(page_ids)
            counts["document_elements"] = conn.execute(
                text(f"DELETE FROM document_elements WHERE page_id IN ({pph})"), pparams
            ).rowcount
        else:
            counts["document_elements"] = 0

        counts["document_pages"] = conn.execute(
            text(f"DELETE FROM document_pages WHERE document_id IN ({dph})"), dparams
        ).rowcount
        counts["documents"] = conn.execute(
            text(f"DELETE FROM documents WHERE id IN ({dph})"), dparams
        ).rowcount
    return counts


def mysql_clear_all(engine) -> dict:
    from sqlalchemy import text

    counts: dict = {}
    with engine.begin() as conn:
        for table in _MYSQL_TABLES_ORDERED:
            counts[table] = conn.execute(text(f"DELETE FROM {table}")).rowcount
    return counts


def mysql_count_paper_tables(engine, doc_ids: list) -> dict:
    from sqlalchemy import text

    if not doc_ids:
        return {t: 0 for t in _MYSQL_TABLES_ORDERED}
    doc_ids = list(doc_ids)
    dph, dparams = _in_clause(doc_ids)
    counts: dict = {}

    def _cnt(_conn, sql: str, params: dict) -> int:
        row = _conn.execute(text(sql), params).fetchone()
        return int(row[0]) if row else 0

    with engine.connect() as conn:
        counts["documents"] = _cnt(conn, f"SELECT count(*) FROM documents WHERE id IN ({dph})", dparams)
        counts["annotations"] = _cnt(conn, f"SELECT count(*) FROM annotations WHERE document_id IN ({dph})", dparams)
        counts["tasks"] = _cnt(conn, f"SELECT count(*) FROM tasks WHERE document_id IN ({dph})", dparams)
        counts["document_pages"] = _cnt(conn, f"SELECT count(*) FROM document_pages WHERE document_id IN ({dph})", dparams)
        counts["annotation_versions"] = _cnt(
            conn,
            f"SELECT count(*) FROM (SELECT id FROM annotations WHERE document_id IN ({dph})) a "
            "JOIN annotation_versions av ON av.annotation_id = a.id",
            dparams,
        )
        counts["annotation_comments"] = _cnt(
            conn,
            f"SELECT count(*) FROM (SELECT id FROM annotations WHERE document_id IN ({dph})) a "
            "JOIN annotation_comments ac ON ac.annotation_id = a.id",
            dparams,
        )
        counts["document_elements"] = _cnt(
            conn,
            f"SELECT count(*) FROM (SELECT id FROM document_pages WHERE document_id IN ({dph})) p "
            "JOIN document_elements e ON e.page_id = p.id",
            dparams,
        )
    return counts


def mysql_doc_exists(engine, filename: str, title: str):
    """按 file_path 后缀或 title 判断是否已入库，返回已存在 document_id 或 None。"""
    from sqlalchemy import text

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM documents WHERE file_path LIKE :fp OR title = :t LIMIT 1"),
            {"fp": f"%/{filename}", "t": title},
        ).fetchone()
        return row[0] if row else None


def mysql_doc_status(engine, doc_id: str):
    """查询指定文档的解析状态（documents.status）。"""
    from sqlalchemy import text

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status FROM documents WHERE id = :id"),
            {"id": doc_id},
        ).fetchone()
        return row[0] if row else None


# ──────────────────────────────────────────────────────────────────────
# Neo4j 辅助（asyncio 包装）
# ──────────────────────────────────────────────────────────────────────
def _run_neo4j(coro_factory):
    """在单一事件循环内执行 Neo4j 协程，结束时关闭 driver 并重置单例。

    Neo4jClient 为模块级单例且 driver 绑定创建时的事件循环；本脚本多处
    ``asyncio.run`` 各建新循环，跨循环复用旧 driver 会抛
    ``got Future attached to a different loop``，故每次运行后彻底释放。
    """
    from app.utils.neo4j_client import Neo4jClient

    async def _run():
        try:
            return await coro_factory()
        finally:
            try:
                await Neo4jClient().driver.close()
            except Exception:  # noqa: BLE001
                pass
            Neo4jClient._instance = None

    return asyncio.run(_run())


def _neo4j_count(query: str, params: dict = None):
    from app.utils.neo4j_client import Neo4jClient

    def _factory():
        return Neo4jClient().execute_query(query, params)

    rows = _run_neo4j(_factory)
    if not rows:
        return 0
    first = rows[0]
    if isinstance(first, dict):
        return int(list(first.values())[0]) if first else 0
    return int(first[0]) if first else 0


def neo4j_count_all() -> int:
    return _neo4j_count("MATCH (n) RETURN count(n) AS cnt")


def neo4j_count_by_docs(doc_ids: list) -> int:
    if not doc_ids:
        return 0
    total = 0
    for did in doc_ids:
        total += _neo4j_count("MATCH (n) WHERE $id IN n.source_document_ids RETURN count(n) AS cnt", {"id": did})
    total += _neo4j_count(
        "MATCH (n) WHERE (n:Document AND n.id IN $ids) OR (n:Chunk AND n.doc_id IN $ids) RETURN count(n) AS cnt",
        {"ids": list(doc_ids)},
    )
    return total


def neo4j_delete_by_docs(doc_ids: list) -> int:
    from app.utils.neo4j_client import Neo4jClient

    def _factory():
        return Neo4jClient().delete_nodes_by_doc(list(doc_ids))

    return _run_neo4j(_factory)


def neo4j_clear_all() -> int:
    from app.utils.neo4j_client import Neo4jClient

    def _factory():
        return Neo4jClient().execute_write("MATCH (n) DETACH DELETE n")

    _run_neo4j(_factory)
    return neo4j_count_all()


# ──────────────────────────────────────────────────────────────────────
# MinIO 辅助
# ──────────────────────────────────────────────────────────────────────
def _minio_client():
    from app.utils.minio_client import MinioClient

    return MinioClient()


# ──────────────────────────────────────────────────────────────────────
# 后端 HTTP 客户端（登录/上传/解析/全文/建图/清图）
# ──────────────────────────────────────────────────────────────────────
class ApiClient:
    def __init__(self, base: str, username: str, password: str):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self.token = None
        self.username = username
        self.password = password

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def _request(self, method: str, path: str, file_path: str = None, **kw):
        """统一请求入口：收到 401 时自动重新登录并重试一次。

        批量入库耗时可能超过 JWT 有效期（实测约 30 分钟），长跑任务须
        具备 token 自愈能力；``file_path`` 指定时每次发送前重开文件流
        （重试时原文件指针已读尽）。
        """

        def _send():
            headers = self._headers()
            if file_path:
                with open(file_path, "rb") as f:
                    return self.session.request(
                        method, f"{self.base}{path}", headers=headers,
                        files={"file": (os.path.basename(file_path), f, "application/pdf")},
                        **kw,
                    )
            return self.session.request(method, f"{self.base}{path}", headers=headers, **kw)

        kw.setdefault("timeout", 60)
        r = _send()
        if r.status_code == 401 and self.token:
            print("    [auth] token 失效，自动重新登录后重试")
            self.login()
            r = _send()
        return r

    def login(self):
        r = self.session.post(
            f"{self.base}/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        self.token = data.get("access_token")
        if not self.token:
            raise RuntimeError(f"登录未返回 access_token: {data}")
        return data

    def upload(self, path: str, title: str = None):
        r = self._request(
            "POST", "/documents/upload", file_path=path,
            data={"title": title} if title else None, timeout=120,
        )
        r.raise_for_status()
        return r.json()

    def parse(self, document_id: str, poll_steps: int = 24, step_wait: float = 5.0):
        r = self._request("POST", f"/documents/{document_id}/parse", timeout=60)
        r.raise_for_status()
        d = {}
        for _ in range(poll_steps):
            time.sleep(step_wait)
            d = self._request(
                "GET", f"/documents/{document_id}", timeout=30
            ).json()
            if d.get("status") in ("parsed", "failed"):
                return d.get("status"), d
        return "timeout", d

    def fulltext(self, document_id: str):
        r = self._request("GET", f"/documents/{document_id}/fulltext", timeout=60)
        r.raise_for_status()
        return r.json()

    def index_document(self, doc_id, doc_title, entities, relations, chunks):
        body = {
            "doc_id": doc_id,
            "doc_title": doc_title,
            "entities": entities,
            "relations": relations,
            "metadata": {"ingested_at": datetime.now().isoformat()},
            "chunks": chunks,
        }
        r = self._request(
            "POST", "/knowledge-graph/rag/index/document", json=body, timeout=120
        )
        return r.status_code, (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )

    def clear_graph(self):
        r = self._request("DELETE", "/knowledge-graph/rag/graph/clear", timeout=120)
        return r.status_code, (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )


# ──────────────────────────────────────────────────────────────────────
# 实体/关系抽取（复用后端 ExtractionService）
# ──────────────────────────────────────────────────────────────────────
def extract_entities_relations(text: str):
    try:
        os.environ.setdefault("NER_ENABLED", "false")
        os.environ.setdefault("RELATION_EXTRACTION_ENABLED", "false")
        os.environ.setdefault("ENTITY_LINKING_ENABLED", "false")

        from app.services.extraction_service import ExtractionService

        async def _run():
            svc = ExtractionService()
            ents = await svc.extract_entities(text)
            rels = await svc.extract_relations(text, ents)
            return ents, rels

        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        print(f"    [warn] ExtractionService 调用失败: {exc}")
        return [], []


# ──────────────────────────────────────────────────────────────────────
# 二次确认
# ──────────────────────────────────────────────────────────────────────
def confirm_or_abort(yes: bool, prompt: str) -> None:
    if yes:
        return
    answer = input(f"{prompt} (输入 yes 继续): ").strip().lower()
    if answer != "yes":
        print("已取消操作。")
        raise SystemExit(0)


# ──────────────────────────────────────────────────────────────────────
# 子命令实现
# ──────────────────────────────────────────────────────────────────────
def cmd_inventory(args) -> int:
    engine = _mysql_engine()
    minio = _minio_client()
    uuid = args.user_uuid
    doc_ids = resolve_doc_ids(engine, uuid)

    report = InventoryReport(
        started_at=datetime.now().isoformat(),
        user_uuid=uuid,
        doc_ids=sorted(doc_ids),
    )

    # 本地文件
    local_dir = os.path.join(_LOCAL_STORAGE_DIR, "original", uuid)
    if os.path.isdir(local_dir):
        report.local_files = sorted(os.listdir(local_dir))
    # MinIO 原始对象
    report.minio_objects = minio.list_objects(f"original/{uuid}/")
    # MinIO 图片对象
    img_objs: list[str] = []
    for did in doc_ids:
        img_objs.extend(minio.list_objects(f"images/{did}/"))
    report.minio_image_objects = sorted(img_objs)
    # MySQL 计数
    report.mysql_counts = mysql_count_paper_tables(engine, list(doc_ids))
    # Neo4j 计数
    report.neo4j_total_nodes = neo4j_count_all()
    report.neo4j_matched_nodes = neo4j_count_by_docs(list(doc_ids))

    out = write_report(report, args.out or default_report_path("inventory"))
    print(f"[inventory] 用户 {uuid} 关联 doc_id {len(doc_ids)} 个：{sorted(doc_ids)}")
    print(f"[inventory] 本地文件 {len(report.local_files)} 个、MinIO 原始对象 {len(report.minio_objects)} 个、图片对象 {len(report.minio_image_objects)} 个")
    print(f"[inventory] MySQL: {report.mysql_counts}")
    print(f"[inventory] Neo4j 总节点 {report.neo4j_total_nodes}、命中节点 {report.neo4j_matched_nodes}")
    print(f"[inventory] 报告已写入: {out}")
    audit_log("inventory", args.user or settings.ADMIN_USERNAME, f"user:{uuid}", "readonly")
    return 0


def cmd_delete_user(args) -> int:
    engine = _mysql_engine()
    minio = _minio_client()
    uuid = args.user_uuid
    doc_ids = resolve_doc_ids(engine, uuid)

    if not doc_ids and not minio.list_objects(f"original/{uuid}/"):
        print(f"[delete-user] 未发现用户 {uuid} 的任何数据，终止。")
        return 1

    report = DeleteReport(
        started_at=datetime.now().isoformat(),
        user_uuid=uuid,
        doc_ids=sorted(doc_ids),
    )

    # 二次确认（先清单后物理）
    print(f"[delete-user] 将删除用户 {uuid} 的 doc_id {len(doc_ids)} 个：{sorted(doc_ids)}")
    confirm_or_abort(
        args.yes,
        "确认删除该用户的本地文件、MinIO 对象、MySQL 级联记录与 Neo4j 节点？（不可逆）",
    )

    # 1 本地目录
    local_dir = os.path.join(_LOCAL_STORAGE_DIR, "original", uuid)
    if os.path.isdir(local_dir):
        report.deleted_local = len(os.listdir(local_dir))
        for name in os.listdir(local_dir):
            p = os.path.join(local_dir, name)
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except Exception as exc:  # noqa: BLE001
                report.failed.append(f"local:{name}:{exc}")
        try:
            os.rmdir(local_dir)
        except OSError:
            pass
    print(f"[delete-user] 本地删除 {report.deleted_local} 个文件")

    # 2 MinIO 原始对象 + 图片对象
    report.deleted_minio += minio.remove_objects(f"original/{uuid}/")
    for did in doc_ids:
        report.deleted_minio += minio.remove_objects(f"images/{did}/")
    print(f"[delete-user] MinIO 删除 {report.deleted_minio} 个对象")

    # 3 MySQL 级联
    report.deleted_mysql = mysql_delete_by_docs(engine, list(doc_ids))
    print(f"[delete-user] MySQL 删除: {report.deleted_mysql}")

    # 4 Neo4j
    report.deleted_neo4j = neo4j_delete_by_docs(list(doc_ids))
    print(f"[delete-user] Neo4j 删除 {report.deleted_neo4j} 个节点")

    out = write_report(report, args.out or default_report_path("delete_user"))
    print(f"[delete-user] 报告已写入: {out}")
    audit_log("delete-user", args.user or settings.ADMIN_USERNAME, f"user:{uuid}", f"docs={len(doc_ids)}")
    return 0


def cmd_clear_all(args) -> int:
    engine = _mysql_engine()
    minio = _minio_client()

    confirm_or_abort(
        args.yes,
        "确认全量清空 MinIO 论文对象、MySQL 论文七表与 Neo4j 全图？（不可逆，请先备份）",
    )

    report = ClearReport(started_at=datetime.now().isoformat())

    # 1 MinIO
    report.minio_removed = minio.remove_objects("original/") + minio.remove_objects("images/")
    print(f"[clear-all] MinIO 删除 {report.minio_removed} 个对象")

    # 2 MySQL 七表
    report.mysql_cleared = mysql_clear_all(engine)
    print(f"[clear-all] MySQL 清空: {report.mysql_cleared}")

    # 3 Neo4j 直连全图清空
    report.neo4j_cleared = neo4j_count_all()
    neo4j_clear_all()
    report.neo4j_after = neo4j_count_all()
    print(f"[clear-all] Neo4j 清空前 {report.neo4j_cleared} 节点、清空后 {report.neo4j_after} 节点")

    # 4 缓存失效（通过后端 HTTP 代理触发，best effort）
    if args.enable_http_cache:
        try:
            client = ApiClient(args.base, args.user or settings.ADMIN_USERNAME, args.password or settings.ADMIN_PASSWORD)
            client.login()
            code, _ = client.clear_graph()
            report.snapshot_invalidated = code == 200
        except Exception as exc:  # noqa: BLE001
            print(f"[clear-all] 后端缓存失效代理失败（可稍后重启后端刷新快照）: {exc}")

    out = write_report(report, args.out or default_report_path("clear_all"))
    print(f"[clear-all] 报告已写入: {out}")
    audit_log("clear-all", args.user or settings.ADMIN_USERNAME, "all", f"minio={report.minio_removed}")
    return 0


def cmd_ingest(args) -> int:
    directory = os.path.abspath(args.dir)
    pdfs = filter_pdfs(directory)
    if not pdfs:
        print(f"[ingest] 目录 {directory} 下未发现匹配 `^\\d{{3}}_*.pdf` 的 PDF。")
        return 1
    print(f"[ingest] 发现 {len(pdfs)} 个 PDF 待入库")

    # 加载断点报告
    resume_map: dict = {}
    if args.resume and os.path.isfile(args.resume):
        with open(args.resume, "r", encoding="utf-8") as f:
            prev = json.load(f)
        for rec in prev.get("records", []):
            if rec.get("success"):
                resume_map[rec.get("filename")] = rec

    client = ApiClient(args.base, args.user or settings.ADMIN_USERNAME, args.password or settings.ADMIN_PASSWORD)
    client.login()
    print("[ingest] 登录成功，开始批量入库")
    minio = _minio_client()

    report = IngestReport(started_at=datetime.now().isoformat(), dir=directory, total=len(pdfs))

    # MySQL 引擎用于去重检查（连接失败则仅依赖断点报告）
    engine = None
    if not args.force:
        try:
            engine = _mysql_engine()
        except Exception as exc:  # noqa: BLE001
            print(f"[ingest] MySQL 连接失败，跳过去重检查（仅依赖断点报告）: {exc}")

    for idx, pdf in enumerate(pdfs, 1):
        filename = os.path.basename(pdf)
        title = derive_title(filename)
        print("=" * 70)
        print(f"[{idx}/{len(pdfs)}] {filename}  (title={title})")

        if filename in resume_map and not args.force:
            rec = IngestRecord(filename=filename, title=title, success=True, error="resumed(skipped)")
            report.records.append(rec)
            report.skipped += 1
            print("    [skip] 断点报告已成功入库，跳过（--force 可重跑）")
            continue

        # MySQL 去重：file_path 后缀或 title 已存在则跳过（未完成解析的脏文档除外）
        if engine is not None and not args.force:
            try:
                dup_id = mysql_doc_exists(engine, filename, title)
                if dup_id:
                    dup_status = mysql_doc_status(engine, dup_id)
                    if dup_status == "parsed":
                        rec = IngestRecord(
                            filename=filename, title=title, document_id=dup_id,
                            success=True, error="dedup(skipped)",
                        )
                        report.records.append(rec)
                        report.skipped += 1
                        print(f"    [skip] 已存在 document_id={dup_id}，跳过（--force 可重跑）")
                        continue
                    # 命中 upload 成功但解析未完成的脏文档（如撞上后端 reload 窗口）：
                    # 清除旧记录后按全新文档重新入库，避免留下缺解析/缺图谱的残档
                    print(f"    [fix] 命中未完成解析的脏文档 {dup_id}(status={dup_status})，清除后重新入库")
                    mysql_delete_by_docs(engine, [dup_id])
                    minio.remove_objects(f"images/{dup_id}/")
                    neo4j_delete_by_docs([dup_id])
            except Exception as exc:  # noqa: BLE001
                print(f"    [warn] 去重检查失败（继续处理）: {exc}")

        rec = IngestRecord(filename=filename, title=title)
        try:
            # 1 上传
            doc = client.upload(pdf, title=title)
            rec.document_id = doc.get("id") or doc.get("document_id")
            print(f"    upload document_id={rec.document_id}")

            # 2 解析
            st, d = client.parse(rec.document_id)
            rec.parse_status = st
            print(f"    parse status={st}")
            if st != "parsed":
                rec.error = d.get("detail") or d.get("error_message") or f"parse status={st}"

            # 3 全文
            ft = client.fulltext(rec.document_id)
            text = flatten_fulltext(ft)
            print(f"    fulltext chars={len(text)}")

            # 4 抽取
            entities, relations = extract_entities_relations(text)
            entities = entities[:500]
            relations = relations[:300]
            rec.entity_count = len(entities)
            rec.relation_count = len(relations)
            print(f"    entities={len(entities)} relations={len(relations)}")

            # 5 建图
            code, _resp = client.index_document(
                rec.document_id, title, entities, relations, build_chunks(text)
            )
            print(f"    index HTTP={code}")

            rec.success = True
        except Exception as exc:  # noqa: BLE001
            rec.success = False
            rec.error = str(exc)
            print(f"    [ERROR] {exc}")

        report.records.append(rec)

    report.ok_count = sum(1 for r in report.records if r.success and r.error == "")
    report.fail_count = sum(1 for r in report.records if not r.success)

    out = write_report(report, args.out or default_report_path("ingest"))
    print("=" * 70)
    print(f"[ingest] 总计 {report.total} 篇：成功 {report.ok_count}、跳过 {report.skipped}、失败 {report.fail_count}")
    print(f"[ingest] 报告已写入: {out}")
    audit_log("ingest", args.user or settings.ADMIN_USERNAME, f"dir:{directory}", f"total={report.total},ok={report.ok_count}")
    return 0 if report.fail_count == 0 else 1


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="论文数据重置与切换运维脚本")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base", default="http://localhost:8000/api/v1")
    common.add_argument("--out", default=None, help="报告输出路径（默认 outputs/paper_data_switch_<cmd>_<ts>.json）")
    common.add_argument("--yes", action="store_true", help="跳过交互式二次确认")
    common.add_argument("--user", default=None, help="管理员用户名（默认取 config/backend.env）")
    common.add_argument("--password", default=None, help="管理员密码（默认取 config/backend.env）")

    p_inv = sub.add_parser("inventory", parents=[common], help="只读清单预演")
    p_inv.add_argument("--user-uuid", required=True, help="目标用户 UUID")

    p_del = sub.add_parser("delete-user", parents=[common], help="定向删除指定用户旧数据")
    p_del.add_argument("--user-uuid", required=True, help="目标用户 UUID")

    p_clr = sub.add_parser("clear-all", parents=[common], help="全量清空论文数据")
    p_clr.add_argument("--enable-http-cache", action="store_true", help="通过后端 HTTP 触发图谱快照缓存失效")

    p_ing = sub.add_parser("ingest", parents=[common], help="批量入库新 PDF")
    p_ing.add_argument("--dir", required=True, help="PDF 源目录（如 download_data/Paper）")
    p_ing.add_argument("--resume", default=None, help="断点报告路径（跳过已成功篇目）")
    p_ing.add_argument("--force", action="store_true", help="忽略断点/去重，强制重跑")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "inventory":
        return cmd_inventory(args)
    if args.command == "delete-user":
        return cmd_delete_user(args)
    if args.command == "clear-all":
        return cmd_clear_all(args)
    if args.command == "ingest":
        return cmd_ingest(args)
    parser.error(f"未知子命令: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())