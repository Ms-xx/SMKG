# MLflow 本地 tracking server（步骤 14.3）

> 本项目**唯一官方支持的部署模式为本地部署**。本目录提供的 MLflow tracking server 面向
> 本机 / 本地计算环境，服务默认仅监听 `127.0.0.1`，不对外暴露。云上部署（远程 MLflow、
> 对象存储工件仓库）不在官方支持范围内，仅作为代码层扩展点，见 [`../README.md`](../README.md)。

## 1. 独立存储目录（与项目其他资源隔离）

MLflow 的全部运行时资源集中存放在**一个独立目录**（缺省 `<仓库根>/mlflow`），与
`moulds/`（模型）、`outputs/`（测试产物）、`backend/storage/`（文档对象）等完全分离：

| 路径 | 用途 |
|------|------|
| `<MLFLOW_STORE_DIR>/backend/mlflow.db` | 后端存储（backend store）：SQLite 库，存放实验 / run / 参数 / 指标 / 标签 / 模型注册元数据 |
| `<MLFLOW_STORE_DIR>/artifacts/` | 工件存储（artifact store）：run 产物（`file:///` 本地目录模式） |
| `<MLFLOW_STORE_DIR>/logs/mlflow_server.log` | 服务端标准输出日志 |
| `<MLFLOW_STORE_DIR>/logs/mlflow_server.err.log` | 服务端错误日志 |

`<MLFLOW_STORE_DIR>` 缺省值为 `<仓库根>/mlflow`（已加入 `.gitignore`，运行时数据不进版本库）。

## 2. 启动服务

```powershell
# 缺省：存储目录 = <仓库根>/mlflow，监听 127.0.0.1:5000
powershell -ExecutionPolicy Bypass -File deploy/mlflow/start_mlflow_server.ps1

# 指定 Python 解释器（缺省按 MLFLOW_PYTHON → VIRTUAL_ENV → PATH 上的 python 回退）
powershell -ExecutionPolicy Bypass -File deploy/mlflow/start_mlflow_server.ps1 `
    -PythonExe "D:\workapp\Anaconda\anaconda3\envs\SciMKG\python.exe" -Port 5000
```

脚本会把 `backend store` / `artifact root` / 日志全部指向独立存储目录，等待就绪后打印
`HTTP 200`。UI 地址：<http://127.0.0.1:5000>。

**脚本参数（全部可覆盖，无硬编码路径）**：

| 参数 | 缺省 | 说明 |
|------|------|------|
| `-TrackingHome` | `$env:MLFLOW_HOME` → `<仓库根>/mlflow` | 独立存储根目录 |
| `-BindHost` | `127.0.0.1` | 监听地址（本地部署只监听回环） |
| `-Port` | `5000` | 监听端口 |
| `-PythonExe` | `$env:MLFLOW_PYTHON` → `$env:VIRTUAL_ENV/...python.exe` → `python` | 运行解释器 |

仓库根由脚本自身位置（`deploy/mlflow/`）自动推导，因此**克隆到任意磁盘、任意目录均可直接运行**；
如需把数据放到仓库外，只需设置环境变量 `MLFLOW_HOME`（或传 `-TrackingHome`）。

## 3. 接入配置要点（所有追踪请求统一指向本地 server）

后端通过 `config/backend.env`（模板：`config/backend.env.example`）读取以下键，
`version_management` 服务的**全部实验追踪请求**即统一发往本地 server：

| 配置键 | 示例 | 说明 |
|--------|------|------|
| `MLFLOW_ENABLED` | `true` | MLflow 接入总开关；`false` = 纯内置注册表 |
| `MLFLOW_TRACKING_URI` | `http://127.0.0.1:5000` | **所有 MLflow 追踪请求统一指向此本地地址** |
| `MLFLOW_STORE_DIR` | 留空 | 缺省即 `<仓库根>/mlflow`；**勿硬编码绝对路径** |
| `MLFLOW_EXPERIMENT_NAME` | `sdp-version-management` | 默认写入的实验名 |
| `MLFLOW_TRACKING_TIMEOUT` | `5` | 客户端健康探测 / 连接超时（秒） |
| `VERSION_MGMT_BACKEND` | `dvc_mlflow` | 置为 `dvc_mlflow` 才会把实验写入 MLflow |

> 启用条件 = `MLFLOW_ENABLED=true` **且** `VERSION_MGMT_BACKEND=dvc_mlflow` **且** 服务端可达。

**降级口径（不阻断主流程）**：以下任一情形自动降级为内置内存注册表（`builtin`），接口与
返回值不变，仅 `mlflow_run_id` 为 `null`：
① `MLFLOW_ENABLED=false` 或后端未切 `dvc_mlflow`；② 未安装 `mlflow` 包；
③ 服务端不可达（`GET /health` 非 200 / 连接超时）；④ 写入过程抛异常。

**接入状态自检**（后端运行中）：

```powershell
# 登录取 token
$tok = (Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/auth/login -Method Post `
    -Body (@{username="admin";password="admin123"}|ConvertTo-Json) -ContentType "application/json").access_token

# 查看 MLflow 接入状态（effective_backend 应为 dvc_mlflow）
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/version-management/mlflow/status?refresh=true" `
    -Headers @{Authorization="Bearer $tok"} | ConvertTo-Json -Depth 5
```

## 4. 接入有效性验证

```powershell
# 前置：MLflow server 已启动
D:\workapp\Anaconda\anaconda3\envs\SciMKG\python.exe test/mlflow_local_e2e.py
```

脚本执行项：① server `/health` 可达；② 后端服务 `effective_backend == dvc_mlflow`；
③ 记录一次实验并取得真实 `mlflow_run_id`；④ 经客户端回读参数/指标一致；⑤ 工件落盘到
`<MLFLOW_STORE_DIR>/artifacts/`；⑥ 后端 SQLite 落盘；⑦ 实验可经客户端与 UI 端点检索。
结果写入 [`outputs/mlflow_local_e2e.json`](../../outputs/mlflow_local_e2e.json)。

## 5. 停止服务

MLflow server 由 `Start-Process` 拉起为独立进程，关闭终端不影响其运行。停止方式：

```powershell
Get-NetTCPConnection -LocalPort 5000 -State Listen | ForEach-Object { taskkill /PID $_.OwningProcess /T /F }
```

## 6. 常见问题

| 现象 | 原因 / 处理 |
|------|-------------|
| `effective_backend` 为 `builtin` 且 `server_reachable=false` | 服务端未启动，或 URI/端口不符 → 执行第 2 节启动脚本 |
| 端口 5000 被占用 | 换端口：脚本 `-Port 5001` 并把 `MLFLOW_TRACKING_URI` 同步改为对应地址 |
| 找不到 `mlflow` 模块 | `pip install mlflow`（本机 SciMKG 环境已安装 3.17.1） |
| UI 打不开 | 确认 `http://127.0.0.1:5000/health` 返回 200；本服务仅监听回环，勿用外网 IP 访问 |
