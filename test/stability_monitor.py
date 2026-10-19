"""本地部署 72 小时连续运行稳定性监控（对应部署规范要求③）。

按固定间隔对全部本地服务与依赖持续采样，把每次采样追加写入
`outputs/stability_timeseries.jsonl`，并实时刷新 `outputs/stability_summary.json`
（累计运行时长、采样次数、各服务可用率、最大延迟、异常次数与达标判定）。

支持「可续跑」：重启时读取既有 summary/timeseries 推算已累计时长，不丢进度。

用法：
    # 后台常驻跑满 72 小时（默认每 300s 采样一次）
    python test/stability_monitor.py
    # 自定义间隔与时长
    python test/stability_monitor.py --interval 60 --duration-hours 72
    # 仅采样一次（用于快速验证）
    python test/stability_monitor.py --once
"""

import argparse
import json
import os
import socket
import time
from datetime import datetime

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(ROOT, "outputs")

BACKEND = "http://127.0.0.1:8000"
GRAPHRAG = "http://127.0.0.1:8001"
FRONTEND = "http://localhost:3000"
API_PREFIX = "/api/v1"

DEPS = [
    ("mysql", "127.0.0.1", 3306),
    ("redis", "127.0.0.1", 6379),
    ("neo4j", "127.0.0.1", 7687),
    ("minio", "127.0.0.1", 9000),
    ("llm", "127.0.0.1", 1234),
]

# 可用率达标阈值（0~1）
AVAILABILITY_THRESHOLD = 0.99
TIMEOUT = 15.0


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def tcp_ok(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_probe(client: httpx.Client, url: str) -> dict:
    start = time.perf_counter()
    try:
        resp = client.get(url)
        latency = (time.perf_counter() - start) * 1000
        return {
            "ok": resp.status_code < 500,
            "status": resp.status_code,
            "latency_ms": round(latency, 1),
        }
    except Exception as exc:  # noqa: BLE001
        latency = (time.perf_counter() - start) * 1000
        return {"ok": False, "status": None, "latency_ms": round(latency, 1), "error": str(exc)}


def sample_once(client: httpx.Client) -> dict:
    sample = {
        "ts": _now_iso(),
        "epoch": time.time(),
        "services": {
            "backend": http_probe(client, f"{BACKEND}/health"),
            "backend_metrics": http_probe(client, f"{BACKEND}/metrics"),
            "graphrag": http_probe(client, f"{GRAPHRAG}{API_PREFIX}/health"),
            "frontend": http_probe(client, FRONTEND),
        },
        "deps": {},
        "host": {},
    }
    for name, host, port in DEPS:
        sample["deps"][name] = {"ok": tcp_ok(host, port), "port": port}

    try:
        import psutil  # type: ignore

        sample["host"] = {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "mem_percent": psutil.virtual_memory().percent,
        }
    except Exception:  # noqa: BLE001
        sample["host"] = {}

    return sample


def load_previous(timeseries_path: str, summary_path: str) -> dict:
    """读取既有结果，用于续跑累计。"""
    state = {"started_at": None, "samples": []}
    if os.path.isfile(timeseries_path):
        with open(timeseries_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    state["samples"].append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if os.path.isfile(summary_path):
        try:
            with open(summary_path, encoding="utf-8") as fh:
                prev = json.load(fh)
            state["started_at"] = prev.get("started_at")
        except Exception:  # noqa: BLE001
            pass
    if not state["started_at"] and state["samples"]:
        state["started_at"] = state["samples"][0]["ts"]
    return state


def _availability(samples: list, getter) -> dict:
    if not samples:
        return {"samples": 0, "ok": 0, "rate": None, "max_latency_ms": None}
    ok = 0
    max_lat = 0.0
    for s in samples:
        item = getter(s)
        if item and item.get("ok"):
            ok += 1
            max_lat = max(max_lat, item.get("latency_ms") or 0.0)
    return {
        "samples": len(samples),
        "ok": ok,
        "rate": round(ok / len(samples), 4),
        "max_latency_ms": round(max_lat, 1),
    }


def _start_epoch(started_at, samples: list, now: float) -> float:
    if not started_at:
        return samples[0]["epoch"] if samples else now
    try:
        return datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return samples[0]["epoch"] if samples else now


def _verdict(samples: list, complete: bool, healthy: bool) -> str:
    if not samples:
        return "未开始"
    if complete and healthy:
        return "达标（PASS）"
    if complete:
        return "时长已满但可用率不达标（FAIL）"
    return "进行中"


def build_summary(state: dict, duration_hours: float, interval: int) -> dict:
    samples = state["samples"]
    started_at = state["started_at"]
    now = time.time()

    services = {
        svc: _availability(samples, lambda s, svc=svc: s["services"].get(svc))
        for svc in ("backend", "graphrag", "frontend")
    }
    deps = {
        name: _availability(samples, lambda s, name=name: s["deps"].get(name))
        for name, _, _ in DEPS
    }

    start_epoch = _start_epoch(started_at, samples, now)
    elapsed_hours = round(max(0.0, now - start_epoch) / 3600.0, 3)

    rates = [v["rate"] for v in services.values() if v["rate"] is not None]
    rates += [v["rate"] for v in deps.values() if v["rate"] is not None]
    min_rate = min(rates) if rates else 0.0

    complete = elapsed_hours >= duration_hours
    healthy = min_rate >= AVAILABILITY_THRESHOLD
    verdict = _verdict(samples, complete, healthy)

    return {
        "generated_at": _now_iso(),
        "deploy_mode_note": "本地部署为唯一官方支持模式",
        "started_at": started_at,
        "elapsed_hours": elapsed_hours,
        "target_hours": duration_hours,
        "interval_seconds": interval,
        "samples": len(samples),
        "min_availability": min_rate,
        "availability_threshold": AVAILABILITY_THRESHOLD,
        "services": services,
        "deps": deps,
        "verdict": verdict,
    }


def run(interval: int, duration_hours: float, out_dir: str, once: bool) -> int:
    os.makedirs(out_dir, exist_ok=True)
    timeseries_path = os.path.join(out_dir, "stability_timeseries.jsonl")
    summary_path = os.path.join(out_dir, "stability_summary.json")

    state = load_previous(timeseries_path, summary_path)
    if not state["started_at"]:
        state["started_at"] = _now_iso()

    if once:
        with httpx.Client(timeout=TIMEOUT) as client:
            state["samples"].append(sample_once(client))
        with open(timeseries_path, "w", encoding="utf-8") as fh:
            for s in state["samples"]:
                fh.write(json.dumps(s, ensure_ascii=False) + "\n")
        summary = build_summary(state, duration_hours, interval)
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(
        f"稳定性监控启动：目标 {duration_hours}h，间隔 {interval}s，"
        f"起始 {state['started_at']}，已累计 {len(state['samples'])} 次采样"
    )
    try:
        with (
            httpx.Client(timeout=TIMEOUT) as client,
            open(timeseries_path, "a", encoding="utf-8") as fh,
        ):
            while True:
                sample = sample_once(client)
                state["samples"].append(sample)
                fh.write(json.dumps(sample, ensure_ascii=False) + "\n")
                fh.flush()

                summary = build_summary(state, duration_hours, interval)
                with open(summary_path, "w", encoding="utf-8") as sfh:
                    json.dump(summary, sfh, ensure_ascii=False, indent=2)

                print(
                    f"[{sample['ts']}] 采样#{len(state['samples'])} "
                    f"已累计 {summary['elapsed_hours']}h / {duration_hours}h "
                    f"→ {summary['verdict']}",
                    flush=True,
                )
                if summary["verdict"].startswith("达标") or summary["verdict"].startswith(
                    "时长已满"
                ):
                    print("目标时长已完成，监控退出。")
                    return 0
                time.sleep(interval)
    except KeyboardInterrupt:
        summary = build_summary(state, duration_hours, interval)
        with open(summary_path, "w", encoding="utf-8") as sfh:
            json.dump(summary, sfh, ensure_ascii=False, indent=2)
        print(f"\n已中止，进度已保存：{summary['elapsed_hours']}h / {duration_hours}h")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="本地部署 72h 连续运行稳定性监控")
    parser.add_argument("--interval", type=int, default=300, help="采样间隔（秒），默认 300")
    parser.add_argument(
        "--duration-hours", type=float, default=72.0, help="目标时长（小时），默认 72"
    )
    parser.add_argument("--out", default=DEFAULT_OUT_DIR, help="输出目录，默认 outputs/")
    parser.add_argument("--once", action="store_true", help="仅采样一次后退出")
    args = parser.parse_args()
    return run(args.interval, args.duration_hours, args.out, args.once)


if __name__ == "__main__":
    raise SystemExit(main())
