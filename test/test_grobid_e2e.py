"""
步骤 13.5：GROBID 增强路径端到端验证（本机）
================================================
- 真实连本机 GROBID 容器（localhost:8070，Docker 镜像 lfoppiano/grobid:0.8.0）
- 对比「规则解析」与「规则解析 + GROBID 增强」的参考文献字段覆盖率
- 降级测试：禁用 GROBID / 关 endpoint 时返回原列表、零长阻塞

产物：outputs/grobid_eval.json（脚本直接以 backend 包运行）
运行：cd backend && python ../test/test_grobid_e2e.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings  # noqa: E402
from app.services.reference_service import (  # noqa: E402
    enhance_references_with_grobid,
    grobid_available,
    reference_service,
)

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


def field_fill_count(refs):
    """统计 references 中各字段非空的条目数。"""
    counts = {f: sum(1 for r in refs if r.get(f)) for f in ("doi", "volume", "issue", "pages", "year", "authors", "title", "journal")}
    return counts


def _pick_pdf():
    """优先选择项目内真实 arXiv 论文 PDF（含参考文献），回退任一候选。"""
    candidates = [
        r"d:\work\VSCodeWork\LX\backend\storage\uploads\original\462111b8-37f5-11f1-98d0-b025aa39c5bf\YOLOv1.pdf",
        r"d:\work\VSCodeWork\LX\outputs\samples\long_2005.14165.pdf",
        r"d:\work\VSCodeWork\LX\download_data\DocBank\DocBank_samples\DocBank_samples\10.tar_1701.04170.gz_TPNL_afterglow_evo_arxiv_g360_v2.pdf",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def main():
    pdf = _pick_pdf()
    print(f"PDF = {pdf}")
    report = {"pdf": pdf, "rules": {}, "grobid": {}, "degradation": {}, "notes": []}

    if not pdf:
        report["notes"].append("未找到可用本地 PDF，跳过规则/GROBID 对比")
        json.dump(report, open(os.path.join(OUTPUT_DIR, "grobid_eval.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("无法执行，见 grobid_eval.json")
        return

    # 规则基线
    refs_rule = reference_service.extract_references(pdf) or []
    report["rules"]["count"] = len(refs_rule)
    report["rules"]["field_fill"] = field_fill_count(refs_rule)

    # GROBID 增强：直接改 settings 开关/端点（grobid_available 在调用时读取）
    settings.GROBID_ENABLED = True
    settings.GROBID_ENDPOINT = "http://localhost:8070"
    t0 = time.time()
    refs_enh = enhance_references_with_grobid(refs_rule, pdf_path=pdf)
    dt = time.time() - t0
    report["grobid"]["enabled"] = grobid_available()
    report["grobid"]["count"] = len(refs_enh)
    report["grobid"]["elapsed_s"] = round(dt, 3)
    report["grobid"]["field_fill"] = field_fill_count(refs_enh)
    report["grobid"]["new_fields_same_order"] = refs_enh and all(
        e.get("index") == r.get("index") for r, e in zip(refs_rule, refs_enh)
    )
    report["grobid"]["got_new_field"] = count_new_fields(refs_rule, refs_enh)

    # 降级：关闭 GROBID 后再增强应原样返回
    settings.GROBID_ENABLED = False
    t1 = time.time()
    degraded = enhance_references_with_grobid(refs_rule, pdf_path=pdf)
    dt1 = time.time() - t1
    report["degradation"]["disabled_returns_original"] = degraded == refs_rule
    report["degradation"]["disabled_elapsed_s"] = round(dt1, 3)

    # 降级：endpoint 配置为不可达端口（不应阻塞）
    settings.GROBID_ENABLED = True
    settings.GROBID_ENDPOINT = "http://localhost:9999"
    t2 = time.time()
    degraded2 = enhance_references_with_grobid(refs_rule, pdf_path=pdf)
    dt2 = time.time() - t2
    report["degradation"]["unreachable_returns_original"] = degraded2 == refs_rule
    report["degradation"]["unreachable_elapsed_s"] = round(dt2, 3)

    # 复位
    settings.GROBID_ENABLED = False
    settings.GROBID_ENDPOINT = ""

    out = os.path.join(OUTPUT_DIR, "grobid_eval.json")
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def count_new_fields(rule, enh):
    added = 0
    for r, e in zip(rule, enh):
        for f in ("doi", "volume", "issue", "pages", "year", "journal", "title", "authors"):
            if not r.get(f) and e.get(f):
                added += 1
    return added


if __name__ == "__main__":
    main()