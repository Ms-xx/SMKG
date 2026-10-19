# deploy/ — 云上扩展点（非官方支持）

> **注意**：本目录下的 Kubernetes 清单**不属于官方支持范围**。
> 本项目**唯一官方支持的部署模式为本地部署**（单机 / 本地计算环境），详见根目录 [DEPLOYMENT.md](../DEPLOYMENT.md)。

## 目录内容

- `k8s/`：Kubernetes 参考清单，含 `00-namespace`、`configmap`、`secret` 及
  `mysql` / `redis` / `neo4j` / `minio` / `backend` / `celery-worker` / `celery-beat` /
  `frontend` / `ingress` 等各服务清单。

## 定位

这些清单仅作为**代码层扩展预留**，供使用者自行探索云端部署：

- 清单中的连接串、CORS、对象存储与 LLM 端点等需自行改为外部可达地址；
- 密钥不得写入仓库，请通过 K8s `Secret` 或 CI/CD 变量注入；
- 由此产生的一切问题由使用者自行承担，官方不提供保障、适配与技术支持。

官方支持的部署、操作与验证流程请遵循本地部署指南：[DEPLOYMENT.md](../DEPLOYMENT.md)。
