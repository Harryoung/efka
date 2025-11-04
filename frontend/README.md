# 智能资料库管理员 - 前端

基于 React 18 + Vite 构建的智能资料库管理员前端应用。

## 技术栈

- **React 18** - UI 框架
- **Vite** - 构建工具
- **Axios** - HTTP 客户端
- **Marked** - Markdown 渲染
- **Server-Sent Events (SSE)** - 实时流式响应

## 功能特性

- 💬 **智能对话** - 与 AI 助手进行多轮对话
- 📁 **文件上传** - 支持拖拽上传多种格式文件
- 🔄 **流式响应** - 实时显示 AI 思考过程
- 📝 **Markdown 渲染** - 美观展示 AI 回复
- 📌 **FAQ 管理** - 一键添加满意的回答到 FAQ
- 🎨 **响应式设计** - 适配桌面和移动设备

## 项目结构

```
frontend/
├── src/
│   ├── components/          # React 组件
│   │   ├── ChatView.jsx    # 主聊天界面
│   │   ├── ChatView.css
│   │   ├── Message.jsx     # 单条消息组件
│   │   ├── Message.css
│   │   ├── FileUpload.jsx  # 文件上传组件
│   │   └── FileUpload.css
│   ├── services/            # API 服务
│   │   └── api.js          # API 客户端封装
│   ├── App.jsx             # 根组件
│   ├── App.css             # 全局样式
│   └── main.jsx            # 应用入口
├── public/                  # 静态资源
├── index.html              # HTML 模板
├── vite.config.js          # Vite 配置
└── package.json            # 项目配置
```

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

应用将在 http://localhost:3000 启动。

### 3. 构建生产版本

```bash
npm run build
```

构建产物位于 `dist/` 目录。

### 4. 预览生产构建

```bash
npm run preview
```

## 环境变量

创建 `.env` 文件（可参考 `.env.example`）：

```bash
# API 基础 URL（可选，默认使用 /api）
VITE_API_BASE_URL=/api
```

## API 集成

前端通过 Vite 代理与后端通信：

- **开发环境**：`/api/*` 请求代理到 `http://localhost:8000`
- **生产环境**：需要配置 Nginx 或其他反向代理

### API 端点

- `POST /api/session/create` - 创建会话
- `DELETE /api/session/{id}` - 删除会话
- `POST /api/query` - 发送查询（非流式）
- `GET /api/query/stream` - SSE 流式查询
- `POST /api/upload` - 上传文件

## 组件说明

### ChatView 主界面

核心组件，集成所有功能：

- 会话管理
- 消息列表展示
- 输入框和发送功能
- 文件上传集成
- SSE 流式响应处理

### Message 消息组件

单条消息显示：

- 支持用户/助手/系统消息
- Markdown 渲染
- 代码高亮
- 添加到 FAQ 按钮

### FileUpload 文件上传

文件上传功能：

- 拖拽上传
- 多文件支持
- 上传进度显示
- 文件列表管理

## 开发指南

### 添加新组件

1. 在 `src/components/` 创建组件文件
2. 创建对应的 CSS 文件
3. 在需要的地方导入使用

### 调用 API

使用封装好的 `apiService`：

```javascript
import apiService from '../services/api';

// 创建会话
const { session_id } = await apiService.createSession();

// 发送查询
await apiService.query(sessionId, message);

// 流式查询
apiService.queryStream(
  sessionId,
  message,
  (data) => console.log('Message:', data),
  (error) => console.error('Error:', error),
  () => console.log('Complete')
);
```

### 样式规范

- 使用 CSS 变量定义主题色
- 遵循 BEM 命名规范
- 响应式设计优先
- 支持深色模式（可选）

## 性能优化

- ✅ 代码分割（Vite 自动）
- ✅ 懒加载组件
- ✅ Markdown 渲染缓存
- ✅ 防抖/节流处理
- ✅ 生产环境压缩

## 浏览器兼容性

- Chrome/Edge >= 88
- Firefox >= 78
- Safari >= 14
- 不支持 IE

## 故障排查

### 端口冲突

如果 3000 端口被占用，修改 `vite.config.js`：

```javascript
export default defineConfig({
  server: {
    port: 3001, // 修改端口
  }
});
```

### API 连接失败

1. 确保后端服务运行在 http://localhost:8000
2. 检查 Vite 代理配置
3. 查看浏览器控制台网络请求

### 构建失败

```bash
# 清除缓存
rm -rf node_modules dist
npm install
npm run build
```

## 待改进功能

- [ ] 会话历史持久化
- [ ] 消息搜索功能
- [ ] 导出对话记录
- [ ] 深色模式支持
- [ ] 多语言支持
- [ ] 离线支持（PWA）

## 相关文档

- [技术方案](../智能资料库管理员-技术方案-Agent自主版.md)
- [Phase 3 验收报告](../docs/Phase3-验收报告.md)
- [后端 API 文档](../backend/README.md)

## License

MIT
