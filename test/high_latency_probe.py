"""高延迟告警验证探针（步骤 2.5）。

对真实慢接口 `/api/v1/writing-assistant/llm-generate`（经 LM Studio，单次约 10~20s）
持续发起请求，使 Prometheus `http_request_duration_seconds` 的 P95 > 2s 维持 5 分钟以上，
从而触发 `HighLatency` 告警，验证「慢请求 → 规则 firing」。

用法：
    python test/high_latency_probe.py --duration 400 --concurrency 3
"""

import argparse
import asyncio
import json
import os
import time
from datetime import datetime

import httpx

BASE = "http://127.0.0.1:8000"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "high_latency_probe.json")


async def login(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{BASE}/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def worker(
    client: httpx.AsyncClient, token: str, deadline: float, stats: dict
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"prompt": "用一句话说明材料科学的图谱检索", "max_tokens": 120}
    while time.time() < deadline:
        start = time.perf_counter()
        try:
            resp = await client.post(
                f"{BASE}/api/v1/writing-assistant/llm-generate",
                json=payload,
                headers=headers,
            )
            status = resp.status_code
        except Exception as exc:  # noqa: BLE001
            status = None
            stats["errors"] += 1
            stats.setdefault("last_error", str(exc))
        elapsed = time.perf_counter() - start
        stats["requests"] += 1
        if status == 200:
            stats["ok"] += 1
        stats["latencies_ms"].append(round(elapsed * 1000, 1))


async def main() -> int:
    parser = argparse.ArgumentParser(description="HighLatency 告警触发探针")
    parser.add_argument("--duration", type=float, default=400, help="持续时间（秒）")
    parser.add_argument("--concurrency", type=int, default=3, help="并发 worker 数")
    parser.add_argument("--out", default=OUT, help="结果输出路径")
    args = parser.parse_args()

    stats: dict = {"requests": 0, "ok": 0, "errors": 0, "latencies_ms": []}
    deadline = time.time() + args.duration

    async with httpx.AsyncClient(timeout=90.0) as client:
        token = await login(client)
        await asyncio.gather(
            *(worker(client, token, deadline, stats) for _ in range(args.concurrency))
        )

    lat = sorted(stats["latencies_ms"])
    p95 = lat[int(len(lat) * 0.95) - 1] if lat else None
    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": args.duration,
        "concurrency": args.concurrency,
        "requests": stats["requests"],
        "ok": stats["ok"],
        "errors": stats["errors"],
        "min_ms": lat[0] if lat else None,
        "max_ms": lat[-1] if lat else None,
        "p95_ms": p95,
        "target": "HighLatency (http_request_duration_seconds P95 > 2s, for 5m)",
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
