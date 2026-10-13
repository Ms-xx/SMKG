# -*- coding: utf-8 -*-
"""创新点A 服务级端到端：取真实英文论文摘要，走 ExtractionService.extract_entities
（NER→图库回退合并），确认英文文本产出非0实体（这正是 graph_tasks 构建图谱时依据的元素抽取路径）。
"""
from __future__ import annotations
import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from sqlalchemy import select, func
from app.core.database import get_db_context
from app.models.document import Document, DocumentPage, DocumentElement
from app.services.extraction_service import ExtractionService

def _gather_text(doc_id: str) -> str:
    with get_db_context() as db:
        pages = db.execute(
            select(DocumentPage).where(DocumentPage.document_id == doc_id).limit(10)
        ).scalars().all()
        parts = []
        for page in pages:
            els = db.execute(
                select(DocumentElement).where(DocumentElement.page_id == page.id)
            ).scalars().all()
            for el in els:
                if el.element_type in ("text", "paragraph", "title") and el.content:
                    parts.append(el.content)
    return " ".join(parts)[:4000]

def main():
    with get_db_context() as db:
        row = db.execute(select(Document).limit(1)).scalar_one_or_none()
    if row is None:
        print("no doc found")
        sys.exit(1)
    text = _gather_text(row.id)
    if len(text) < 30:
        text = (row.title or "") + " " + (row.abstract or "")
    print("DOC:", row.id, "|", row.title)
    print("TEXT_LEN:", len(text))

    srv = ExtractionService()
    # ExtractionService.extract_entities 是 async；用单行事件循环执行
    import asyncio
    entities = asyncio.run(srv.extract_entities(text))

    # 仅保留英文科学实体（去掉中文规则残留：过滤全部非 ASCII 文本实体）
    entities = [e for e in entities if e.get("text") and all(ord(c) < 128 for c in e["text"])]
    uniq = {}
    for e in entities:
        uniq.setdefault((e["type"], e["text"].lower()), e)
    unique_entities = list(uniq.values())
    from collections import Counter
    by_type = Counter(e["type"] for e in unique_entities)

    result = {
        "doc_id": row.id,
        "title": row.title,
        "abstract_len": len(text),
        "extracted_raw": len(entities),
        "unique_entities": len(unique_entities),
        "node_types": dict(by_type),
    }
    out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs", "innovA_abstract_e2e.json"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("PASS" if len(unique_entities) > 0 else "FAIL")

if __name__ == "__main__":
    main()