# API 接口文档

## 概述

本文档定义了多模态科学文献智能解析平台的所有 RESTful API 接口。

**基础信息**
- Base URL: `/api/v1`
- 认证方式: Bearer Token (JWT)
- 数据格式: JSON
- 字符编码: UTF-8

**通用响应格式**

```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "timestamp": 1700000000
}
```

**分页响应格式**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [],
    "total": 100,
    "page": 1,
    "page_size": 10,
    "total_pages": 10
  }
}
```

**错误响应格式**

```json
{
  "code": 400,
  "message": "参数错误",
  "errors": [
    {
      "field": "email",
      "message": "邮箱格式不正确"
    }
  ],
  "timestamp": 1700000000
}
```

---

## 一、认证模块 (Auth)

### 1.1 用户登录

**POST** `/api/v1/auth/login`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

**请求示例**

```json
{
  "username": "admin",
  "password": "your_password"
}
```

**响应示例**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

---

### 1.2 刷新 Token

**POST** `/api/v1/auth/refresh`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| refresh_token | string | 是 | 刷新令牌 |

**请求示例**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**响应示例**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

---

### 1.3 用户注册

**POST** `/api/v1/auth/register`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 (3-50字符) |
| email | string | 是 | 邮箱 |
| password | string | 是 | 密码 (至少8字符) |
| full_name | string | 否 | 真实姓名 |

**请求示例**

```json
{
  "username": "newuser",
  "email": "user@example.com",
  "password": "SecurePass123",
  "full_name": "张三"
}
```

**响应示例**

```json
{
  "code": 201,
  "message": "success",
  "data": {
    "id": "uuid",
    "username": "newuser",
    "email": "user@example.com",
    "full_name": "张三",
    "role": "user",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

### 1.4 用户登出

**POST** `/api/v1/auth/logout`

**Headers**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| Authorization | string | 是 | Bearer {access_token} |

**响应示例**

```json
{
  "code": 200,
  "message": "登出成功"
}
```

---

### 1.5 获取当前用户信息

**GET** `/api/v1/auth/me`

**Headers**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| Authorization | string | 是 | Bearer {access_token} |

**响应示例**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "uuid",
    "username": "admin",
    "email": "admin@example.com",
    "full_name": "管理员",
    "avatar_url": "https://...",
    "role": "admin",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "last_login": "2024-01-15T10:30:00Z"
  }
}
```

---

### 1.6 修改密码

**POST** `/api/v1/auth/change-password`

**Headers**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| Authorization | string | 是 | Bearer {access_token} |

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| old_password | string | 是 | 原密码 |
| new_password | string | 是 | 新密码（至少6位） |

**请求示例**

```json
{
  "old_password": "admin123",
  "new_password": "newpass123"
}
```

**响应示例**

```json
{
  "message": "密码修改成功"
}
```

---

## 二、用户管理模块 (Users)

### 2.1 获取用户列表

**GET** `/api/v1/users/`

**权限**: `system:user:manage`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量 |
| role | string | 否 | - | 角色筛选 |
| is_active | boolean | 否 | - | 是否激活 |
| keyword | string | 否 | - | 搜索关键词 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "uuid",
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "is_active": true,
        "created_at": "2024-01-01T00:00:00Z"
      }
    ],
    "total": 50,
    "page": 1,
    "page_size": 10
  }
}
```

---

### 2.2 获取用户详情

**GET** `/api/v1/users/{user_id}`

**权限**: `admin` 或 本人

**Path 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "id": "uuid",
    "username": "admin",
    "email": "admin@example.com",
    "full_name": "管理员",
    "avatar_url": "https://...",
    "role": "admin",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "last_login": "2024-01-15T10:30:00Z"
  }
}
```

---

### 2.3 更新用户信息

**PUT** `/api/v1/users/{user_id}`

**权限**: `admin` 或 本人

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| full_name | string | 否 | 真实姓名 |
| avatar_url | string | 否 | 头像 URL |
| email | string | 否 | 邮箱 |

---

### 2.4 更新用户角色

**PUT** `/api/v1/users/{user_id}/role`

**权限**: `system:user:manage`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| role | string | 是 | 新角色 (admin/annotator/reviewer/user) |

---

### 2.5 禁用/启用用户

**PUT** `/api/v1/users/{user_id}/status`

**权限**: `system:user:manage`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| is_active | boolean | 是 | 是否激活 |

---

### 2.6 删除用户

**DELETE** `/api/v1/users/{user_id}`

**权限**: `system:user:manage`

---

## 三、文档管理模块 (Documents)

### 3.1 上传文档

**POST** `/api/v1/documents/upload`

**权限**: `document:write`

**Content-Type**: `multipart/form-data`

**表单参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | PDF 文件 (最大 100MB) |
| title | string | 否 | 文档标题 (默认使用文件名) |

**请求示例**

```
POST /api/v1/documents/upload
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="paper.pdf"
Content-Type: application/pdf

(binary data)
------WebKitFormBoundary
Content-Disposition: form-data; name="title"

钙钛矿太阳能电池研究进展
------WebKitFormBoundary--
```

**响应示例**

```json
{
  "code": 201,
  "data": {
    "id": "uuid",
    "title": "钙钛矿太阳能电池研究进展",
    "file_path": "original/user-1/paper.pdf",
    "file_size": 2048576,
    "status": "uploaded",
    "uploaded_by": "uuid",
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

---

### 3.2 获取文档列表

**GET** `/api/v1/documents/`

**权限**: `document:read`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量 |
| status | string | 否 | - | 状态筛选 (uploaded/parsing/parsed/failed) |
| keyword | string | 否 | - | 标题搜索 |
| sort_by | string | 否 | created_at | 排序字段 |
| sort_order | string | 否 | desc | 排序方向 (asc/desc) |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "钙钛矿太阳能电池研究进展",
        "doi": "10.1000/example.2024",
        "authors": ["张三", "李四"],
        "keywords": ["钙钛矿", "太阳能电池"],
        "page_count": 15,
        "status": "parsed",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:05:00Z"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 10
  }
}
```

---

### 3.3 获取文档详情

**GET** `/api/v1/documents/{document_id}`

**权限**: `document:read`

**Path 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| document_id | string | 是 | 文档 ID |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "id": "uuid",
    "title": "钙钛矿太阳能电池研究进展",
    "doi": "10.1000/example.2024",
    "authors": ["张三", "李四"],
    "abstract": "本文综述了...",
    "keywords": ["钙钛矿", "太阳能电池", "光电转换"],
    "publication_date": "2024-01-01",
    "journal": "材料学报",
    "references": [
      {
        "index": 1,
        "authors": "Smith J, Doe A, et al.",
        "title": "Perovskite solar cells",
        "journal": "Nature Energy",
        "year": "2023",
        "volume": "8",
        "issue": "2",
        "pages": "101-115",
        "doi": "10.1038/s41560-023-01000-0",
        "type": "journal",
        "raw": "Smith J, Doe A, et al. Perovskite solar cells[J]. Nature Energy, 2023, 8(2): 101-115."
      }
    ],
    "file_path": "original/user-1/paper.pdf",
    "file_size": 2048576,
    "page_count": 15,
    "status": "parsed",
    "uploaded_by": "uuid",
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:05:00Z"
  }
}
```

---

### 3.4 更新文档信息

**PUT** `/api/v1/documents/{document_id}`

**权限**: `document:write`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 否 | 标题 |
| doi | string | 否 | DOI |
| authors | array | 否 | 作者列表 |
| abstract | string | 否 | 摘要 |
| keywords | array | 否 | 关键词 |
| publication_date | string | 否 | 发表日期 |
| journal | string | 否 | 期刊名称 |

---

### 3.5 删除文档

**DELETE** `/api/v1/documents/{document_id}`

**权限**: `document:write`

**响应**

```json
{
  "code": 204,
  "message": "删除成功"
}
```

---

### 3.6 触发文档解析

**POST** `/api/v1/documents/{document_id}/parse`

**权限**: `document:write`

**响应示例**

```json
{
  "code": 200,
  "data": {
    "task_id": "uuid",
    "status": "pending",
    "message": "解析任务已提交"
  }
}
```

---

### 3.7 获取文档文件

> ⚠️ **未实现**：后端 `documents.py` 当前无此接口（规划中）。

**GET** `/api/v1/documents/{document_id}/file`

**说明**: 返回 PDF 文件二进制流（规划）

**响应头**

```
Content-Type: application/pdf
Content-Disposition: attachment; filename="paper.pdf"
```

---

### 3.8 获取页面元素

**GET** `/api/v1/documents/{document_id}/pages/{page_number}/elements`

**权限**: `document:read`

**Path 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| document_id | string | 是 | 文档 ID |
| page_number | integer | 是 | 页码 (从1开始) |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "page_number": 1,
    "elements": [
      {
        "id": "uuid",
        "element_type": "heading",
        "bbox": [100, 50, 500, 80],
        "content": "1. 引言",
        "confidence": 0.95,
        "metadata": {}
      },
      {
        "id": "uuid",
        "element_type": "text",
        "bbox": [100, 100, 500, 300],
        "content": "钙钛矿太阳能电池是...",
        "confidence": 0.92,
        "metadata": {}
      },
      {
        "id": "uuid",
        "element_type": "formula",
        "bbox": [200, 350, 400, 380],
        "content": null,
        "confidence": 0.88,
        "metadata": {
          "latex": "CH_3NH_3PbI_3"
        }
      }
    ]
  }
}
```

---

### 3.9 批量解析文档

> ⚠️ **未实现**：后端 `documents.py` 当前无此接口（规划中）。

**POST** `/api/v1/documents/batch-parse`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| document_ids | array | 是 | 文档 ID 列表 |

**请求示例**

```json
{
  "document_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**响应示例**

```json
{
  "code": 200,
  "data": {
    "task_ids": ["uuid1", "uuid2", "uuid3"],
    "message": "已提交 3 个解析任务"
  }
}
```

---

## 四、任务管理模块 (Tasks)

> **任务状态**: pending（等待中）| running（运行中）| paused（已暂停）| completed（已完成）| failed（失败）| cancelled（已取消）

### 4.1 创建任务

**POST** `/api/v1/tasks/`

**权限**: `task:write`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_type | string | 是 | 任务类型 (parsing/extraction/graph 自动化 / parse_validation/entity_annotation/graph_review 人工分配) |
| document_id | string | 否 | 关联文档 ID |
| assigned_to | string | 否 | 负责人用户 ID（手动分配） |
| priority | integer | 否 | 优先级 (0-10, 默认 0) |
| due_at | string | 否 | 截止日期 (ISO 8601) |
| params | object | 否 | 任务参数 |

**请求示例**

```json
{
  "task_type": "extraction",
  "document_id": "uuid",
  "priority": 5,
  "params": {
    "extract_entities": true,
    "extract_relations": true,
    "model": "qwen-7b"
  }
}
```

**响应示例**

```json
{
  "code": 201,
  "data": {
    "id": "uuid",
    "task_type": "extraction",
    "document_id": "uuid",
    "status": "pending",
    "priority": 5,
    "progress": 0,
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

---

### 4.2 获取任务列表

**GET** `/api/v1/tasks/`

**权限**: `task:read`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量 |
| status | string | 否 | - | 状态筛选 |
| task_type | string | 否 | - | 任务类型筛选 |
| assigned_to | string | 否 | - | 分配给用户 |
| sort_by | string | 否 | created_at | 排序字段 |
| sort_order | string | 否 | desc | 排序方向 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "uuid",
        "task_type": "parsing",
        "document_id": "uuid",
        "assigned_to": "uuid",
        "status": "running",
        "priority": 5,
        "progress": 65.5,
        "created_at": "2024-01-15T10:00:00Z",
        "started_at": "2024-01-15T10:01:00Z"
      }
    ],
    "total": 50,
    "page": 1,
    "page_size": 10
  }
}
```

---

### 4.3 获取任务详情

**GET** `/api/v1/tasks/{task_id}`

**权限**: `task:read`

**响应示例**

```json
{
  "code": 200,
  "data": {
    "id": "uuid",
    "task_type": "parsing",
    "document_id": "uuid",
    "assigned_to": "uuid",
    "assigned_by": "uuid",
    "due_at": "2024-01-20T18:00:00Z",
    "status": "completed",
    "priority": 5,
    "progress": 100,
    "params": {},
    "result": {
      "pages_parsed": 15,
      "elements_extracted": 120,
      "tables_found": 5
    },
    "error_message": null,
    "created_at": "2024-01-15T10:00:00Z",
    "started_at": "2024-01-15T10:01:00Z",
    "completed_at": "2024-01-15T10:05:00Z"
  }
}
```

---

### 4.4 取消任务

**POST** `/api/v1/tasks/{task_id}/cancel`

**权限**: `task:write`

**响应示例**

```json
{
  "code": 200,
  "message": "任务已取消"
}
```

---

### 4.5 暂停任务

**POST** `/api/v1/tasks/{task_id}/pause`

**权限**: `task:write`

**响应示例**

```json
{
  "message": "Task paused",
  "task": { "id": "uuid", "status": "paused" }
}
```

---

### 4.6 恢复任务

**POST** `/api/v1/tasks/{task_id}/resume`

**权限**: `task:write`

**响应示例**

```json
{
  "message": "Task resumed",
  "task": { "id": "uuid", "status": "running" }
}
```

---

### 4.7 终止任务

**DELETE** `/api/v1/tasks/{task_id}/terminate`

**权限**: `task:write`

**说明**: 终止任务，删除任务记录，并将关联文档状态标记为 failed（不删除文档本身）

**响应示例**

```json
{
  "message": "任务已终止并删除"
}
```

---

### 4.8 重试失败任务

**POST** `/api/v1/tasks/{task_id}/retry`

**权限**: `task:write`

**响应示例**

```json
{
  "code": 200,
  "data": {
    "task_id": "uuid",
    "status": "pending",
    "message": "任务已重新提交"
  }
}
```

---

### 4.9 获取任务进度

**GET** `/api/v1/tasks/{task_id}/progress`

**权限**: `task:read`

**说明**: 获取任务实时进度（REST 轮询，同步 Celery 状态）。WebSocket 实时推送为规划功能（未实现，见第十章）。

**响应示例**

```json
{
  "code": 200,
  "data": {
    "progress": 75.5,
    "status": "running",
    "celery_state": "PROGRESS"
  }
}
```

---

### 4.10 手动分配任务

**POST** `/api/v1/tasks/{task_id}/assign`

**权限**: `task:write`

**说明**: 手动分配任务，指定负责人、优先级、截止日期。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| assigned_to | string | 是 | 负责人用户 ID |
| priority | integer | 否 | 优先级 (0-10) |
| due_at | string | 否 | 截止日期 (ISO 8601) |

**请求示例**

```json
{
  "assigned_to": "uuid",
  "priority": 5,
  "due_at": "2024-01-20T18:00:00Z"
}
```

**响应示例**

```json
{
  "code": 200,
  "data": {
    "id": "uuid",
    "task_type": "entity_annotation",
    "document_id": "uuid",
    "assigned_to": "uuid",
    "assigned_by": "uuid",
    "due_at": "2024-01-20T18:00:00Z",
    "status": "pending",
    "priority": 5,
    "progress": 0,
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

---

## 五、标注管理模块 (Annotations)

### 5.1 创建标注

**POST** `/api/v1/annotations/`

**权限**: `annotation:write`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| document_id | string | 是 | 文档 ID |
| element_id | string | 否 | 元素 ID |
| annotation_type | string | 是 | 标注类型 (ner/relation/correction) |
| content | object | 是 | 标注内容 |
| confidence | number | 否 | 置信度 (0-1) |

**请求示例 (实体标注)**

```json
{
  "document_id": "uuid",
  "element_id": "uuid",
  "annotation_type": "ner",
  "content": {
    "entities": [
      {
        "text": "钙钛矿",
        "type": "Material",
        "start": 0,
        "end": 3
      },
      {
        "text": "CH3NH3PbI3",
        "type": "Material",
        "start": 10,
        "end": 20
      }
    ]
  },
  "confidence": 0.95
}
```

**响应示例**

```json
{
  "code": 201,
  "data": {
    "id": "uuid",
    "document_id": "uuid",
    "annotation_type": "ner",
    "content": {...},
    "status": "draft",
    "annotated_by": "uuid",
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

---

### 5.2 获取标注列表

**GET** `/api/v1/annotations/`

**权限**: `annotation:read`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| document_id | string | 否 | - | 文档 ID |
| annotation_type | string | 否 | - | 标注类型 |
| status | string | 否 | - | 状态筛选 |
| annotated_by | string | 否 | - | 标注人 |
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量 |

---

### 5.3 获取文档标注

**GET** `/api/v1/annotations/document/{document_id}`

**权限**: `annotation:read`

**响应示例**

```json
{
  "code": 200,
  "data": [
    {
      "id": "uuid",
      "annotation_type": "ner",
      "content": {
        "entities": [...]
      },
      "status": "approved",
      "annotated_by": "uuid",
      "first_reviewed_by": "uuid",
      "final_reviewed_by": "uuid",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

---

### 5.4 更新标注

**PUT** `/api/v1/annotations/{annotation_id}`

**权限**: `annotation:write`

**请求体**: 同创建标注

---

### 5.5 提交标注审核

**POST** `/api/v1/annotations/{annotation_id}/submit`

**权限**: `annotation:write`

**响应示例**

```json
{
  "code": 200,
  "message": "标注已提交审核"
}
```

---

### 5.6 审核标注（初审/终审）

**初审** `POST` `/api/v1/annotations/{annotation_id}/first-review`

**权限**: `annotation:review`

> 状态流转：submitted → pending_final（通过）/ rejected（驳回）

**终审** `POST` `/api/v1/annotations/{annotation_id}/final-review`

**权限**: `annotation:review`

> 状态流转：pending_final → approved（通过）/ rejected（驳回）

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| approved | boolean | 是 | 是否通过 |
| comment | string | 否 | 审核意见/驳回理由 |

**请求示例**

```json
{
  "approved": true,
  "comment": "标注准确，实体类型正确"
}
```

---

### 5.7 获取标注版本历史

**GET** `/api/v1/annotations/{annotation_id}/versions`

**权限**: `annotation:read`

**响应示例**

```json
{
  "code": 200,
  "data": [
    {
      "id": "uuid",
      "content": {...},
      "changed_by": "uuid",
      "change_type": "create",
      "created_at": "2024-01-15T10:00:00Z"
    },
    {
      "id": "uuid",
      "content": {...},
      "changed_by": "uuid",
      "change_type": "update",
      "created_at": "2024-01-15T10:05:00Z"
    }
  ]
}
```

---

### 5.8 删除标注

**DELETE** `/api/v1/annotations/{annotation_id}`

**权限**: `annotation:write`

---

### 5.9 标注一致性评估

**POST** `/api/v1/annotations/agreement`

**权限**: `annotation:read`

**说明**: 计算多名标注员对同一批样本标注结果的一致性，支持 Cohen's Kappa（两标注员）、Fleiss' Kappa（多标注员）、Krippendorff's Alpha（任意标注员，名义/区间/比值度量）；纯 Python 零依赖。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ratings | array | 是 | 样本 × 标注员 矩阵；单元格为类别标签（字符串/数值），`null` 表示缺失 |
| metrics | array | 否 | cohens \| fleiss \| krippendorff；不填默认全部 |
| krippendorff_metric | string | 否 | nominal \| interval \| ratio（默认 nominal） |

**请求示例**

```json
{
  "ratings": [
    ["Material", "Material", "Material"],
    ["Method", "Method", "Material"]
  ],
  "metrics": ["fleiss", "cohens", "krippendorff"],
  "krippendorff_metric": "nominal"
}
```

**响应示例**

```json
{
  "n_subjects": 2,
  "n_raters": 3,
  "cohens_kappa": 0.4,
  "fleiss_kappa": 0.4545,
  "krippendorff_alpha": 0.3333,
  "krippendorff_metric": "nominal"
}
```

---

## 六、知识图谱模块 (Knowledge Graph)

### 6.1 搜索图谱

**GET** `/api/v1/knowledge-graph/search`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | 搜索关键词 |
| entity_type | string | 否 | - | 实体类型筛选 |
| limit | integer | 否 | 20 | 返回数量 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "entities": [
      {
        "id": "mat_001",
        "labels": ["Material"],
        "properties": {
          "name": "甲基铵铅碘钙钛矿",
          "formula": "CH3NH3PbI3",
          "category": "钙钛矿"
        },
        "score": 0.95
      }
    ],
    "total": 15
  }
}
```

---

### 6.2 获取实体详情

**GET** `/api/v1/knowledge-graph/entities/{entity_id}`

**响应示例**

```json
{
  "code": 200,
  "data": {
    "id": "mat_001",
    "labels": ["Material"],
    "properties": {
      "name": "甲基铵铅碘钙钛矿",
      "formula": "CH3NH3PbI3",
      "category": "钙钛矿",
      "structure": "ABX3",
      "description": "一种典型的有机-无机杂化钙钛矿材料"
    },
    "relations": [
      {
        "type": "HAS_PROPERTY",
        "target": {
          "id": "prop_001",
          "name": "光电转换效率"
        },
        "properties": {
          "value": 25.5,
          "unit": "%"
        }
      }
    ]
  }
}
```

---

### 6.3 获取实体关系

**GET** `/api/v1/knowledge-graph/entities/{entity_id}/relations`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| depth | integer | 否 | 1 | 关系深度 (1-3) |
| relation_type | string | 否 | - | 关系类型筛选 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "nodes": [
      {"id": "mat_001", "label": "甲基铵铅碘钙钛矿", "type": "Material"},
      {"id": "prop_001", "label": "光电转换效率", "type": "Property"},
      {"id": "meth_001", "label": "旋涂法", "type": "Method"}
    ],
    "links": [
      {"source": "mat_001", "target": "prop_001", "type": "HAS_PROPERTY"},
      {"source": "mat_001", "target": "meth_001", "type": "PRODUCED_BY"}
    ]
  }
}
```

---

### 6.4 执行 Cypher 查询

**POST** `/api/v1/knowledge-graph/query`

**权限**: `admin`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cypher | string | 是 | Cypher 查询语句 |
| params | object | 否 | 查询参数 |

**请求示例**

```json
{
  "cypher": "MATCH (m:Material {category: $category})-[:HAS_PROPERTY]->(p:Property {name: 'PCE'}) RETURN m.name, m.formula, p.value",
  "params": {
    "category": "钙钛矿"
  }
}
```

**响应示例**

```json
{
  "code": 200,
  "data": {
    "columns": ["m.name", "m.formula", "p.value"],
    "rows": [
      ["甲基铵铅碘钙钛矿", "CH3NH3PbI3", 25.5],
      ["甲脒铅碘钙钛矿", "FAPbI3", 26.1]
    ]
  }
}
```

---

### 6.5 获取图谱统计

**GET** `/api/v1/knowledge-graph/statistics`

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total_nodes": 15000,
    "total_relations": 45000,
    "node_types": {
      "Material": 5000,
      "Property": 3000,
      "Method": 2000,
      "Parameter": 3000,
      "Document": 1500,
      "Result": 500
    },
    "relation_types": {
      "HAS_PROPERTY": 15000,
      "PRODUCED_BY": 10000,
      "IMPROVES": 8000,
      "CORRELATES_WITH": 7000,
      "CITES": 5000
    },
    "last_updated": "2024-01-15T10:00:00Z"
  }
}
```

---

### 6.6 批量导入图谱数据

**POST** `/api/v1/knowledge-graph/import`

**权限**: `admin`

**Content-Type**: `multipart/form-data`

**表单参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nodes_file | file | 是 | 节点数据 (JSON/CSV) |
| relations_file | file | 是 | 关系数据 (JSON/CSV) |
| merge_strategy | string | 否 | 合并策略 (skip/update) |

---

### 6.7 实体链接（批量）

**POST** `/api/v1/knowledge-graph/entity-link`

**权限**: 需登录

**说明**: 接入 Wikidata/DBpedia 对实体做消歧与同义词合并。未启用/网络失败时自动降级为本地领域同义词表或返回未链接标记（`source=none`）。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| entities | array | 是 | 实体列表，每项含 `text` 与可选 `entity_type` |

**请求示例**

```json
{
  "entities": [
    { "text": "钙钛矿", "entity_type": "Material" },
    { "text": "高效率", "entity_type": "Property" }
  ]
}
```

**响应示例**

```json
{
  "code": 200,
  "data": {
    "results": [
      {
        "text": "钙钛矿",
        "canonical_id": "Q13308963",
        "canonical_name": "perovskite",
        "aliases": ["calcium titanate"],
        "source": "wikidata",
        "score": 0.95,
        "description": "mineral"
      }
    ],
    "total": 1
  }
}
```

---

### 6.8 实体链接（单个）

**POST** `/api/v1/knowledge-graph/entity-link/single`

**权限**: 需登录

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| text | string | 是 | 实体文本 |
| entity_type | string | 否 | 实体类型（用于消歧打分） |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "text": "二氧化钛",
    "canonical_id": "local:titanium dioxide",
    "canonical_name": "titanium dioxide",
    "aliases": ["氧化钛", "tio2"],
    "source": "local",
    "score": 1.0,
    "description": "本地领域本体对齐"
  }
}
```

---

### 6.9 关系推理

**POST** `/api/v1/knowledge-graph/reason`

**权限**: 需登录

**说明**: 基于组合 / 逆关系 / 传递规则，从已有三元组推导新关系（纯函数，零依赖）。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| triples | array | 是 | 三元组列表，每项含 `head`、`relation`、`tail` |

**请求示例**

```json
{
  "triples": [
    { "head": "反溶剂法", "relation": "PRODUCES", "tail": "MAPbI3" },
    { "head": "MAPbI3", "relation": "ACHIEVES", "tail": "高效率" }
  ]
}
```

**响应示例**

```json
{
  "code": 200,
  "data": {
    "inferred": [
      {
        "head": "反溶剂法",
        "relation": "ENABLES",
        "tail": "高效率",
        "reason": "组合: PRODUCES + ACHIEVES => ENABLES",
        "confidence": 0.8
      }
    ],
    "total": 1
  }
}
```

---

### 6.10 图谱补全 / 链路预测

**POST** `/api/v1/knowledge-graph/link-prediction`

**权限**: 需登录

**说明**: 给定头实体与关系，预测最可能的尾实体（TransE 嵌入打分；numpy 缺失/三元组过少自动降级为统计共现基线）。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| head | string | 是 | 头实体 |
| relation | string | 是 | 关系类型 |
| triples | array | 否 | 训练三元组列表（缺省使用上一次推理上下文） |
| top_k | integer | 否 | 返回候选数量（默认 10） |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "head": "反溶剂法",
    "relation": "PRODUCES",
    "backend": "transe",
    "candidates": [
      { "entity": "FAPbI3", "score": -0.32 }
    ]
  }
}
```

---

### 6.11 三元组打分

**POST** `/api/v1/knowledge-graph/triple-score`

**权限**: 需登录

**说明**: 对候选三元组打分（越高越可能），用于图谱补全的缺失边判定。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| head | string | 是 | 头实体 |
| relation | string | 是 | 关系类型 |
| tail | string | 是 | 尾实体 |
| triples | array | 否 | 训练三元组列表 |

**响应示例**

```json
{
  "code": 200,
  "data": { "head": "反溶剂法", "relation": "PRODUCES", "tail": "MAPbI3", "score": 1.0 }
}
```

### 6.12 搜索建议

**POST** `/api/v1/knowledge-graph/suggest`

**权限**: 需登录

**说明**: 基于前缀 / 子串 / 编辑距离的搜索建议（纯 Python 实现，零依赖）。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| prefix | string | 是 | 搜索前缀 |
| candidates | array | 否 | 候选实体列表（缺省使用全量实体） |
| limit | integer | 否 | 返回建议数量（默认 10） |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "prefix": "钙",
    "suggestions": ["钙钛矿", "氧化钙", "碳酸钙"],
    "backend": "builtin"
  }
}
```

### 6.13 分面搜索

**POST** `/api/v1/knowledge-graph/facet-search`

**权限**: 需登录

**说明**: 关键字打分 + 按 facet_key 聚合计数（纯 Python 实现，零依赖）。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 否 | 搜索关键词（空则返回全量） |
| records | array | 否 | 候选记录列表（缺省使用全量实体） |
| facet_key | string | 否 | 分面字段（默认 "label"） |
| limit | integer | 否 | 返回结果数量（默认 20） |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "query": "钙钛矿",
    "total": 1,
    "results": [{"name": "钙钛矿", "label": "Material", "score": 0.95}],
    "facets": [{"value": "Material", "count": 1}]
  }
}
```

### 6.14 Text-to-Cypher

**POST** `/api/v1/knowledge-graph/text-to-cypher`

**权限**: 需登录

**说明**: 自然语言 → 只读 Cypher 查询（规则模板，LLM 预留可降级）。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| question | string | 是 | 自然语言问题 |
| node_labels | array | 否 | 节点标签列表（辅助消歧） |
| relation_types | array | 否 | 关系类型列表 |
| limit | integer | 否 | 返回结果数量（默认 20） |
| execute | boolean | 否 | 是否直接执行查询（默认 false） |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "question": "有多少种材料",
    "cypher": "MATCH (n:`Material`) RETURN count(n) AS count",
    "params": {},
    "intent": "count_by_label",
    "backend": "rule",
    "results": [{"count": 5}]
  }
}
```

---

## 七、模型管理模块 (Models)

### 7.1 获取模型列表

**GET** `/api/v1/models/`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| model_type | string | 否 | - | 模型类型 |
| is_active | boolean | 否 | - | 是否激活 |

**响应示例**

```json
{
  "code": 200,
  "data": [
    {
      "id": "uuid",
      "name": "bge-m3",
      "version": "1.0.0",
      "model_type": "embedding",
      "framework": "pytorch",
      "is_active": true,
      "metrics": {
        "mteb_score": 0.65
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

### 7.2 注册模型

**POST** `/api/v1/models/`

**权限**: `admin`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 模型名称 |
| version | string | 是 | 版本号 |
| model_type | string | 是 | 模型类型 |
| framework | string | 否 | 框架 |
| file_path | string | 否 | 模型文件路径 |
| metrics | object | 否 | 性能指标 |

---

### 7.3 激活/停用模型

**PUT** `/api/v1/models/{model_id}/status`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| is_active | boolean | 是 | 是否激活 |

---

### 7.4 获取模型详情

**GET** `/api/v1/models/{model_id}`

---

### 7.5 删除模型

**DELETE** `/api/v1/models/{model_id}`

---

## 八、系统管理模块 (System)

### 8.1 健康检查

**GET** `/api/v1/health`

**响应示例**

```json
{
  "code": 200,
  "data": {
    "status": "healthy",
    "version": "1.0.0",
    "services": {
      "database": "connected",
      "redis": "connected",
      "neo4j": "connected",
      "minio": "connected"
    },
    "timestamp": "2024-01-15T10:00:00Z"
  }
}
```

---

### 8.2 获取系统配置

**GET** `/api/v1/system/config`

**权限**: `admin`

**响应示例**

```json
{
  "code": 200,
  "data": [
    {
      "key": "max_upload_size",
      "value": {"value": 100, "unit": "MB"},
      "description": "最大上传文件大小"
    },
    {
      "key": "supported_formats",
      "value": {"value": ["pdf"]},
      "description": "支持的文件格式"
    }
  ]
}
```

---

### 8.3 更新系统配置

**PUT** `/api/v1/system/config/{key}`

**权限**: `admin`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| value | object | 是 | 配置值 |

---

### 8.4 查询操作日志

**GET** `/api/v1/operation-logs/`

**权限**: `system:audit:read`（记录标注/修改/审核等操作的审计日志）

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| user_id | string | 否 | - | 按操作人用户 ID 筛选 |
| action | string | 否 | - | 操作类型（create/update/submit/first_review/final_review/delete） |
| resource_type | string | 否 | - | 资源类型筛选 |
| start_date | string | 否 | - | 开始时间（ISO 8601） |
| end_date | string | 否 | - | 结束时间（ISO 8601） |
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量（最大 100） |

**响应示例**

```json
{
  "items": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "action": "final_review",
      "resource_type": "annotation",
      "resource_id": "uuid",
      "details": {
        "approved": true,
        "comment": "标注准确，实体类型正确"
      },
      "ip_address": "127.0.0.1",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 10
}
```

> **说明**：操作日志由后端在标注的创建、修改、提交、初审、终审、删除等操作中自动记录，无需前端显式调用写入接口。

### 8.5 工作量统计

个人完成量、准确率与团队看板。数据由后端基于标注（`annotations`）与任务（`tasks`）表实时聚合，无需额外数据库表。

#### 8.5.1 获取个人工作量统计

**GET** `/api/v1/statistics/personal`

**权限**: 需登录（返回当前登录用户的统计）

**响应示例**

```json
{
  "user_id": "uuid",
  "username": "zhangsan",
  "full_name": "张三",
  "role": "annotator",
  "annotation_total": 120,
  "annotation_approved": 100,
  "annotation_rejected": 10,
  "annotation_pending": 8,
  "annotation_draft": 2,
  "accuracy_rate": 90.9,
  "task_total": 30,
  "task_completed": 20,
  "task_in_progress": 7,
  "task_failed": 3
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| username | string \| null | 用户名 |
| full_name | string \| null | 姓名 |
| role | string \| null | 角色 |
| annotation_total | integer | 标注总数 |
| annotation_approved | integer | 审核通过数 |
| annotation_rejected | integer | 审核驳回数 |
| annotation_pending | integer | 待审核数（submitted + pending_final） |
| annotation_draft | integer | 草稿数 |
| accuracy_rate | number \| null | 准确率（%），审核数为 0 时为 null |
| task_total | integer | 任务总数 |
| task_completed | integer | 已完成任务数 |
| task_in_progress | integer | 进行中任务数（pending + running + paused） |
| task_failed | integer | 失败任务数 |

#### 8.5.2 获取团队看板

**GET** `/api/v1/statistics/team`

**权限**: 需登录（返回全部成员的工作量统计）

**响应示例**

```json
{
  "items": [
    {
      "user_id": "uuid",
      "username": "zhangsan",
      "full_name": "张三",
      "role": "annotator",
      "annotation_total": 120,
      "annotation_approved": 100,
      "annotation_rejected": 10,
      "annotation_pending": 8,
      "annotation_draft": 2,
      "accuracy_rate": 90.9,
      "task_total": 30,
      "task_completed": 20,
      "task_in_progress": 7,
      "task_failed": 3
    }
  ],
  "total_users": 5
}
```

**字段说明**：`items` 为按 `annotation_total` 降序排列的成员统计列表，结构与个人统计一致；`total_users` 为成员总数。

---

### 8.6 评论讨论

#### 8.6.1 发表评论

**POST** `/api/v1/comments/`

**权限**: 需登录

**请求体**

```json
{
  "annotation_id": "uuid",
  "content": "请确认这条标注 @zhangsan",
  "parent_id": "uuid（可选，回复某条评论）"
}
```

**响应** (201)

```json
{
  "id": "uuid",
  "annotation_id": "uuid",
  "parent_id": null,
  "user_id": "uuid",
  "username": "lisi",
  "full_name": "李四",
  "content": "请确认这条标注 @zhangsan",
  "mentions": ["zhangsan-uuid"],
  "created_at": "2026-09-08T12:00:00",
  "updated_at": "2026-09-08T12:00:00"
}
```

**说明**：后端自动解析 `content` 中的 `@用户名` 提及，向被提及用户（及被回复评论的作者）写入通知；`mentions` 为被提及用户的 user_id 列表（自动排除本人、去重）。

#### 8.6.2 查询评论列表

**GET** `/api/v1/comments/`

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| annotation_id | string | 否 | 按标注过滤 |
| document_id | string | 否 | 按文档聚合（注释关联到该文档的所有标注） |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20，最大 100 |

**响应**：`{ "items": [CommentResponse...], "total": n, "page": 1, "page_size": 20 }`

#### 8.6.3 删除评论

**DELETE** `/api/v1/comments/{comment_id}`

**权限**: 仅评论作者本人可删除；返回 204。

---

### 8.7 通知

#### 8.7.1 查询通知列表

**GET** `/api/v1/notifications/`

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20，最大 100 |
| unread_only | bool | 否 | 仅返回未读，默认 false |

**响应**

```json
{
  "items": [
    {
      "id": "uuid",
      "type": "mention",
      "title": "有人在评论中提及了你",
      "content": "请确认这条标注 @zhangsan",
      "sender_id": "uuid",
      "sender_name": "lisi",
      "resource_type": "comment",
      "resource_id": "comment-uuid",
      "is_read": false,
      "created_at": "2026-09-08T12:00:00"
    }
  ],
  "total": 1,
  "unread_count": 1,
  "page": 1,
  "page_size": 20
}
```

#### 8.7.2 未读数量

**GET** `/api/v1/notifications/unread-count` → `{ "count": 3 }`

#### 8.7.3 标记单条已读

**POST** `/api/v1/notifications/{notification_id}/read` → `{ "message": "marked as read" }`

#### 8.7.4 全部标记已读

**POST** `/api/v1/notifications/read-all` → `{ "message": "all marked as read" }`

#### 8.7.5 可提及用户（@补全）

**GET** `/api/v1/users/mentionable`

**权限**: 需登录

**响应**：`[ { "id": "uuid", "username": "zhangsan", "full_name": "张三" }, ... ]`

---

### 8.8 权限管理 (Permissions)

> RBAC 细粒度权限。权限码格式为 `resource:action`，分文档级 / 任务级 / 标注级 / 系统级。

#### 8.8.1 获取我的权限

**GET** `/api/v1/permissions/me`

**权限**: 需登录

**响应示例**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "role": "annotator",
    "permissions": ["document:read", "annotation:read", "annotation:write", "task:read"]
  }
}
```

#### 8.8.2 获取权限定义

**GET** `/api/v1/permissions/definitions`

**权限**: 需登录

**响应示例**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      { "code": "document:read", "description": "查看文档" },
      { "code": "document:write", "description": "上传/编辑/删除/解析文档" },
      { "code": "task:read", "description": "查看任务" },
      { "code": "task:write", "description": "创建/分配/操作任务" },
      { "code": "annotation:read", "description": "查看标注" },
      { "code": "annotation:write", "description": "创建/编辑标注" },
      { "code": "annotation:review", "description": "审核标注" },
      { "code": "system:user:manage", "description": "用户管理" },
      { "code": "system:role:manage", "description": "角色权限管理" },
      { "code": "system:audit:read", "description": "查看操作日志" }
    ],
    "total": 10
  }
}
```

#### 8.8.3 获取角色列表

**GET** `/api/v1/permissions/roles`

**权限**: `system:role:manage`

**响应示例**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "name": "reviewer",
        "description": "审核员",
        "permissions": ["document:read", "document:write", "annotation:read", "annotation:review", "task:read", "task:write"]
      }
    ],
    "total": 4
  }
}
```

#### 8.8.4 更新角色权限

**PUT** `/api/v1/permissions/roles/{role_name}`

**权限**: `system:role:manage`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| permissions | array[string] | 是 | 该角色完整权限码列表（仅合法码被接受并去重） |

**请求示例**

```json
{
  "permissions": ["document:read", "task:read", "annotation:read", "annotation:write"]
}
```

**响应示例**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "uuid",
    "name": "annotator",
    "description": "标注员",
    "permissions": ["document:read", "task:read", "annotation:read", "annotation:write"]
  }
}
```

---

## 九、错误码说明

| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 删除成功 |
| 400 | 请求参数错误 |
| 401 | 未认证/Token 无效 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 409 | 资源冲突 (如用户名已存在) |
| 422 | 数据验证失败 |
| 429 | 请求频率过高 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

---

## 十、WebSocket 接口

> ⚠️ **未实现**：以下 WebSocket 端点均为规划功能，后端当前无 `WebSocket` 路由实现。任务进度请使用 REST 轮询 `GET /api/v1/tasks/{task_id}/progress`（见 4.9）。

### 10.1 任务进度推送

**WS** `/ws/tasks/{task_id}`

**连接参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| token | string | 是 | Access Token |

**服务器消息**

```json
{
  "type": "progress_update",
  "data": {
    "task_id": "uuid",
    "status": "running",
    "progress": 75.5,
    "step": "extracting_tables",
    "message": "正在提取表格..."
  }
}
```

### 10.2 实时通知

**WS** `/ws/notifications`

**服务器消息**

```json
{
  "type": "notification",
  "data": {
    "id": "uuid",
    "title": "任务完成",
    "message": "文档解析已完成",
    "type": "task_completed",
    "created_at": "2024-01-15T10:05:00Z"
  }
}
```

---

## 七、GraphRAG 集成接口 (代理到 GraphRAGTest :8001)

> **说明**: 以下接口由主后端 (8000) 代理到 GraphRAGTest 子系统 (8001)，实现基于 Neo4j 图数据库 + Qwen LLM 的智能问答。

### 7.1 GraphRAGTest 健康状态

**GET** `/api/v1/knowledge-graph/rag/health`

**响应示例**

```json
{
  "status": "connected",
  "service": { "status": "healthy", "service": "GraphRAG", "version": "1.0.0" }
}
```

---

### 7.2 LLM 状态

**GET** `/api/v1/knowledge-graph/rag/llm/status`

**响应示例**

```json
{
  "llm_provider": "LM Studio",
  "base_url": "http://localhost:1234",
  "current_model": "qwen/qwen3-4b-2507",
  "loaded_model": { "id": "qwen/qwen3-4b-2507", "state": "loaded" }
}
```

---

### 7.3 列出可用模型

**GET** `/api/v1/knowledge-graph/rag/llm/models`

**响应示例**

```json
{
  "data": [
    { "id": "qwen/qwen3-4b-2507", "state": "loaded", "size": 4000000000 }
  ]
}
```

---

### 7.4 加载模型

**POST** `/api/v1/knowledge-graph/rag/llm/load`

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 否 | 模型 ID，不填则使用 .env 默认模型 |

---

### 7.5 GraphRAG 智能问答

**POST** `/api/v1/knowledge-graph/rag/query`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| question | string | 是 | 用户问题 |
| return_context | boolean | 否 | 是否返回检索到的图谱上下文 |

**请求示例**

```json
{
  "question": "钙钛矿有哪些性能特点？",
  "return_context": true
}
```

**响应示例**

```json
{
  "question": "钙钛矿有哪些性能特点？",
  "answer": "钙钛矿材料具有以下性能特点：\n1. 高光电转换效率（PCE可达25%以上）\n2. 带隙可调节...\n3. 制备成本低...",
  "keywords": ["钙钛矿", "光电转换效率", "带隙", "成本"],
  "context": {
    "nodes": [
      { "label": "Material", "properties": { "id": "钙钛矿", "formula": "CH3NH3PbI3" } }
    ],
    "relations": [
      { "source": { "id": "钙钛矿" }, "relation": "HAS_PROPERTY", "target": { "id": "高效率" } }
    ]
  }
}
```

---

### 7.6 图谱统计

**GET** `/api/v1/knowledge-graph/rag/graph/stats`

**响应示例**

```json
{
  "total_nodes": 150,
  "total_relations": 320,
  "node_labels": {
    "Material": 50,
    "Property": 40,
    "Method": 30,
    "Document": 20,
    "Result": 10
  },
  "relation_types": {
    "HAS_PROPERTY": 150,
    "PRODUCED_BY": 80,
    "IMPROVES": 50,
    "CORRELATES_WITH": 40
  }
}
```

---

### 7.7 文档索引（实体+关系批量入库）

**POST** `/api/v1/knowledge-graph/rag/index/document`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| doc_id | string | 是 | 文档唯一标识 |
| doc_title | string | 是 | 文档标题 |
| entities | array | 是 | 实体列表 |
| relations | array | 是 | 关系列表 |
| metadata | object | 否 | 额外元数据 |

**entities 格式**:
```json
[
  { "text": "钙钛矿", "entity_type": "Material" },
  { "text": "高效率", "entity_type": "Property" }
]
```

**relations 格式**:
```json
[
  {
    "source": "钙钛矿",
    "source_type": "Material",
    "target": "高效率",
    "target_type": "Property",
    "relation_type": "HAS_PROPERTY",
    "context": "钙钛矿具有高光电转换效率"
  }
]
```

**响应示例**

```json
{
  "message": "文档索引完成",
  "doc_id": "uuid",
  "entities_imported": 12,
  "relations_imported": 8,
  "doc_entity_links": 12
}
```

---

### 7.8 按标签查询图谱节点

**GET** `/api/v1/knowledge-graph/rag/graph/nodes/{label}`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | integer | 否 | 50 | 返回数量 (1-200) |

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| label | string | 是 | 节点标签 (Material, Property, Method 等) |

**响应示例**

```json
{
  "label": "Material",
  "count": 50,
  "nodes": [
    {
      "id": "钙钛矿",
      "label": "Material",
      "properties": {
        "name": "钙钛矿",
        "formula": "CH3NH3PbI3"
      }
    }
  ]
}
```

---

### 7.9 关键词搜索图谱节点

**GET** `/api/v1/knowledge-graph/rag/graph/search/{keyword}`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | integer | 否 | 20 | 返回数量 (1-100) |

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |

**响应示例**

```json
{
  "keyword": "钙钛矿",
  "count": 15,
  "nodes": [
    {
      "id": "钙钛矿-001",
      "label": "Material",
      "properties": {
        "name": "钙钛矿",
        "formula": "CH3NH3PbI3"
      }
    }
  ]
}
```

---

### 7.10 添加图谱节点

**POST** `/api/v1/knowledge-graph/rag/graph/nodes`

**权限**: `admin`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| label | string | 是 | 节点标签 (Material, Property, Method 等) |
| id | string | 是 | 节点唯一标识 |
| properties | object | 否 | 节点属性 |

**请求示例**

```json
{
  "label": "Material",
  "id": "钙钛矿-001",
  "properties": {
    "name": "钙钛矿",
    "formula": "CH3NH3PbI3",
    "category": "有机-无机杂化钙钛矿"
  }
}
```

**响应示例**

```json
{
  "message": "节点创建成功",
  "node": {
    "id": "钙钛矿-001",
    "label": "Material",
    "properties": {...}
  }
}
```

---

### 7.11 添加图谱关系

**POST** `/api/v1/knowledge-graph/rag/graph/relations`

**权限**: `admin`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_label | string | 是 | 源节点标签 |
| source_id | string | 是 | 源节点 ID |
| target_label | string | 是 | 目标节点标签 |
| target_id | string | 是 | 目标节点 ID |
| rel_type | string | 是 | 关系类型 (HAS_PROPERTY, PRODUCED_BY 等) |
| properties | object | 否 | 关系属性 |

**请求示例**

```json
{
  "source_label": "Material",
  "source_id": "钙钛矿",
  "target_label": "Property",
  "target_id": "高效率",
  "rel_type": "HAS_PROPERTY",
  "properties": {
    "value": 25.5,
    "unit": "%"
  }
}
```

**响应示例**

```json
{
  "message": "关系创建成功",
  "relation": {
    "source": "钙钛矿",
    "target": "高效率",
    "type": "HAS_PROPERTY"
  }
}
```

---

### 7.12 清空图谱

**DELETE** `/api/v1/knowledge-graph/rag/graph/clear`

**权限**: `admin`

**警告**: 此操作将删除图谱中的所有节点和关系，不可恢复！

**响应示例**

```json
{
  "message": "图谱已清空",
  "deleted_nodes": 150,
  "deleted_relations": 320
}
```

---

### 7.13 直接调用 LLM 生成

**POST** `/api/v1/knowledge-graph/rag/llm/generate`

**说明**: 直接调用 LLM 生成文本（不经过 GraphRAG），用于测试 LLM 连接或不需要图谱检索的场景。

**请求体**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| prompt | string | 是 | - | 用户提示词 |
| system_prompt | string | 否 | - | 系统提示词 |
| temperature | float | 否 | 0.7 | 温度参数 (0-2) |
| max_tokens | integer | 否 | 1024 | 最大生成 token 数 (1-8192) |

**请求示例**

```json
{
  "prompt": "请介绍一下钙钛矿太阳能电池的优缺点",
  "system_prompt": "你是一个专业的材料科学助手",
  "temperature": 0.7,
  "max_tokens": 512
}
```

**响应示例**

```json
{
  "prompt": "请介绍一下钙钛矿太阳能电池的优缺点",
  "answer": "钙钛矿太阳能电池具有以下优点：\n1. 高光电转换效率...\n2. 制备成本低...\n\n缺点：\n1. 稳定性问题...\n2. 含铅毒性...",
  "raw": {...}
}
```

---

### 7.14 卸载 LLM 模型

**POST** `/api/v1/knowledge-graph/rag/llm/unload`

**说明**: 卸载当前加载的 LLM 模型，释放显存/内存。

**响应示例**

```json
{
  "message": "模型已卸载"
}
```

---

### 7.15 查询历史记录

**GET** `/api/v1/knowledge-graph/rag/query/history`

**说明**: 获取最近 20 条问答历史记录。

**响应示例**

```json
{
  "history": [
    {
      "question": "钙钛矿有哪些性能特点？",
      "answer": "钙钛矿材料具有以下性能特点...",
      "keywords": ["钙钛矿", "光电转换效率"],
      "timestamp": "2026-05-12T10:30:00Z"
    }
  ]
}
```

---

## 十一、Webhooks 与回调接口

### 11.1 任务完成回调

**POST** `/api/v1/callbacks/task-complete`

**说明**: Celery 任务完成后回调此接口，用于触发后续流程（如文档解析完成后自动触发信息抽取）。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | 是 | 任务 ID |
| task_type | string | 是 | 任务类型 |
| document_id | string | 否 | 关联文档 ID |
| result | object | 否 | 任务结果 |

**请求示例**

```json
{
  "task_id": "uuid",
  "task_type": "parsing",
  "document_id": "uuid",
  "result": {
    "pages_parsed": 15,
    "elements_extracted": 120
  }
}
```

---

## 十二、导入/导出接口

### 12.1 导出标注数据

**GET** `/api/v1/annotations/export`

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| document_id | string | 否 | - | 文档 ID |
| format | string | 否 | json | 导出格式 (json/csv) |
| annotation_type | string | 否 | - | 标注类型 |

**响应**

```json
{
  "code": 200,
  "data": {
    "filename": "annotations_2024-01-15.json",
    "count": 50,
    "content": [...]
  }
}
```

---

### 12.2 批量导入标注数据

**POST** `/api/v1/annotations/import`

**Content-Type**: `multipart/form-data`

**表单参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 标注数据文件 (JSON/CSV) |
| document_id | string | 是 | 目标文档 ID |

**响应示例**

```json
{
  "code": 200,
  "message": "导入成功",
  "data": {
    "imported": 45,
    "skipped": 5,
    "errors": []
  }
}
```

---

## 十三、速率限制

### 13.1 限流规则

| 接口类型 | 限制 | 窗口 |
|----------|------|------|
| 通用 API | 100 次/分钟 | 按 IP |
| 文件上传 | 10 次/分钟 | 按用户 |
| LLM 生成 | 5 次/分钟 | 按用户 |
| GraphRAG 问答 | 20 次/分钟 | 按用户 |

### 13.2 限流响应

当请求超过限制时，返回 429 错误：

```json
{
  "code": 429,
  "message": "请求频率过高，请稍后再试",
  "retry_after": 60
}
```

---

## 十四、附录

### 14.1 实体类型枚举

| 类型 | 说明 |
|------|------|
| Material | 材料 |
| Property | 性能指标 |
| Method | 方法技术 |
| Parameter | 实验参数 |
| Document | 文献 |
| Result | 实验结果 |

### 14.2 关系类型枚举

| 类型 | 说明 | 示例 |
|------|------|------|
| HAS_PROPERTY | 具有性能 | 钙钛矿 → HAS_PROPERTY → 高效率 |
| PRODUCED_BY | 由...制备 | 薄膜 → PRODUCED_BY → 旋涂法 |
| IMPROVES | 改善 | 退火 → IMPROVES → 结晶度 |
| CORRELATES_WITH | 与...相关 | 温度 → CORRELATES_WITH → 带隙 |
| CITES | 引用 | 论文A → CITES → 论文B |
| DERIVED_FROM | 衍生于 | FAPbI3 → DERIVED_FROM → MAPbI3 |

### 14.3 标注状态枚举

| 状态 | 说明 |
|------|------|
| draft | 草稿 |
| submitted | 已提交 |
| approved | 已通过 |
| rejected | 已驳回 |
| merged | 已合并 |

### 14.4 任务状态枚举

| 状态 | 说明 |
|------|------|
| pending | 等待中 |
| running | 运行中 |
| paused | 已暂停 |
| completed | 已完成 |
| failed | 失败 |
| cancelled | 已取消 |

---

## 十五、主动学习模块 (Active Learning)

### 15.1 主动学习采样

**POST** `/api/v1/active-learning/select`

**权限**: 需登录

**说明**: 从待标注样本池中挑选优先标注样本，支持不确定性采样（熵/最小置信度/边缘）、多样性采样（Core-Set/K-Means++）、QBC（投票熵/分歧度）与混合策略；纯 Python 零依赖，可插拔可降级。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| samples | array | 是 | 样本池；每项含 `id`/`text`（可选）、`probs`（概率分布）、`features`（特征向量）、`predictions`（委员会各成员概率分布列表） |
| strategy | string | 否 | uncertainty \| diversity \| qbc \| hybrid（默认 hybrid） |
| top_k | integer | 否 | 返回数量 (1-200，默认 10) |
| uncertainty_method | string | 否 | entropy \| least_confidence \| margin |
| diversity_method | string | 否 | core_set \| kmeans |
| qbc_method | string | 否 | vote_entropy \| disagreement |

**请求示例**

```json
{
  "samples": [
    {"id": "a", "probs": [0.9, 0.1]},
    {"id": "b", "probs": [0.5, 0.5]},
    {"id": "c", "probs": [0.33, 0.33, 0.34]}
  ],
  "strategy": "uncertainty",
  "top_k": 2,
  "uncertainty_method": "entropy"
}
```

**响应示例**

```json
{
  "strategy": "uncertainty",
  "backend": "builtin",
  "top_k": 2,
  "total": 3,
  "selected": 2,
  "results": [
    {"index": 2, "score": 0.9964, "method": "entropy", "id": "c"},
    {"index": 1, "score": 1.0, "method": "entropy", "id": "b"}
  ]
}
```

---

## 十六、数据/模型版本管理模块 (Version Management)

**权限**: 需登录（所有接口）

**说明**: 围绕 DVC 数据版本 + MLflow 实验追踪/模型注册 + 自动重训管道；纯 Python 零依赖，可插拔可降级。

### 16.1 记录数据集版本

**POST** `/api/v1/version-management/datasets`

**说明**: DVC 风格内容寻址版本记录：计算数据集内容哈希、记录血缘（来源/流程/标注员）与质量评估快照（样本数/类别分布/缺失数），版本号自动递增。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 数据集名称 |
| data | array | 否 | 数据集记录；每项为 dict 或对象 |
| source | string | 否 | 数据来源 |
| pipeline | string | 否 | 处理流程 |
| annotators | array | 否 | 标注员标识列表 |
| label_key | string | 否 | 标签字段名（默认 label） |

**响应示例**

```json
{
  "name": "ner-train",
  "version": 3,
  "hash": "9f2c...",
  "n_records": 200,
  "quality": {"n_records": 200, "n_labeled": 198, "n_missing": 2, "n_categories": 6, "distribution": {"Material": 120}},
  "source": "annotations",
  "pipeline": "ner-pipeline",
  "annotators": ["u1", "u2"]
}
```

---

### 16.2 列出数据集版本

**GET** `/api/v1/version-management/datasets`

**响应示例**

```json
{
  "ner-train": [
    {"name": "ner-train", "version": 1, "hash": "...", "n_records": 100},
    {"name": "ner-train", "version": 2, "hash": "...", "n_records": 200}
  ]
}
```

---

### 16.3 记录实验

**POST** `/api/v1/version-management/experiments`

**说明**: MLflow 风格实验追踪：记录训练参数、评估指标、关联模型版本与标签。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 实验名称 |
| params | object | 否 | 训练参数 |
| metrics | object | 否 | 评估指标 |
| model_name | string | 否 | 关联模型名 |
| model_version | integer | 否 | 关联模型版本 |
| tags | object | 否 | 标签 |

**响应示例**

```json
{"id": "exp-0003", "name": "ner-finetune", "params": {"lr": 0.001}, "metrics": {"f1": 0.92}, "model_name": "ner", "model_version": 2}
```

---

### 16.4 列出实验

**GET** `/api/v1/version-management/experiments?name={name}`

---

### 16.5 多实验对比

**POST** `/api/v1/version-management/experiments/compare`

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| experiment_ids | array | 否 | 实验 id 列表；缺省对比全部 |

**响应示例**

```json
{"n_experiments": 2, "metrics": {"f1": {"exp-0001": 0.8, "exp-0002": 0.92}}, "best": {"f1": "exp-0002"}}
```

---

### 16.6 注册模型

**POST** `/api/v1/version-management/models`

**说明**: 注册模型新版本，初始阶段 Staging；版本号在模型内自增。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 模型名称 |
| artifacts | object | 否 | 模型产物（文件路径/哈希等） |
| metrics | object | 否 | 评估指标 |
| experiment_id | string | 否 | 关联实验 id |
| description | string | 否 | 版本描述 |

**响应示例**

```json
{"name": "ner", "version": 2, "stage": "staging", "metrics": {"f1": 0.92}, "artifacts": {}, "experiment_id": "exp-0002"}
```

---

### 16.7 列出模型

**GET** `/api/v1/version-management/models`

---

### 16.8 模型阶段流转

**POST** `/api/v1/version-management/models/stage`

**说明**: Staging → Production → Archived 单向流转；晋升 Production 自动归档旧 Production 版本。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 模型名称 |
| version | integer | 是 | 模型版本号 |
| stage | string | 是 | staging \| production \| archived |

**响应示例**

```json
{"ok": true, "model": {"name": "ner", "version": 2, "stage": "production"}, "changed": true, "archived_previous": 1}
```

---

### 16.9 自动重训触发评估

**POST** `/api/v1/version-management/retrain/check`

**说明**: 评估是否触发自动重训，触发条件：手动（force）/ 新标注达到阈值（默认 `RETRAIN_THRESHOLD=100`）/ 定期（默认 `RETRAIN_PERIODIC_DAYS=7` 天）。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| new_annotated | integer | 否 | 新标注样本数 |
| last_train_count | integer | 否 | 上次训练时样本数 |
| threshold | integer | 否 | 触发阈值（缺省用配置） |
| periodic_days | integer | 否 | 定期触发间隔（缺省用配置） |
| last_train_age_days | number | 否 | 距上次训练天数 |
| force | boolean | 否 | 手动强制触发 |

**响应示例**

```json
{"trigger": true, "reasons": ["threshold"], "threshold": 100, "periodic_days": 7}
```

---

### 16.10 启动自动重训管道

**POST** `/api/v1/version-management/retrain/run`

**说明**: 分段执行数据准备 → 训练 → 评估 → 注册 → 部署；失败按 `max_retries` 重试并回滚。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_name | string | 是 | 模型名称 |
| trigger_reason | string | 否 | manual \| threshold \| periodic |
| max_retries | integer | 否 | 分段失败最大重试次数（缺省用配置） |

**响应示例**

```json
{"id": "pipe-0001", "model_name": "ner", "trigger": "manual", "status": "completed", "steps": [{"step": "training", "status": "success", "attempt": 1}]}
```

---

### 16.11 查询重训管道状态

**GET** `/api/v1/version-management/retrain/{run_id}`

---

## 十七、置信度校准与漂移检测模块 (Calibration & Drift)

**权限**: 需登录（所有接口）

**说明**: Temperature/Platt Scaling 置信度校准、ECE 校准质量评估、PSI/KS/卡方数据漂移告警；纯 Python 零依赖，可插拔可降级。

### 17.1 置信度校准

**POST** `/api/v1/calibration-drift/calibrate`

**说明**: `temperature` 对 logits 做温度缩放（未显式给 temperature 且提供 labels 时自动拟合 T）；`platt` 对二分类 scores 拟合 `sigmoid(a*s+b)`。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| method | string | 否 | temperature \| platt（默认 temperature） |
| logits | array | 否 | temperature 校准的 logits 矩阵 |
| labels | array | 否 | temperature 校准的真实类别（拟合 T 用） |
| scores | array | 否 | platt 校准的二分类置信度 |
| binary_labels | array | 否 | platt 校准的二分类标签 (0/1) |
| temperature | number | 否 | 显式温度（缺省自动拟合） |

**响应示例**

```json
{"ok": true, "method": "temperature", "temperature": 0.8, "probs": [[0.65, 0.35]]}
```

---

### 17.2 校准质量评估

**POST** `/api/v1/calibration-drift/evaluate`

**说明**: 计算 Expected Calibration Error（ECE）与可靠性曲线（分箱置信度/准确率/样本数）。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| probs | array | 是 | 预测概率（正类） |
| labels | array | 是 | 真实标签（0/1） |
| n_bins | integer | 否 | 分箱数（缺省用配置 `CALIBRATION_ECE_BINS`） |

**响应示例**

```json
{"ece": 0.054, "n_bins": 10, "reliability": [{"bin": 0, "range": [0.0, 0.1], "count": 12, "confidence": 0.05, "accuracy": 0.0}]}
```

---

### 17.3 数据漂移检测

**POST** `/api/v1/calibration-drift/detect`

**说明**: 数值漂移用 PSI（默认）或 KS 统计量；类别漂移（`categorical=true`）用卡方统计量；按阈值分级输出 stable / warning / drift。

**请求体**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| reference | array | 是 | 参考分布（数值列表或类别列表） |
| current | array | 是 | 当前分布 |
| method | string | 否 | psi \| ks（数值漂移） |
| categorical | boolean | 否 | 是否为类别分布 |

**响应示例**

```json
{"method": "psi", "value": 0.31, "status": "drift", "warning": 0.1, "alert": 0.25}
```
