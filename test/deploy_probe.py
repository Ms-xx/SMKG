"""本地部署全量探针（对应部署规范要求②③）。

逐项验证：
  1) 第三方依赖可达性（MySQL / Redis / Neo4j / MinIO / LM Studio）
  2) 服务可访问性（后端 / GraphRAGTest / 前端）
  3) 全量功能点完整性（/api/v1 全部路由模块及其 GET 端点）
  4) 配置参数加载完整性（config/*.env → Settings）
  5) 插件/模块完整性（backend/app/plugins 插件数量）

用法：
    python test/deploy_probe.py
输出：
    outputs/deploy_probe_report.json（结构化报告）
    stdout 中文汇总表

说明：设计上「可插拔可降级」的模块若回退到规则/纯 Python 实现，记为 degraded（通过但注明），
不视为功能缺失；仅当服务不可达、模块缺失或返回 5xx 时才记 fail。
"""

import json
import os
import socket
import sys
import time
from datetime import datetime

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs")
REPORT_PATH = os.path.join(OUTPUT_DIR, "deploy_probe_report.json")

BACKEND = "http://127.0.0.1:8000"
GRAPHRAG = "http://127.0.0.1:8001"
FRONTEND = "http://localhost:3000"
API_PREFIX = "/api/v1"

# 期望存在的后端路由模块（来自 backend/app/api/v1/router.py 的 include_router 前缀）
EXPECTED_MODULES = [
    "auth",
    "users",
    "documents",
    "tasks",
    "annotations",
    "operation-logs",
    "statistics",
    "comments",
    "notifications",
    "permissions",
    "knowledge-graph",
    "active-learning",
    "version-management",
    "ab-test",
    "multi-agent",
    "system",
    "calibration-drift",
    "models",
    "alerts",
    "deduplication",
    "source-anchor",
    "citation-link",
    "paper-retrieval",
    "citation-graph",
    "citation-quality",
    "repo-recommend",
    "writing-assistant",
]

# 期望在跑的本地依赖服务（端口）
DEPENDENCIES = [
    ("MySQL", 3306),
    ("Redis", 6379),
    ("Neo4j", 7687),
    ("MinIO", 9000),
    ("MinIO Console", 9001),
    ("LM Studio", 1234),
]

TIMEOUT = 15.0
# 部分功能端点首次调用含冷启动/重查询（如 /tasks/ 约 13s），模块探测放宽超时
MODULE_TIMEOUT = 45.0


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add(items: list, category: str, name: str, status: str, detail: str) -> None:
    items.append(
        {
            "category": category,
            "name": name,
            "status": status,
            "detail": detail,
        }
    )


def tcp_ok(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def classify_http(status_code: int) -> str:
    if status_code < 300:
        return "pass"
    if status_code in (400, 401, 403, 404, 405, 422):
        return "degraded"  # 端点可达（需鉴权/参数），非服务故障
    return "fail"


def probe_dependencies(items: list) -> None:
    for name, port in DEPENDENCIES:
        ok = tcp_ok("127.0.0.1", port)
        add(
            items,
            "dependency",
            f"{name}(:{port})",
            "pass" if ok else "fail",
            "TCP 端口可达" if ok else "TCP 端口不可达",
        )


def probe_backend_base(client: httpx.Client, items: list):
    """后端基础端点 + 登录，返回 (token, deploy_mode)。"""
    token = None
    deploy_mode = None

    for path in ("/health", "/", "/docs", "/openapi.json"):
        try:
            resp = client.get(f"{BACKEND}{path}")
            add(
                items,
                "service",
                f"backend GET {path}",
                classify_http(resp.status_code),
                f"HTTP {resp.status_code}",
            )
        except Exception as exc:  # noqa: BLE001
            add(items, "service", f"backend GET {path}", "fail", f"异常: {exc}")

    try:
        resp = client.get(f"{BACKEND}/")
        if resp.status_code < 300:
            deploy_mode = resp.json().get("deploy_mode")
    except Exception:  # noqa: BLE001
        pass

    # 登录获取管理员令牌
    username, password = "admin", "admin123"
    try:
        sys.path.insert(0, os.path.join(ROOT, "backend"))
        from app.core.config import settings  # noqa: E402

        username = settings.ADMIN_USERNAME or username
        password = settings.ADMIN_PASSWORD or password
    except Exception:  # noqa: BLE001
        pass

    try:
        resp = client.post(
            f"{BACKEND}{API_PREFIX}/auth/login",
            json={"username": username, "password": password},
        )
        if resp.status_code < 300:
            token = resp.json().get("access_token")
            add(
                items,
                "service",
                "backend 登录 /auth/login",
                "pass",
                "已获取管理员令牌",
            )
        else:
            add(
                items,
                "service",
                "backend 登录 /auth/login",
                "fail",
                f"HTTP {resp.status_code}",
            )
    except Exception as exc:  # noqa: BLE001
        add(items, "service", "backend 登录 /auth/login", "fail", f"异常: {exc}")

    return token, deploy_mode


def probe_modules(client: httpx.Client, token, items: list) -> None:
    """按 openapi 校验全部路由模块注册与 GET 端点可达性。"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        spec = client.get(f"{BACKEND}/openapi.json").json()
    except Exception as exc:  # noqa: BLE001
        add(items, "module", "openapi 解析", "fail", f"异常: {exc}")
        return

    paths = spec.get("paths", {})
    # 模块 -> 该模块下所有 (method, path)
    by_module: dict = {}
    for path, ops in paths.items():
        if not path.startswith(API_PREFIX + "/"):
            continue
        rest = path[len(API_PREFIX) + 1 :]
        module = rest.split("/", 1)[0]
        for method in ops:
            by_module.setdefault(module, []).append((method.upper(), path))

    # 模块注册完整性
    for module in EXPECTED_MODULES:
        ops = by_module.get(module)
        if not ops:
            add(items, "module", f"模块 /{module}", "fail", "未在 openapi 中注册")
            continue

        get_no_param = [p for (m, p) in ops if m == "GET" and "{" not in p]
        if not get_no_param:
            add(
                items,
                "module",
                f"模块 /{module}",
                "degraded",
                f"已注册 {len(ops)} 个端点（无无参 GET，跳过实调）",
            )
            continue

        target = sorted(get_no_param)[0]
        try:
            resp = client.get(f"{BACKEND}{target}", headers=headers)
            add(
                items,
                "module",
                f"模块 /{module}",
                classify_http(resp.status_code),
                f"{target} → HTTP {resp.status_code}",
            )
        except Exception as exc:  # noqa: BLE001
            add(items, "module", f"模块 /{module}", "fail", f"{target} 异常: {exc}")


def probe_graphrag(client: httpx.Client, items: list) -> None:
    checks = [
        ("GET", f"{GRAPHRAG}{API_PREFIX}/health"),
        ("GET", f"{GRAPHRAG}{API_PREFIX}/graph/stats"),
        ("GET", f"{GRAPHRAG}{API_PREFIX}/llm/status"),
    ]
    for method, url in checks:
        try:
            resp = client.request(method, url)
            add(
                items,
                "service",
                f"GraphRAGTest {method} {url.split('8001')[-1]}",
                classify_http(resp.status_code),
                f"HTTP {resp.status_code}",
            )
        except Exception as exc:  # noqa: BLE001
            add(
                items,
                "service",
                f"GraphRAGTest {method} {url.split('8001')[-1]}",
                "fail",
                f"异常: {exc}",
            )


def probe_frontend(items: list) -> None:
    ok = False
    detail = ""
    for host in ("localhost", "127.0.0.1"):
        try:
            resp = httpx.get(f"http://{host}:3000", timeout=TIMEOUT)
            ok = resp.status_code < 400
            detail = f"HTTP {resp.status_code} ({host})"
            break
        except Exception as exc:  # noqa: BLE001
            detail = f"异常: {exc} ({host})"
    add(
        items,
        "service",
        "frontend GET :3000",
        "pass" if ok else "fail",
        detail,
    )


def probe_config(items: list) -> str:
    """校验 config/*.env 与 Settings 关键项已加载。"""
    config_dir = os.path.join(ROOT, "config")
    deploy_mode = None
    for fname in ("common.env", "backend.env", "graphrag.env"):
        exists = os.path.isfile(os.path.join(config_dir, fname))
        add(
            items,
            "config",
            f"config/{fname}",
            "pass" if exists else "fail",
            "存在" if exists else "缺失",
        )

    try:
        sys.path.insert(0, os.path.join(ROOT, "backend"))
        from app.core.config import settings  # noqa: E402

        deploy_mode = settings.DEPLOY_MODE
        keys = [
            "DATABASE_URL",
            "REDIS_URL",
            "NEO4J_URI",
            "MINIO_ENDPOINT",
            "LLM_ENDPOINT",
            "DEPLOY_MODE",
        ]
        for key in keys:
            val = getattr(settings, key, None) or ""
            ok = bool(val)
            add(
                items,
                "config",
                f"settings.{key}",
                "pass" if ok else "fail",
                f"={val}" if ok else "未加载",
            )
    except Exception as exc:  # noqa: BLE001
        add(items, "config", "settings 加载", "fail", f"异常: {exc}")
    return deploy_mode


def probe_websocket(token, items: list) -> None:
    """以真实 WS 握手探测实时协作模块（WebSocket 不在 openapi 中）。"""
    if not token:
        add(items, "module", "模块 /ws (WebSocket)", "degraded", "无令牌，跳过握手")
        return
    try:
        import asyncio

        import websockets
    except Exception as exc:  # noqa: BLE001
        add(items, "module", "模块 /ws (WebSocket)", "degraded", f"websockets 不可用: {exc}")
        return

    url = f"ws://127.0.0.1:8000{API_PREFIX}/ws/annotations/probe-doc?token={token}"

    async def _handshake() -> str:
        async with websockets.connect(url, open_timeout=15) as ws:
            return await asyncio.wait_for(ws.recv(), timeout=15)

    try:
        msg = asyncio.run(_handshake())
        ok = "subscribed" in msg
        add(
            items,
            "module",
            "模块 /ws (WebSocket)",
            "pass" if ok else "degraded",
            f"握手成功，首帧={str(msg)[:80]}",
        )
    except Exception as exc:  # noqa: BLE001
        add(items, "module", "模块 /ws (WebSocket)", "fail", f"WS 握手失败: {exc}")


def probe_plugins(items: list) -> None:
    plugin_dir = os.path.join(ROOT, "backend", "app", "plugins")
    try:
        dirs = [
            d
            for d in os.listdir(plugin_dir)
            if os.path.isdir(os.path.join(plugin_dir, d)) and not d.startswith("__")
        ]
        # 官方插件以目录内含 plugin.py 为准（其余为辅助目录，如 data/）
        plugins = [d for d in dirs if os.path.isfile(os.path.join(plugin_dir, d, "plugin.py"))]
        add(
            items,
            "plugin",
            "plugins 目录插件数",
            "pass" if plugins else "fail",
            f"{len(plugins)} 个插件（含 plugin.py；目录共 {len(dirs)} 个）",
        )
    except Exception as exc:  # noqa: BLE001
        add(items, "plugin", "plugins 目录", "fail", f"异常: {exc}")


def main() -> int:
    started = time.time()
    items: list = []

    probe_dependencies(items)
    with httpx.Client(timeout=TIMEOUT) as client:
        token, deploy_mode = probe_backend_base(client, items)
        probe_graphrag(client, items)
    with httpx.Client(timeout=MODULE_TIMEOUT) as mclient:
        probe_modules(mclient, token, items)
    probe_websocket(token, items)
    probe_frontend(items)
    cfg_mode = probe_config(items)
    probe_plugins(items)

    counts = {"pass": 0, "degraded": 0, "fail": 0}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1

    report = {
        "generated_at": _now(),
        "duration_seconds": round(time.time() - started, 2),
        "deploy_mode": deploy_mode or cfg_mode,
        "summary": {
            "total": len(items),
            "pass": counts.get("pass", 0),
            "degraded": counts.get("degraded", 0),
            "fail": counts.get("fail", 0),
            "verdict": "PASS" if counts.get("fail", 0) == 0 else "FAIL",
        },
        "items": items,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print("=" * 64)
    print("本地部署全量探针报告")
    print(f"部署模式: {report['deploy_mode']}（官方支持: local only）")
    print("-" * 64)
    for it in items:
        flag = {"pass": "PASS", "degraded": "WARN", "fail": "FAIL"}[it["status"]]
        print(f"[{flag}] {it['name']:<38} {it['detail']}")
    print("-" * 64)
    s = report["summary"]
    print(
        f"合计 {s['total']} 项：pass={s['pass']} degraded={s['degraded']} "
        f"fail={s['fail']} → 判定 {s['verdict']}"
    )
    print(f"报告已写入: {REPORT_PATH}")
    print("=" * 64)

    return 0 if s["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
