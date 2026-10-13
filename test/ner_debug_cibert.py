# -*- coding: utf-8 -*-
"""排查 moulds/scibert 抽出0实体的原因：模型是否真能分到非O标签，以及 pipeline 参数。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.core.config import settings
import numpy as np

from transformers import AutoTokenizer, AutoModelForTokenClassification

src = settings.NER_MODEL_PATH
print("source:", src)
tok = AutoTokenizer.from_pretrained(src)
model = AutoModelForTokenClassification.from_pretrained(src)
print("labels:", sorted(model.config.id2label.items()))
print("id2label keys count:", len(model.config.id2label))

text = "Methylammonium lead iodide (MAPbI3) perovskite solar cells."
inputs = tok(text, return_tensors="pt")
print("input_ids:", tok.convert_ids_to_tokens(inputs["input_ids"][0]))
with __import__("torch").no_grad():
    out = model(**inputs)
    logits = out.logits[0]
    preds = logits.argmax(-1)
    probs = __import__("torch").softmax(logits, -1)
    for t, p, prob in zip(tok.convert_ids_to_tokens(inputs["input_ids"][0]), preds.tolist(), probs):
        label = model.config.id2label.get(str(p), model.config.id2label.get(p, "?"))
        print(f"  token={t!r:<20} pred={label:<18} conf={float(prob[p]):.3f}")