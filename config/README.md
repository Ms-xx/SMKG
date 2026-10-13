# 集中化配置目录（config/）

本项目所有**敏感配置**（数据库口令、对象存储密钥、JWT 密钥、第三方服务凭据等）统一集中在本目录管理与引用，代码中不再硬编码任何真实密钥。

## 文件说明

| 文件 | 用途 | 是否入库 |
|------|------|---------|
| `common.env` | 跨服务共享凭据：Neo4j 连接、LLM / LM Studio 端点与模型 | ❌ 不进库 |
| `backend.env` | 后端专有：MySQL/Redis/MinIO/JWT/Celery 及功能开关 | ❌ 不进库 |
| `graphrag.env` | GraphRAGTest 子服务专有：API 监听地址/端口、Neo4j 库名 | ❌ 不进库 |
| `common.env.example` | 上述三者的**模板**（占位值），供新环境初始化 | ✅ 进库 |
| `backend.env.example` | 同上 | ✅ 进库 |
| `graphrag.env.example` | 同上 | ✅ 进库 |

> 真实文件由 `.gitignore` 的 `config/*.env` 规则排除；仅 `*.env.example` 模板被提交。

## 引用关系（谁在读这些文件）

- 后端 `backend/app/core/config.py` → 依次加载 `config/common.env`、`config/backend.env`（后者优先级更高），**使用绝对路径**，不再依赖启动时的工作目录。
- GraphRAGTest `GraphRAGTest/config.py` → 依次加载 `config/common.env`、`config/graphrag.env`。

## 新环境初始化

```bash
# 复制模板并填入真实值
cp config/common.env.example    config/common.env
cp config/backend.env.example   config/backend.env
cp config/graphrag.env.example  config/graphrag.env
```

## 约定

1. **口令/密钥只写在 `config/*.env`，绝不写进代码或提交进仓库。**
2. `common.env` 中的 Neo4j / LLM 配置为后端与 GraphRAGTest 共用，修改一次即可两处生效，避免漂移。
3. 新增敏感配置项时：在对应 `*.env` 写入真实值，并在同名 `*.env.example` 中以占位值登记，同时确认 `.gitignore` 规则仍覆盖该文件。
4. 前端（Vite）的环境变量**不放在此处**：`frontend/.env.*` 会被构建期内联进产物，只能放非敏感项（如 API 基址），其机制由 Vite 限定在 `frontend/` 目录内。
