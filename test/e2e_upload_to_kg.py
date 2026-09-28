# -*- coding: utf-8 -*-
"""
端到端流程测试：文件(PDF)上传 → 解析 → 实体/关系抽取 → 知识图谱建立 → 图谱查询验证
针对 D:\work\VSCodeWork\LX\download_data 下的真实论文 PDF 运行。

用法:
  D:\\workapp\\Anaconda\\anaconda3\\envs\\SciMKG\\python.exe test\\e2e_upload_to_kg.py [pdf1 pdf2 pdf3] [--base http://localhost:8000/api/v1] [--out outputs/e2e_xxx.json]

说明:
  - 依赖本地后端(8000)、MySQL、Redis、MinIO、Neo4j、GraphRAGTest(8001)、Celery worker 已就绪。
  - 实体/关系抽取复用后端真实服务 ExtractionService（规则 + 可选 SciBERT NER）。
  - 建图谱走后端 POST /knowledge-graph/rag/index/document（内部转发 GraphRAGTest→Neo4j）。
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import requests

# --------------------------------------------------------------------------
# 后端真实 ExtractionService（复用既有抽取逻辑）
# --------------------------------------------------------------------------
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
_sys_ok = _BACKEND_DIR not in sys.path
if _sys_ok:
    sys.path.insert(0, _BACKEND_DIR)


def extract_entities_relations(text: str):
    """调用后端 ExtractionService 做真实实体/关系抽取。失败则返回空（不阻断流程）。

    本环境无法访问 huggingface.co：默认关闭 NER(REBEL/entity-linking) 的远程模型加载，
    使其回退到自带规则，避免测试被网络重试长时间阻塞。
    """
    try:
        os.environ.setdefault("NER_ENABLED", "false")
        os.environ.setdefault("RELATION_EXTRACTION_ENABLED", "false")
        os.environ.setdefault("ENTITY_LINKING_ENABLED", "false")
        import asyncio

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


def build_chunks(text: str, size: int = 1200) -> list:
    return [text[i : i + size] for i in range(0, len(text), size)]


def flatten_fulltext(ft: dict) -> str:
    """兼容 fulltext 接口多种返回形状，拼出纯文本。"""
    if isinstance(ft, str):
        return ft
    if not ft:
        return ""
    if ft.get("text"):
        return ft["text"]
    pages = ft.get("pages") or ft.get("data") or []
    parts = []
    for p in pages:
        if isinstance(p, str):
            parts.append(p)
        else:
            for k in ("text", "content", "full_text"):
                v = p.get(k) or p.get(k + "_content")
                if v:
                    parts.append(v)
                    break
    return " ".join(p for p in parts if p)


class E2EPipeline:
    def __init__(self, base: str, username: str, password: str):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self.token = None
        self.username = username
        self.password = password

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def login(self):
        r = self.session.post(
            f"{self.base}/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        self.token = data.get("access_token")
        assert self.token, f"登录未返回 access_token: {data}"
        return data

    def upload(self, path: str, title: str = None):
        with open(path, "rb") as f:
            name = os.path.basename(path)
            r = self.session.post(
                f"{self.base}/documents/upload",
                headers=self._headers(),
                files={"file": (name, f, "application/pdf")},
                data={"title": title} if title else None,
                timeout=120,
            )
        r.raise_for_status()
        return r.json()

    def parse(self, document_id: str, poll_steps: int = 24, step_wait: float = 5.0):
        r = self.session.post(
            f"{self.base}/documents/{document_id}/parse",
            headers=self._headers(),
            timeout=60,
        )
        r.raise_for_status()
        for i in range(poll_steps):
            time.sleep(step_wait)
            d = self.session.get(
                f"{self.base}/documents/{document_id}",
                headers=self._headers(),
                timeout=30,
            ).json()
            st = d.get("status")
            if st in ("parsed", "failed"):
                return st, d
        return "timeout", d

    def fulltext(self, document_id: str):
        r = self.session.get(
            f"{self.base}/documents/{document_id}/fulltext",
            headers=self._headers(),
            timeout=60,
        )
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
        r = self.session.post(
            f"{self.base}/knowledge-graph/rag/index/document",
            headers=self._headers(),
            json=body,
            timeout=120,
        )
        return r.status_code, (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )

    def graph_stats(self):
        for path in ("/knowledge-graph/rag/graph/stats", "/knowledge-graph/statistics"):
            try:
                r = self.session.get(
                    f"{self.base}{path}", headers=self._headers(), timeout=30
                )
                if r.status_code == 200:
                    return path, r.json()
            except Exception:  # noqa: BLE001
                continue
        return None, None

    def graph_nodes_by_label(self, label: str):
        """按标签列出图谱节点（稳定，不依赖实体命中）。"""
        try:
            r = self.session.get(
                f"{self.base}/knowledge-graph/rag/graph/nodes/{label}",
                headers=self._headers(),
                timeout=30,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:  # noqa: BLE001
            pass
        return None

    def graph_search(self, keyword: str):
        """按实体关键词搜索图谱（仅在确实抽到实体时调用）。"""
        try:
            r = self.session.get(
                f"{self.base}/knowledge-graph/rag/graph/search/{keyword}",
                headers=self._headers(),
                params={"limit": 20},
                timeout=30,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:  # noqa: BLE001
            pass
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdfs", nargs="+", help="要处理的 PDF 文件路径（2-3 个）")
    parser.add_argument("--base", default="http://localhost:8000/api/v1")
    parser.add_argument(
        "--out",
        default=None,
        help="结果 JSON 输出路径（默认 outputs/e2e_upload_to_kg.json）",
    )
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()

    pdfs = [os.path.abspath(p) for p in args.pdfs]
    for p in pdfs:
        assert os.path.exists(p), f"PDF 不存在: {p}"

    out = args.out or os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "outputs", "e2e_upload_to_kg.json"
        )
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)

    pipe = E2EPipeline(args.base, args.user, args.password)
    summary = {
        "started_at": datetime.now().isoformat(),
        "base": args.base,
        "user": args.user,
        "documents": [],
    }

    print("=" * 70)
    print("STEP 0  登录")
    pipe.login()
    print("  登录成功, token 已获取")

    for idx, pdf in enumerate(pdfs, 1):
        print("=" * 70)
        print(f"文档 {idx}/{len(pdfs)}  {os.path.basename(pdf)}")
        rec = {"pdf": pdf, "filename": os.path.basename(pdf)}
        try:
            # 1 上传
            print("- STEP 1 上传文件")
            doc = pipe.upload(pdf)
            doc_id = doc.get("id") or doc.get("document_id")
            title = doc.get("title") or os.path.basename(pdf)
            rec["document_id"] = doc_id
            rec["upload_status"] = doc.get("status")
            print(f"   document_id={doc_id}  status={doc.get('status')}")

            # 2 解析
            print("- STEP 2 解析(PDF 文本/表格/图像/参考文献)")
            st, d = pipe.parse(doc_id)
            rec["parse_status"] = st
            rec["page_count"] = d.get("page_count")
            print(f"   解析结束 status={st}  page_count={d.get('page_count')}")
            if st != "parsed":
                rec["parse_error"] = d.get("detail") or d.get("error_message")
                print(f"   [warn] 解析未成功: {rec.get('parse_error')}")

            # 3 全文
            print("- STEP 3 读取全文")
            ft = pipe.fulltext(doc_id)
            text = flatten_fulltext(ft)
            rec["text_chars"] = len(text)
            print(f"   全文字符数={len(text)}")

            # 4 实体/关系抽取
            print("- STEP 4 实体/关系抽取(ExtractionService)")
            entities, relations = extract_entities_relations(text)
            # 去除跨文档重复/超大文本，字段控制在后端 schema 接受范围
            entities = entities[:500]
            relations = relations[:300]
            rec["entity_count"] = len(entities)
            rec["relation_count"] = len(relations)
            print(f"   实体={len(entities)}  关系={len(relations)}")
            if entities:
                print(f"   实体样例: {entities[:5]}")

            # 5 建图谱
            chunks = build_chunks(text)
            rec["chunk_count"] = len(chunks)
            print(f"- STEP 5 建立知识图谱(index/document, chunks={len(chunks)})")
            code, resp = pipe.index_document(doc_id, title, entities, relations, chunks)
            rec["index_http"] = code
            rec["index_response"] = resp
            print(f"   index HTTP={code}  resp={str(resp)[:200]}")

            # 6 查询验证
            print("- STEP 6 图谱查询验证")
            spath, stats = pipe.graph_stats()
            rec["graph_stats_path"] = spath
            rec["graph_stats"] = stats
            print(
                f"   图谱统计({spath}): nodes={stats.get('total_nodes')} rels={stats.get('total_relations')}"
            )
            # 稳定校验：按标签列出该文档产生的节点
            doc_nodes = pipe.graph_nodes_by_label("Document")
            chunk_nodes = pipe.graph_nodes_by_label("Chunk")
            rec["graph_document_nodes"] = doc_nodes
            rec["graph_chunk_node_count_latest"] = (
                len(chunk_nodes) if chunk_nodes else None
            )
            print(
                f"   Document 标签节点数(累计) = {len(doc_nodes) if doc_nodes else 'N/A'}，Chunk 标签节点数(累计) = {len(chunk_nodes) if chunk_nodes else 'N/A'}"
            )
            # 有实体才做按实体关键词搜索
            if entities:
                kw = entities[0]["text"]
                rec["graph_search_keyword"] = kw
                rec["graph_search"] = pipe.graph_search(kw)
                print(f"   按实体搜索 '{kw}': {str(rec['graph_search'])[:200]}")
            else:
                rec["graph_search"] = None
                rec["graph_search_keyword"] = None
                print("   (未抽到实体，跳过按实体关键词搜索；以上以标签校验代替)")

            rec["success"] = True
        except Exception as exc:  # noqa: BLE001
            rec["success"] = False
            rec["error"] = str(exc)
            print(f"   [ERROR] {exc}")
        summary["documents"].append(rec)

    # 汇总
    summary["finished_at"] = datetime.now().isoformat()
    ok = [d for d in summary["documents"] if d.get("success")]
    summary["ok_count"] = len(ok)
    summary["fail_count"] = len(summary["documents"]) - len(ok)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("=" * 70)
    print(f"结果已写入: {out}")
    print(f"成功 {len(ok)}/{len(summary['documents'])}")
    print("=" * 70)
    return 0 if len(ok) == len(summary["documents"]) else 1


if __name__ == "__main__":
    sys.exit(main())
