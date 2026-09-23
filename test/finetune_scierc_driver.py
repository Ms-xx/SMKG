# -*- coding: utf-8 -*-
"""
步骤 1.2 微调驱动：登录取 token -> 读 SciERC 转换后的真实训练样本 -> 调 /retrain/finetune
用法（SciMKG 环境）:
    python finetune_scierc_driver.py [n_samples] [epochs]
t 可调: 默认 n_samples=120, epochs=1（CPU LoRA 验证规模，避免过久）
"""
from __future__ import annotations

import json
import os
import sys

import requests

BASE = "http://localhost:8000/api/v1"
SAMPLES = r"D:\work\VSCodeWork\LX\download_data\SciERC\data\samples\train.jsonl"


def login() -> str:
    r = requests.post(
        f"{BASE}/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def load_subset(n: int) -> list[dict]:
    out: list[dict] = []
    with open(SAMPLES, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            out.append(json.loads(ln))
            if len(out) >= n:
                break
    return out


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    records = load_subset(n)
    print(f"loaded {len(records)} samples; epochs={epochs}")

    token = login()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "model_name": "ner",
        "records": records,
        "trigger_reason": "scierc-real-data",
        "epochs": epochs,
        "lr": 2e-4,
        "lora_r": 8,
        "lora_alpha": 32,
        "quantize": False,
        "f1_threshold": 0.5,
    }
    resp = requests.post(
        f"{BASE}/version-management/retrain/finetune",
        json=payload,
        headers=headers,
        timeout=7200,  # CPU 训练可能很长
    )
    print("HTTP", resp.status_code)
    try:
        import json as _j

        print(_j.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(resp.text[:4000])


if __name__ == "__main__":
    main()