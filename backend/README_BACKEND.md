# Backend API 服务

多模态科学文献智能解析平台后端服务

## 项目状态

✅ **已完成的核心功能**

### 1. 核心服务 (Services)
- ✅ **extraction_service.py** - 完整的实体和关系抽取逻辑
  - 支持基于规则的实体识别(Material, Property, Method等)
  - 支持关系抽取(HAS_PROPERTY, PRODUCED_BY, IMPROVES等)
  - 支持LLM集成接口

- ✅ **parsing_service.py** - PDF解析服务
  - PyMuPDF文本提取
  - PDFPlumber表格提取
  - 图像提取功能

- ✅ **document_service.py** - 文档管理服务
  - 上传、查询、更新、删除文档
  - 触发解析任务
  - 页面元素获取

- ✅ **auth_service.py** - 认证服务
  - 用户登录验证
  - 用户注册
  - Token生成

- ✅ **annotation_service.py** - 标注服务
  - 创建、更新标注
  - 提交审核
  - 版本管理

- ✅ **task_service.py** - 任务管理服务
  - 创建、查询任务
  - 取消、暂停、恢复、终止、重试任务

- ✅ **graph_service.py** - 知识图谱服务
  - 图谱搜索
  - 实体查询
  - 关系查询
  - Cypher执行

### 2. Celery异步任务 (Workers)
- ✅ **parsing_tasks.py** - 完整的文档解析流程
  - 从MinIO下载PDF
  - 文本、表格、图像提取
  - 结果保存到数据库
  - 错误处理和状态更新

- ✅ **extraction_tasks.py** - 信息抽取任务框架

- ✅ **graph_tasks.py** - 知识图谱构建任务
  - 实体节点创建
  - 关系建立
  - 文档节点创建
  - 统计信息更新

### 3. API端点 (API)
- ✅ **auth.py** - 认证API
  - POST /login - 用户登录
  - POST /refresh - 刷新Token
  - POST /logout - 登出
  - POST /register - 用户注册
  - GET /me - 获取当前用户信息
  - POST /change-password - 修改密码

- ✅ **documents.py** - 文档管理API
  - POST /upload - 上传PDF
  - GET / - 文档列表(分页、筛选)
  - GET /{id} - 文档详情
  - PUT /{id} - 更新文档
  - DELETE /{id} - 删除文档
  - POST /{id}/parse - 触发解析
  - GET /{id}/pages/{num}/elements - 页面元素

- ✅ **tasks.py** - 任务管理API
  - POST / - 创建任务
  - GET / - 任务列表(分页/状态/类型筛选)
  - GET /{id} - 任务详情
  - POST /{id}/cancel - 取消任务
  - POST /{id}/pause - 暂停任务
  - POST /{id}/resume - 恢复任务
  - DELETE /{id}/terminate - 终止任务(删除记录,关联文档标记失败)
  - POST /{id}/retry - 重试任务

- ✅ **annotations.py** - 标注管理API
- ✅ **knowledge_graph.py** - 知识图谱API
- ✅ **users.py** - 用户管理API
- ✅ **models.py** - 模型管理API

### 4. 数据库配置
- ✅ **database.py** - 完善的数据库连接
  - 异步连接用于FastAPI
  - 同步连接用于Celery任务
  - 连接池配置

- ✅ **config.py** - 配置管理
  - 数据库配置(WX数据库,root用户,密码CHANGE_ME)
  - Redis配置
  - Neo4j配置
  - MinIO配置
  - JWT配置

### 5. 工具类 (Utils)
- ✅ **minio_client.py** - MinIO文件存储客户端
- ✅ **neo4j_client.py** - Neo4j图数据库客户端
- ✅ **redis_client.py** - Redis客户端
- ✅ **pagination.py** - 分页工具

### 6. 数据库模型 (Models)
- ✅ User, Role, UserSession
- ✅ Document, DocumentPage, DocumentElement
- ✅ Task
- ✅ Annotation, AnnotationVersion
- ✅ Model, TrainingExperiment
- ✅ SystemConfig, OperationLog

### 7. 数据验证 (Schemas)
- ✅ 所有Pydantic Schema定义完整

## 数据库配置

- 数据库名: WX
- 用户名: root
- 密码: CHANGE_ME
- 连接地址: 127.0.0.1:3306

## 快速启动

### 1. 安装依赖
```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量
```bash
# .env文件已配置完成,数据库连接信息正确
```

### 3. 初始化数据库
```bash
python scripts/init_db.py
```

### 4. 启动服务
```bash
# 方式1: 使用启动脚本(Linux)
bash start.sh

# 方式2: 手动启动
# 启动FastAPI
uvicorn app.main:app --reload --port 8000

# 启动Celery Worker(另一个终端)
celery -A app.core.celery_app worker -l info -Q parsing,extraction,graph

# 启动Redis(如果未启动)
redis-server

# 启动Neo4j(如果未启动)
neo4j start
```

### 5. 访问API文档
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 默认管理员账号

- 用户名: admin
- 密码: admin123
- **请及时修改密码!**

## API端点测试

### 登录获取Token
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### 上传文档
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer {token}" \
  -F "file=@paper.pdf"
```

### 触发解析
```bash
curl -X POST "http://localhost:8000/api/v1/documents/{document_id}/parse" \
  -H "Authorization: Bearer {token}"
```

## 目录结构

```
backend/
├── app/
│   ├── api/v1/          # API端点(已完成)
│   ├── core/            # 核心配置(已完成)
│   ├── models/          # 数据库模型(已完成)
│   ├── schemas/         # 数据验证(已完成)
│   ├── services/        # 业务逻辑(已完成)
│   ├── workers/         # Celery任务(已完成)
│   ├── utils/           # 工具类(已完成)
│   └── main.py          # 应用入口(已完成)
├── scripts/
│   └ init_db.py         # 数据库初始化脚本(已完成)
├── alembic/             # 数据库迁移
├── .env                 # 环境配置(已完成)
├── requirements.txt     # 依赖列表(已完成)
└── README_BACKEND.md    # 本文档
```

## 待完善功能(可选扩展)

### 1. AI模型集成
- 集成实际的NER模型(如SciBERT)
- 集成LLM模型(如Qwen)
- 集成Embedding模型(如BGE-M3)
- 集成公式识别模型(如LaTeX-OCR)

### 2. 高级功能
- WebSocket实时任务进度推送
- 用户头像上传
- 批量文档处理优化
- 高级搜索功能
- 数据导出功能

### 3. 监控与运维
- Prometheus监控
- Grafana仪表盘
- 日志聚合
- 性能优化

## 技术栈

- **框架**: FastAPI 0.109.0
- **数据库**: MySQL 8.0 (WX数据库)
- **ORM**: SQLAlchemy 2.0
- **图数据库**: Neo4j 5.x
- **缓存**: Redis 7.x
- **任务队列**: Celery 5.3
- **文件存储**: MinIO
- **PDF处理**: PyMuPDF, PDFPlumber

## 开发建议

1. 使用Python 3.11+
2. 推荐使用VSCode或PyCharm
3. 安装Python扩展和调试工具
4. 使用FastAPI自动生成的API文档测试接口
5. 查看日志文件排查问题

## 问题排查

### 数据库连接失败
- 检查MySQL是否启动
- 验证数据库名称、用户名、密码
- 检查防火墙设置

### Redis连接失败
- 检查Redis是否启动: redis-cli ping
- 查看Redis配置

### Celery任务不执行
- 确认Celery Worker已启动
- 检查Redis连接
- 查看Celery日志

## 联系方式

如有问题,请查看项目文档或联系开发团队。

---

**最后更新**: 2026-04-28
**版本**: 1.1.0
**状态**: ✅ 核心功能已完成（含任务暂停/恢复/终止/重试）