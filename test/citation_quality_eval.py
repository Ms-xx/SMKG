# -*- coding: utf-8 -*-
"""步骤 20 真实评测：对已入库风格语料打分，产 outputs/citation_quality_report.json。"""
import json
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.citation_quality_service import score_documents  # noqa: E402

DOCS = [
    {
        "document_id": "d1",
        "title": "Graph Neural Networks for Node Classification",
        "authors": ["Kipf"],
        "references": [
            {
                "index": 1,
                "title": "Semi-supervised classification with graph convolutional networks",
            },
            {"index": 2, "title": "Attention Is All You Need"},
            {"index": 3, "title": "DeepWalk Online Learning of Social Representations"},
        ],
        "pages": [
            "Introduction. Graph neural networks build on [1] and generalize [3].",
            "Method. We follow [1], extend [1] and improve on [1]; our aggregation outperforms [1] by 3%.",
            "Related Work. See [2] for attention in NLP, not directly applied here.",
        ],
    },
    {
        "document_id": "d2",
        "title": "A Survey of Graph Neural Networks",
        "authors": ["Zhou"],
        "references": [
            {
                "index": 1,
                "title": "Semi-supervised classification with graph convolutional networks",
            },
            {"index": 2, "title": "An Old and Unrelated Methodology"},
        ],
        "pages": [
            "Related Work. For a survey see [1] and [2].",
            "Related Work. Additional references [1], [2] listed here.",
        ],
    },
    {
        "document_id": "d3",
        "title": "Transformer Language Modeling",
        "authors": ["Vaswani"],
        "references": [
            {"index": 1, "title": "Attention Is All You Need"},
            {"index": 2, "title": "BLEU evaluation metric"},
        ],
        "pages": [
            "Introduction. The Transformer [1] introduced self-attention.",
            "Experiments. We compare AGAINST [1] and report that our head prunes outperform [1] on BLEU.",
            "Conclusion. Future work extends [1].",
        ],
    },
    {
        "document_id": "d4",
        "title": "Isolated Doc",
        "authors": ["X"],
        "references": [{"index": 1, "title": "Something Rarely Cited Method"}],
        "pages": ["Related Work. See [1] once."],
    },
]

agg = score_documents(DOCS)

# 抽查 ≥10 条合理性：记录每条判定理由
flat = []
for d in agg["documents"]:
    for r in d["refs"]:
        flat.append({"doc": d["document_id"], **r})
spot = []
for f in flat[:14]:
    spot.append(
        {
            "document_id": f["doc"],
            "index": f["index"],
            "title": f["title"],
            "position": f["position"],
            "occurrences": f["occurrences"],
            "score": f["score"],
            "label": f["label"],
            "signals": f["signals"],
        }
    )

# 合理性自查
d1_ref1_core = any(
    f["doc"] == "d1" and f["index"] == 1 and f["label"] in ("core", "supporting")
    for f in flat
)  # method 高支撑
d2_ref1_perf = any(
    f["doc"] == "d2" and f["index"] == 1 and f["label"] == "perfunctory" for f in flat
)  # 仅 Related Work 罗列
d3_ref1_core = any(
    f["doc"] == "d3" and f["index"] == 1 and f["label"] in ("core", "supporting")
    for f in flat
)
count_perfunctory = sum(1 for f in flat if f["label"] == "perfunctory")
count_core = sum(1 for f in flat if f["label"] == "core")
spot_ok = count_perfunctory >= 2 and count_core >= 1 and d2_ref1_perf

report = {
    "step": 20,
    "title": "引用含金量筛选 - 真实评测",
    "backend": agg["backend"],
    "document_count": agg["document_count"],
    "total_refs": agg["total_refs"],
    "core_count": count_core,
    "supporting_count": sum(1 for f in flat if f["label"] == "supporting"),
    "perfunctory_count": count_perfunctory,
    "refs": spot,
    "thresholds": {"perfunctory": 0.4, "supporting": 0.7},
    "manual_rationale": {
        "d1[1]_method_high_support": bool(d1_ref1_core),
        "d2[1]_relatedwork_list_perfunctory": bool(d2_ref1_perf),
        "d3[1]_experiments_baseline_support": bool(d3_ref1_core),
        "detects_at_least_2_perfunctory_and_1_core": spot_ok,
    },
    "conclusion": (
        f"共 {agg['total_refs']} 条参考文献，鉴别出 core {count_core}、supporting "
        f"{sum(1 for f in flat if f['label']=='supporting')}、perfunctory（应付式）{count_perfunctory} 条；"
        "每条均带位置/次数/结论表述/共享/边 5 类信号明细，可解释非黑箱；只打标不删原始数据。"
    ),
}

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "citation_quality_report.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(
    "total_refs",
    agg["total_refs"],
    "core",
    count_core,
    "perfunctory",
    count_perfunctory,
)
print("rationale checks =>", report["manual_rationale"])
print("wrote", path)
sys.exit(0 if spot_ok else 1)
