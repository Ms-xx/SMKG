# 前后端API接口配置说明

## 🎯 接口连接状态

✅ **前后端已完全配置并连接**

### 1. 后端API地址配置

#### 开发环境 (.env.development)
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

#### 生产环境 (.env.production)
```bash
VITE_API_BASE_URL=/api/v1
VITE_WS_URL=ws://your-production-domain/ws
```

### 2. Vite代理配置

已在 `vite.config.ts` 中配置代理：

```typescript
server: {
  port: 3000,
  proxy: {
    "/api": {
      target: "http://localhost:8000",
      changeOrigin: true,
    },
  },
}
```

### 3. Axios请求拦截器配置

已在 `src/api/index.ts` 中完善配置：

#### 请求拦截器
- ✅ 自动添加Authorization头
- ✅ 从localStorage读取access_token
- ✅ 设置Bearer Token格式

#### 响应拦截器
- ✅ 自动处理401错误
- ✅ Token刷新逻辑
- ✅ 错误消息提示
- ✅ 失败后跳转登录页

### 4. API模块完整实现

#### ✅ authApi (认证模块)
- `login()` - POST /auth/login
- `register()` - POST /auth/register  
- `logout()` - POST /auth/logout
- `getCurrentUser()` - GET /auth/me

#### ✅ documentApi (文档模块)
- `upload()` - POST /documents/upload
- `getList()` - GET /documents/
- `getById()` - GET /documents/:id
- `delete()` - DELETE /documents/:id
- `triggerParse()` - POST /documents/:id/parse
- `getPageElements()` - GET /documents/:id/pages/:num/elements

#### ✅ taskApi (任务模块)
- `getList()` - GET /tasks/
- `getById()` - GET /tasks/:id
- `create()` - POST /tasks/
- `cancel()` - POST /tasks/:id/cancel

#### ✅ annotationApi (标注模块)
- `create()` - POST /annotations/
- `getByDocument()` - GET /annotations/document/:id
- `update()` - PUT /annotations/:id
- `submit()` - POST /annotations/:id/submit
- `review()` - POST /annotations/:id/review
- `getVersions()` - GET /annotations/:id/versions

#### ✅ graphApi (图谱模块)
- `search()` - GET /knowledge-graph/search
- `getEntity()` - GET /knowledge-graph/entities/:id
- `getEntityRelations()` - GET /knowledge-graph/entities/:id/relations
- `executeCypher()` - POST /knowledge-graph/query
- `getStatistics()` - GET /knowledge-graph/statistics

### 5. Zustand状态管理

#### ✅ authStore (认证状态)
- 用户信息存储
- 登录/登出方法
- Token管理
- 自动fetchUser

#### ✅ documentStore (文档状态)
- 文档列表管理
- 当前文档
- 分页和筛选
- 上传/删除/解析触发

### 6. React Query配置

在 `main.tsx` 中已配置：

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
```

## 📋 API接口映射表

| 前端方法 | 后端端点 | 说明 |
|---------|---------|------|
| authApi.login | POST /api/v1/auth/login | 用户登录 |
| authApi.register | POST /api/v1/auth/register | 用户注册 |
| documentApi.upload | POST /api/v1/documents/upload | 上传PDF |
| documentApi.getList | GET /api/v1/documents/ | 文档列表 |
| documentApi.getById | GET /api/v1/documents/:id | 文档详情 |
| documentApi.triggerParse | POST /api/v1/documents/:id/parse | 触发解析 |
| taskApi.getList | GET /api/v1/tasks/ | 任务列表 |
| annotationApi.create | POST /api/v1/annotations/ | 创建标注 |
| graphApi.search | GET /api/v1/knowledge-graph/search | 图谱搜索 |

## 🔧 使用示例

### 1. 登录示例

```typescript
import { authApi } from '@/api/modules';
import { useAuthStore } from '@/store/authStore';

// 在组件中使用
const handleLogin = async (username: string, password: string) => {
  try {
    await authApi.login(username, password);
    // Token会自动保存到localStorage
    // 用户信息会自动fetch
  } catch (error) {
    console.error('登录失败:', error);
  }
};
```

### 2. 上传文档示例

```typescript
import { documentApi } from '@/api/modules';
import { useDocumentStore } from '@/store/documentStore';

const handleUpload = async (file: File, title?: string) => {
  try {
    const doc = await documentApi.upload(file, title);
    console.log('上传成功:', doc);
    // 可以使用store自动刷新列表
    useDocumentStore.getState().fetchDocuments();
  } catch (error) {
    console.error('上传失败:', error);
  }
};
```

### 3. 触发解析示例

```typescript
import { documentApi } from '@/api/modules';

const handleParse = async (documentId: string) => {
  try {
    const result = await documentApi.triggerParse(documentId);
    console.log('解析任务已提交:', result.task_id);
    // 可以跳转到任务页面查看进度
  } catch (error) {
    console.error('解析失败:', error);
  }
};
```

### 4. 使用React Query

```typescript
import { useQuery, useMutation } from '@tanstack/react-query';
import { documentApi } from '@/api/modules';

// 查询文档列表
const { data, isLoading } = useQuery({
  queryKey: ['documents', page, pageSize],
  queryFn: () => documentApi.getList({ page, page_size: pageSize }),
});

// 上传文档
const uploadMutation = useMutation({
  mutationFn: (data: { file: File; title?: string }) => 
    documentApi.upload(data.file, data.title),
  onSuccess: () => {
    // 刷新列表
    queryClient.invalidateQueries({ queryKey: ['documents'] });
  },
});
```

## 🌐 WebSocket连接

### 配置
WebSocket URL配置在 `.env.development`:
```
VITE_WS_URL=ws://localhost:8000/ws
```

### 使用示例

```typescript
import useWebSocket from '@/hooks/useWebSocket';

// 在组件中使用
const { sendMessage, lastMessage, connectionStatus } = useWebSocket(
  `${import.meta.env.VITE_WS_URL}/tasks/${taskId}`
);

// 监听任务进度
useEffect(() => {
  if (lastMessage) {
    const data = JSON.parse(lastMessage.data);
    console.log('任务进度:', data);
  }
}, [lastMessage]);
```

## 🔄 Token刷新机制

### 自动刷新流程
1. 请求拦截器检查localStorage中的access_token
2. 401错误触发Token刷新
3. 使用refresh_token获取新token
4. 更新localStorage
5. 重新发起原请求

### 手动刷新

```typescript
import axios from 'axios';

const refreshToken = async () => {
  const refreshToken = localStorage.getItem('refresh_token');
  const response = await axios.post('/api/v1/auth/refresh', {
    refresh_token: refreshToken
  });
  const { access_token, refresh_token } = response.data;
  localStorage.setItem('access_token', access_token);
  localStorage.setItem('refresh_token', refresh_token);
};
```

## ⚠️ 注意事项

### 1. CORS配置
后端已配置CORS,允许前端地址:
```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Token存储
- access_token 存储在 localStorage
- refresh_token 存储在 localStorage  
- ⚠️ 生产环境建议使用更安全的存储方式

### 3. 错误处理
- 所有API错误会自动显示message提示
- 401错误自动处理Token刷新
- 其他错误需要手动catch处理

### 4. 开发环境
确保同时启动:
- 后端: http://localhost:8000
- 前端: http://localhost:3000
- Redis: localhost:6379
- Neo4j: bolt://localhost:7687
- MySQL: localhost:3306

## 🚀 启动顺序

### 推荐启动顺序

1. **启动数据库服务**
   ```bash
   # MySQL、Redis、Neo4j
   ```

2. **启动后端**
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8000
   celery -A app.core.celery_app worker -l info
   ```

3. **启动前端**
   ```bash
   cd frontend
   pnpm install  # 如果依赖未安装
   pnpm dev
   ```

4. **访问应用**
   - 前端: http://localhost:3000
   - 后端API文档: http://localhost:8000/docs

## 📊 接口测试流程

### 1. 登录测试
```bash
# 前端登录
访问: http://localhost:3000/login
用户名: admin
密码: admin123

# 或直接调用API
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### 2. 上传文档测试
```bash
# 使用前端界面
访问: http://localhost:3000/documents
点击上传按钮，选择PDF文件

# 或使用API
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer {token}" \
  -F "file=@test.pdf"
```

### 3. 触发解析测试
```bash
# 使用前端
在文档列表页点击"解析"按钮

# 或使用API
curl -X POST http://localhost:8000/api/v1/documents/{id}/parse \
  -H "Authorization: Bearer {token}"
```

## ✅ 连接验证清单

- ✅ Vite代理配置正确
- ✅ Axios拦截器配置完整
- ✅ Token管理机制完善
- ✅ 所有API模块实现
- ✅ 状态管理配置正确
- ✅ React Query集成
- ✅ WebSocket配置
- ✅ CORS配置正确
- ✅ 错误处理完善

---

**状态**: ✅ **前后端接口完全配置并连接**

可以立即启动前后端进行测试！