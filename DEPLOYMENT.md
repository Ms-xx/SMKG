# 部署指南（DEPLOYMENT）

> ## ⚠️ 部署模式声明（重要）
>
> **本项目当前唯一官方支持的部署模式为「本地部署」**（单机 / 本地服务器 / 本地计算环境）。
> 所有标准使用场景均在本地完成，官方仅对本地部署提供安装、配置、启动、验证与排障支持。
>
> **云端部署不属于官方支持范围**：代码层虽预留了云上部署扩展接口（见文末「云上扩展点」），
> 允许使用者根据自身需求自行调整配置切换，但官方**不对云端部署提供任何保障、适配与技术支持**。
> 请勿将未经验证的云端部署用于生产环境。

---

## 1. 部署模式开关

后端配置项 `DEPLOY_MODE`（见 `config/backend.env`）用于声明部署模式：

| 取值 | 含义 | 官方支持 |
| --- | --- | --- |
| `local`（默认） | 本地部署（单机 / 本地计算环境） | ✅ 唯一官方支持 |
| `cloud` | 云上部署（仅代码层扩展预留） | ❌ 非官方支持，启动期仅告警 |

- 默认 `local`，不改变既有启动行为；非法取值自动回退 `local`。
- 取 `cloud` 时后端仍可启动，但启动日志会打印「非官方支持」告警。
- 后端根端点 `GET /` 会透出 `deploy_mode` 字段，便于自动化探针核对。

## 2. 环境要求

- Python 3.11+（推荐使用项目的 `SciMKG` 虚拟环境）
- Node.js 22+ / pnpm（前端）
- Windows（一键脚本 `start_all.ps1` 为 Windows PowerShell 脚本）
- 本地依赖服务：MySQL 8.0、Redis、Neo4j 5、MinIO
- 本地 LLM：LM Studio（默认 `http://127.0.0.1:1234`，用于 RAG 问答与翻译）

## 3. 本地依赖服务

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| MySQL | 3306 | 业务数据库 |
| Redis | 6379 | 缓存 / Celery Broker 与结果后端 |
| Neo4j | 7687 | 知识图谱 |
| MinIO | 9000 / 9001 | 对象存储（9001 为控制台） |
| LM Studio | 1234 | 本地 LLM（OpenAI 兼容端点） |

> 以上均为**本机常驻服务**；`start_all.ps1` 会在启动时做健康检查，缺失时尝试拉起或提示。

## 4. 配置初始化

所有敏感配置集中在 [`config/`](config/README.md)，代码中不硬编码任何密钥。首次部署：

```bash
cp config/common.env.example    config/common.env
cp config/backend.env.example   config/backend.env
cp config/graphrag.env.example  config/graphrag.env
```

随后按本机实际值填写上述 `*.env`（`config/*.env` 已被 `.gitignore` 排除，不会进入版本库）。

## 5. 启动服务

**方式一：一键启动（Windows，官方推荐）**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_all.ps1
```

脚本依次拉起：依赖检查（MySQL/Redis/Neo4j）→ MinIO → 后端(8000) → Celery Worker → Celery Beat →
GraphRAGTest(8001) → 前端(3000)，并做健康检查汇总。

**方式二：分步启动**（见根 [README.md](README.md#启动服务)）

**可选组件：MLflow 本地 tracking server（步骤 14.3）**

实验追踪（版本管理）默认使用内置内存注册表，无需额外组件；如需把实验追踪写入真实
MLflow，可另起一台本地 tracking server：

```powershell
powershell -ExecutionPolicy Bypass -File deploy/mlflow/start_mlflow_server.ps1
```

存储目录、启动参数、接入环境变量与验证方法详见 [deploy/mlflow/README.md](deploy/mlflow/README.md)。

## 6. 访问地址

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:3000 |
| 后端健康检查 | http://localhost:8000/health |
| 后端 API 文档 | http://localhost:8000/docs |
| GraphRAGTest | http://localhost:8001/docs |
| MinIO 控制台 | http://localhost:9001 |
| MLflow UI（可选，步骤 14.3） | http://localhost:5000 |

默认管理员账号见 `config/backend.env` 的 `ADMIN_USERNAME` / `ADMIN_PASSWORD`。

## 7. 部署验证流程（官方验收口径）

部署完成后必须依次执行以下三段验证，全部通过方可视为「完全符合正常使用要求」。

### 7.1 服务可访问性 + 全量功能点完整性

```bash
python test/deploy_probe.py
```

逐项探测并产出报告 `outputs/deploy_probe_report.json`：

1. **第三方依赖可达性**：MySQL / Redis / Neo4j / MinIO / LM Studio 端口连通；
2. **服务可访问性**：后端 `/health` `/` `/docs` `/openapi.json`、登录、GraphRAGTest、前端；
3. **全量功能点完整性**：遍历 `/api/v1` 下全部路由模块（28 个前缀）并实调其 GET 端点；
4. **配置参数加载完整性**：`config/*.env` 存在且 `Settings` 关键项已加载；
5. **插件/模块完整性**：`backend/app/plugins/` 插件数量核对。

判定：`fail = 0` 时整体 `PASS`；设计上可降级的模块（回退规则/纯 Python）记为 `degraded`（通过但注明）。

### 7.2 72 小时连续运行稳定性

```bash
python test/stability_monitor.py --duration-hours 72
```

- 按间隔（默认 300s）持续采样各服务健康、依赖端口、主机资源；
- 逐条追加写入 `outputs/stability_timeseries.jsonl`；
- 实时刷新 `outputs/stability_summary.json`（累计时长、可用率、最大延迟、达标判定）；
- **可续跑**：中途重启不丢进度（读取既有记录累计时长）。

达标口径：累计运行 ≥ 72h 且各服务/依赖可用率 ≥ 99% → `达标（PASS）`。

快速自检可先跑一次：`python test/stability_monitor.py --once`。

### 7.3 结论归档

- 探针报告：`outputs/deploy_probe_report.json`
- 长稳时序：`outputs/stability_timeseries.jsonl`
- 长稳汇总：`outputs/stability_summary.json`

## 8. 云上扩展点（非官方支持）

以下资产仅作为**代码层扩展预留**，供使用者自行探索云端部署，**不属于官方支持范围**：

- `docker-compose.yml` / `docker-compose.monitoring.yml`：容器化编排参考；
- `deploy/k8s/`：Kubernetes 清单参考（namespace/configmap/secret/各服务）；
- `.github/workflows/ci.yml` 的 `deploy` job：默认 `if: false`，仅镜像打标推送与占位部署步骤。

若自行切换云端，需要把连接串、CORS、对象存储与 LLM 端点等改为可配置的外部地址；
由此产生的一切问题由使用者自行承担，官方不提供保障。

## 9. 常见问题

- **前端 3000 探活误报 DOWN**：Vite 绑定 IPv6 `::1`，请用 `http://localhost:3000` 或 `::1` 复检。
- **改动后端配置未生效**：本机以非 `--reload` 模式运行时需重启 `uvicorn` 进程。
- **LLM 功能回退为规则模板**：确认 LM Studio 已开启且 `LLM_ENDPOINT` 指向 `http://127.0.0.1:1234/v1`。
- **可降级模块报 degraded**：属预期行为（模型/依赖缺失时回退规则/纯 Python 实现，不阻断主流程）。
