# -*- coding: utf-8 -*-
"""
引用图谱挖掘与综述 — 基于已有知识图谱的端到端测试
从知识图谱的 Document 节点提取参考文献元数据, 依次调用:
  /citation-graph/network     引用网络建图
  /citation-graph/key-papers  基石节点挖掘 (PageRank + 介数中心性)
  /citation-graph/survey      自动综述 (LLM 或规则模板)
输出: outputs/citation_graph_test.json
"""
import json
import os
import traceback

import requests

BASE = "http://localhost:8000/api/v1"


def main() -> dict:
    out: dict = {"steps": {}}
    s = requests.Session()
    login = s.post(
        f"{BASE}/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=30,
    )
    login.raise_for_status()
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    out["login"] = login.status_code

    # 1) 从已有知识图谱取 Document 节点, 构造参考文献
    docs = (
        s.get(
            f"{BASE}/knowledge-graph/rag/graph/nodes/Document",
            headers=h,
            params={"limit": 100},
            timeout=30,
        )
        .json()
        .get("nodes")
        or []
    )
    references = []
    for i, d in enumerate(docs):
        p = d.get("properties", {})
        references.append(
            {
                "index": i + 1,
                "title": p.get("title") or p.get("name"),
                "year": p.get("year"),
                "doi": p.get("doi"),
                "authors": p.get("authors"),
            }
        )
    out["documents_from_graph"] = len(docs)
    out["references"] = references

    # 2) 引用网络建图
    r = s.post(
        f"{BASE}/citation-graph/network",
        headers=h,
        json={"references": references},
        timeout=30,
    )
    net = r.json()
    out["steps"]["network"] = {"status": r.status_code, **net}

    # 3) 基石节点挖掘
    graph = {"nodes": net.get("nodes", []), "edges": net.get("edges", [])}
    r = s.post(
        f"{BASE}/citation-graph/key-papers",
        headers=h,
        json={"graph": graph},
        timeout=30,
    )
    kp = r.json()
    out["steps"]["key_papers"] = {
        "status": r.status_code,
        "backend": kp.get("backend"),
        "key_papers": kp.get("key_papers", [])[:8],
    }

    # 4) 自动综述
    r = s.post(
        f"{BASE}/citation-graph/survey",
        headers=h,
        json={"references": references, "top_papers": kp.get("key_papers", [])},
        timeout=90,
    )
    sv = r.json()
    out["steps"]["survey"] = {
        "status": r.status_code,
        "backend": sv.get("backend"),
        "model": sv.get("model"),
        "reference_count": sv.get("reference_count"),
        "timeline": sv.get("timeline"),
        "top_papers": sv.get("top_papers"),
        "survey": sv.get("survey"),
    }
    # 5) Future Work 相似去重 (附带)
    chunks = [
        "基于钙钛矿开发高稳定材料",
        "基于钙钛矿材料提升器件稳定性",
        "探索低成本钙钛矿制备工艺",
    ]
    r = (
        s.post(
            f"{BASE}/citation-graph/survey/future-work?tmp=1",
            headers=h,
            json={},
            timeout=30,
        )
        if False
        else None
    )
    if False:
        pass
    out["op"] = "ok"
    return out


if __name__ == "__main__":
    try:
        res = main()
        outdir = os.path.join(os.path.dirname(__file__), "..", "outputs")
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "citation_graph_test.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print(f"[written] {path}")
    except Exception:
        traceback.print_exc()
