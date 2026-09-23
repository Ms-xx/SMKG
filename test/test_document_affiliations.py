# -*- coding: utf-8 -*-
"""文档作者/机构结构化字段测试：模型列 + 取值回环。"""
from app.models.document import Document


def test_document_model_has_author_and_affiliation_columns():
    cols = {c.name for c in Document.__table__.columns}
    assert "authors" in cols
    assert "affiliations" in cols


async def test_document_affiliations_roundtrip(db):
    doc = Document(
        title="Attention Is All You Need",
        file_path="s3://documents/test.pdf",
        uploaded_by="u1",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        affiliations=["Google Brain", "mit.edu"],
    )
    db.add(doc)
    await db.flush()

    assert doc.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert doc.affiliations == ["Google Brain", "mit.edu"]
