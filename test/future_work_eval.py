# -*- coding: utf-8 -*-
"""步骤 22 真实评测：在含时间线的语料上跑 Future Work，判定已解决/待探索，产 outputs/future_work_scan.json。"""
import json
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.future_work_service import scan_future_work  # noqa: E402

# 工序语料（含未来工作声明 + 1 条被后续论文解决的 idea）
DOCS = [
    {
        "document_id": "d1",
        "title": "Transformer Baseline",
        "year": 2017,
        "authors": ["Vaswani"],
        "references": [],
        "pages": [
            {
                "page_number": 1,
                "text": (
                    "We introduce the sequence transduction Transformer. Future work: we plan to study "
                    "sparse attention to reduce quadratic cost and to extend the model to long documents."
                ),
            }
        ],
    },
    {
        "document_id": "d2",
        "title": "Sparse Attention Longformer",
        "year": 2020,
        "authors": ["Vaswani", "Beltagy"],
        "references": [{"title": "Transformer Baseline"}],
        "pages": [
            {
                "page_number": 1,
                "text": (
                    "Longformer overcomes the quadratic cost of standard attention using sparse attention "
                    "patterns, enabling long-document processing. We solve the sparse attention scaling for "
                    "long documents."
                ),
            }
        ],
    },
    {
        "document_id": "d3",
        "title": "BERT",
        "year": 2019,
        "authors": ["Devlin"],
        "references": [],
        "pages": [
            {
                "page_number": 1,
                "text": (
                    "We present BERT. As future research, we will investigate cross-lingual pre-training "
                    "and multilingual representations."
                ),
            }
        ],
    },
    {
        "document_id": "d4",
        "title": "XLM Multilingual",
        "year": 2019,
        "authors": ["Conneau"],
        "references": [{"title": "BERT"}],
        "pages": [
            {
                "page_number": 1,
                "text": (
                    "We address cross-lingual pre-training and we improve multilingual representations "
                    "with XLM, a cross-lingual language model."
                ),
            }
        ],
    },
    {
        "document_id": "d5",
        "title": "Vision Transformer (ViT)",
        "year": 2021,
        "authors": ["Dosovitskiy"],
        "references": [],
        "pages": [
            {
                "page_number": 1,
                "text": (
                    "We apply the Transformer directly to image patches. In future work we aim to scale "
                    "to video understanding and object detection."
                ),
            }
        ],
    },
]

scan = scan_future_work(DOCS)


def spot_check(idea_count, excluded, candidates):
    rows = []
    for i in scan["excluded"] + scan["candidates"]:
        rows.append(
            {
                "document_id": i["document_id"],
                "title": i["title"],
                "year": i["year"],
                "idea": i["idea"][:80],
                "resolved": i["resolved"],
                "confidence": i["confidence"],
                "resolved_by": i["resolved_by"],
                "snippet": (i["snippet"] or "")[:120],
            }
        )
    return rows


all_items = scan["excluded"] + scan["candidates"]
rows = spot_check(len(all_items), scan["excluded"], scan["candidates"])

# 人工抽查合理性要点：
# 1) d1 稀疏注意力 idea 被 d2（更晚+共享作者+CITES）解决
d1_resolved = any(i["document_id"] == "d1" and i["resolved"] for i in all_items)
# 2) d3 跨语言 idea 被 d4 解决（同年 2019 不满足"年份更晚"→ 依赖无边低置信；此处 d4 year==2019 不晚于 d3，应判定未解决或低置信）
#    d3 year=2019, d4 year=2019 → 不晚于，被过滤，所以 d3 unresolved
d3_unresolved = next((i for i in all_items if i["document_id"] == "d3"), None)
# 3) d5 视频 idea 无后文 → 待探索
d5_candidate = any(i["document_id"] == "d5" and not i["resolved"] for i in all_items)
# 4) 无年份/无边降级：d2 无边时按无边降级（此处有边）
has_confidence = all(i["confidence"] >= 0.0 for i in all_items)

report = {
    "step": 22,
    "title": "Future Work 前沿探索 - 真实评测",
    "backend": scan["backend"],
    "idea_count": scan["idea_count"],
    "excluded_count": scan["excluded_count"],
    "candidate_count": scan["candidate_count"],
    "time_buckets": scan["time_buckets"],
    "items": rows,
    "manual_rationale_checks": {
        "d1_sparse_attention_resolved_by_d2_with_edge": bool(d1_resolved),
        "d3_lingual_idea_not_resolved_by_same_year_d4": bool(
            not d3_unresolved or not d3_unresolved["resolved"]
        ),
        "d5_video_idea_kept_as_candidate": bool(d5_candidate),
        "all_confidence_recorded": bool(has_confidence),
    },
    "conclusion": (
        f"扫描 {scan['idea_count']} 条 Future Work，{scan['excluded_count']} 条已被后续论文解决（自动排除），"
        f"{scan['candidate_count']} 条待探索。时间线年份桶 {len(scan['time_buckets'])} 个。"
        "每条 idea 均带 提出年份 + 是否已解决 + resolved_by + 原文 snippet 溯源。"
    ),
}

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "future_work_scan.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(
    "idea_count",
    scan["idea_count"],
    "excluded",
    scan["excluded_count"],
    "candidates",
    scan["candidate_count"],
)
print("d1_resolved", d1_resolved, "d5_candidate", d5_candidate)
print("wrote", path)
sys.exit(0 if d1_resolved and d5_candidate else 1)
