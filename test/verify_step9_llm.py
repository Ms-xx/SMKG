# -*- coding: utf-8 -*-
"""步骤 9 真实 LLM 验证：翻译 + 生成。从 backend 目录运行。"""
import json
import urllib.request


def chat(prompt):
    payload = json.dumps(
        {
            "model": "qwen/qwen3-4b-2507",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:1234/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


print("== 9.1 翻译 ==")
print(chat("将以下英文翻译为中文，仅输出译文：\nGraph neural networks enable materials property prediction."))
print("== 9.2 生成 ==")
print(chat("写一段关于石墨烯电池应用的 100 字中文学术引言。"))