# Frontend 前端应用

多模态科学文献智能解析平台前端应用 - React + TypeScript + Vite

## 🎯 项目状态

✅ **前端核心功能已完成并配置**

### 已完成的模块

#### 1. ✅ 核心配置
- **vite.config.ts** - Vite配置完善
  - React插件配置
  - 路径别名配置
  - 开发服务器代理(后端API)
  - 构建优化(代码分割)
  
- **tsconfig.json** - TypeScript配置完善

- **tailwind.config.js** - Tailwind CSS配置

- **.env.development/.env.production** - 环境配置
  - API地址配置正确
  - WebSocket地址配置

#### 2. ✅ API接口层
- **src/api/index.ts** - Axios配置
  - 请求拦截器(Token自动添加)
  - 响应拦截器(401处理、Token刷新)
  - 错误处理和提示
  
- **src/api/modules.ts** - API模块完整
  - authApi - 认证接口
  - documentApi - 文档接口
  - taskApi - 任务接口
  - annotationApi - 标注接口
  - graphApi - 图谱接口

#### 3. ✅ 类型定义
- **src/types/index.ts** - TypeScript类型完整
  - User类型
  - Document类型
  - Task类型
  - Annotation类型
  - Graph类型
  - API响应类型

#### 4. ✅ 状态管理
- **src/store/authStore.ts** - 认证状态(Zustand)
  - 用户信息存储
  - 登录/登出方法
  - Token管理
  
- **src/store/documentStore.ts** - 文档状态
  - 文档列表管理
  - 分页筛选
  - CRUD操作

- **src/store/uiStore.ts** - UI状态

#### 5. ✅ 路由配置
- **src/router/index.ts** - 路由配置完整
  - 登录页
  - Dashboard仪表盘
  - 文档列表/详情
  - 标注工作台
  - 知识图谱
  - 任务列表
  - 用户设置
  
- **src/router/guards.ts** - 路由守卫

#### 6. ✅ 页面组件
- **LoginPage** - 登录页
- **DashboardPage** - 仪表盘
- **DocumentListPage** - 文档列表
- **DocumentDetailPage** - 文档详情
- **AnnotationWorkspace** - 标注工作台
- **GraphExplorer** - 知识图谱探索
- **GraphRAGPage** - GraphRAG 智能问答
- **TaskListPage** - 任务列表
- **ProfilePage** - 个人设置
- **NotFoundPage** - 404页面

#### 7. ✅ 核心组件
- **MainLayout** - 主布局
- **Header** - 头部导航
- **Sidebar** - 侧边栏
- **PDFViewer** - PDF查看器
- **AnnotationPanel** - 标注面板
- **ForceGraph** - 图谱可视化

#### 8. ✅ Hooks
- **useWebSocket** - WebSocket连接
- **usePagination** - 分页处理

#### 9. ✅ 样式配置
- **src/styles/global.css** - 全局样式

## 🚀 快速启动

### 1. 安装依赖

```bash
cd frontend

# 使用pnpm安装(推荐)
pnpm install

# 或使用npm
npm install
```

### 2. 配置检查

确认 `.env.development` 配置正确:
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

### 3. 启动后端服务

**重要**: 前端依赖后端API,必须先启动后端

```bash
# 在另一个终端
cd ../backend
python scripts/init_db.py  # 首次启动初始化数据库
uvicorn app.main:app --reload --port 8000
```

### 4. 启动前端

```bash
# 使用启动脚本
bash start.sh

# 或直接启动
pnpm dev
```

### 5. 访问应用

打开浏览器访问:
- **前端应用**: http://localhost:3000
- **API文档**: http://localhost:8000/docs

## 📋 功能说明

### 登录功能
- 默认管理员: **admin/admin123**
- Token自动管理
- 自动Token刷新

### 文档管理
- PDF文件上传
- 文档列表查看(分页、筛选)
- 文档详情查看
- 触发解析任务
- 删除文档

### PDF查看
- PDF.js集成
- 页面导航
- 缩放和旋转
- 文本选择

### 标注工作台
- 实体标注（Material/Property/Method/Parameter/Result 五种类型）
- 关系标注（HAS_PROPERTY/PRODUCED_BY/IMPROVES/CORRELATES_WITH）
- 历史记录查看
- 保存与提交审核

### 知识图谱
- 力导向图可视化
- 实体搜索
- 关系浏览
- 统计信息

### 任务管理
- 任务列表（状态/类型筛选、分页）
- 暂停、恢复、终止、重试操作
- 任务详情抽屉（错误信息、执行结果）
- 自动刷新（运行中任务每5秒）

## 🔧 开发指南

### 项目结构

```
frontend/
├── src/
│   ├── api/              # ✅ API接口层
│   │   ├── index.ts      # Axios配置
│   │   └ modules.ts      # API模块
│   ├── components/       # ✅ 通用组件
│   │   ├── Layout/       # 布局组件
│   │   ├── PDFViewer/    # PDF查看器
│   │   ├── Annotation/   # 标注组件
│   │   └── Graph/        # 图谱组件
│   ├── hooks/            # ✅ 自定义Hooks
│   ├── pages/            # ✅ 页面组件
│   │   ├── Login/        # 登录页
│   │   ├── Dashboard/    # 仪表盘
│   │   ├── Documents/    # 文档页
│   │   ├── Annotation/   # 标注页
│   │   ├── KnowledgeGraph/ # 图谱页
│   │   ├── Tasks/        # 任务页
│   │   └ Settings/       # 设置页
│   │   └ NotFound/       # 404页
│   ├── router/           # ✅ 路由配置
│   ├── store/            # ✅ 状态管理(Zustand)
│   ├── styles/           # 样式文件
│   ├── types/            # ✅ 类型定义
│   ├── App.tsx           # 应用入口
│   └ main.tsx            # 主入口
│   └── vite-env.d.ts     # Vite环境类型
├── public/               # 静态资源
├── .env.development      # ✅ 开发环境配置
├── .env.production       # ✅ 生产环境配置
├── package.json          # ✅ 依赖配置
├── vite.config.ts        # ✅ Vite配置
├── tsconfig.json         # ✅ TypeScript配置
├── tailwind.config.js    # Tailwind配置
├── pnpm-lock.yaml        # 锁定文件
├── start.sh              # ✅ 启动脚本
├── API_INTERFACE_CONFIG.md  # ✅ API接口文档
└── README_FRONTEND.md    # 本文档
```

### 开发命令

```bash
# 开发
pnpm dev

# 构建
pnpm build

# 类型检查
pnpm type-check

# 代码检查
pnpm lint
pnpm lint:fix

# 代码格式化
pnpm format

# 预览生产构建
pnpm preview
```

### 技术栈

- **框架**: React 18
- **语言**: TypeScript 5
- **构建**: Vite 5
- **UI库**: Ant Design 5
- **状态**: Zustand 4
- **请求**: Axios + React Query
- **路由**: React Router 6
- **PDF**: PDF.js + React-PDF
- **图谱**: React-Force-Graph
- **图表**: ECharts
- **样式**: Tailwind CSS
- **公式**: KaTeX

### API调用示例

#### 登录
```typescript
import { authApi } from '@/api/modules';
import { useAuthStore } from '@/store/authStore';

const handleLogin = async (username: string, password: string) => {
  try {
    await authApi.login(username, password);
    useAuthStore.getState().fetchUser();
  } catch (error) {
    console.error('登录失败:', error);
  }
};
```

#### 上传文档
```typescript
import { documentApi } from '@/api/modules';

const handleUpload = async (file: File) => {
  try {
    const doc = await documentApi.upload(file);
    console.log('上传成功:', doc);
  } catch (error) {
    console.error('上传失败:', error);
  }
};
```

#### 使用React Query
```typescript
import { useQuery } from '@tanstack/react-query';
import { documentApi } from '@/api/modules';

const { data, isLoading } = useQuery({
  queryKey: ['documents'],
  queryFn: () => documentApi.getList({ page: 1, page_size: 10 }),
});
```

## 🌐 前后端连接

### 接口映射

所有接口已完整配置并连接后端:

| 功能 | 前端方法 | 后端端点 | 状态 |
|------|---------|---------|------|
| 登录 | authApi.login | POST /api/v1/auth/login | ✅ |
| 注册 | authApi.register | POST /api/v1/auth/register | ✅ |
| 上传文档 | documentApi.upload | POST /api/v1/documents/upload | ✅ |
| 文档列表 | documentApi.getList | GET /api/v1/documents/ | ✅ |
| 文档详情 | documentApi.getById | GET /api/v1/documents/:id | ✅ |
| 触发解析 | documentApi.triggerParse | POST /api/v1/documents/:id/parse | ✅ |
| 任务列表 | taskApi.getList | GET /api/v1/tasks/ | ✅ |
| 创建标注 | annotationApi.create | POST /api/v1/annotations/ | ✅ |
| 图谱搜索 | graphApi.search | GET /api/v1/knowledge-graph/search | ✅ |

详细接口配置请查看: [API_INTERFACE_CONFIG.md](./API_INTERFACE_CONFIG.md)

## ⚙️ 环境变量

### 开发环境 (.env.development)
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
VITE_APP_TITLE=科学文献解析平台 (开发)
```

### 生产环境 (.env.production)
```bash
VITE_API_BASE_URL=/api/v1
VITE_WS_URL=ws://your-domain/ws
VITE_APP_TITLE=科学文献解析平台
```

## 🔒 路由守卫

所有页面都有authGuard保护,未登录会自动跳转到登录页。

## 📦 构建和部署

### 构建
```bash
pnpm build
```

### Docker部署
```bash
docker build -t frontend-app .
docker run -p 80:80 frontend-app
```

### 预览构建结果
```bash
pnpm preview
```

## 🐛 问题排查

### 1. API请求失败
- 检查后端是否启动: http://localhost:8000/health
- 检查Token是否有效
- 查看浏览器控制台错误信息
- 检查CORS配置

### 2. 依赖安装失败
- 清除缓存: `pnpm store prune`
- 删除node_modules重新安装
- 检查Node版本(需要Node 18+)

### 3. TypeScript类型错误
- 运行类型检查: `pnpm type-check`
- 检查tsconfig配置
- 确保所有类型定义文件存在

### 4. PDF无法加载
- 检查PDF.js worker配置
- 确认PDF文件路径正确
- 检查CORS设置

## 📚 相关文档

- [API接口配置](./API_INTERFACE_CONFIG.md) - 前后端接口详细说明
- [后端文档](../backend/README_BACKEND.md) - 后端使用说明
- [数据库设计](../01-数据库设计.md) - 数据库表结构
- [API接口文档](../05-API接口文档.md) - API详细定义

## ✅ 完成清单

- ✅ Vite配置完善
- ✅ TypeScript类型定义
- ✅ API接口层完整
- ✅ 状态管理配置
- ✅ 路由配置完整
- ✅ 所有页面组件
- ✅ 核心功能组件
- ✅ 前后端连接配置
- ✅ 环境配置正确
- ✅ 启动脚本创建
- ✅ 文档完善

## 🎯 状态总结

**🎉 前端核心功能已完成,前后端已完全配置并连接**

可以立即:
1. 启动后端服务(http://localhost:8000)
2. 启动前端服务(http://localhost:3000)
3. 使用admin/admin123登录
4. 上传PDF文档测试完整流程

---

**最后更新**: 2026-04-28
**版本**: 1.1.0
**状态**: ✅ 已完成（含标注工作台完善、个人设置、任务管理增强）