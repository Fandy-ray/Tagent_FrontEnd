# TAgentNote · 系统建模与仿真智能教学平台

面向《系统建模与仿真》课程的智能教学前端，支持 RAG 增强答疑、知识笔记本与智能测评。面向「AI for 高校教学智能体创新大赛 · 未来课堂」方向。

## 功能概览

| 模块 | 路由 | 说明 |
|------|------|------|
| 欢迎页 | `/welcome` | 平台入口与品牌展示 |
| 智能体选择 | `/agent-select` | 选择模型与智能体类型 |
| 答疑智能体 | `/qa` | 基于课程知识库的检索增强问答（当前为 Mock RAG） |
| 笔记本 | `/notebook` | 嵌入 OpenNoteBook 知识工作空间 |
| 测评智能体 | `/exam-copy` | 生成知识测验并对作答评分 |

## 技术栈

- [SvelteKit](https://svelte.dev/docs/kit) + Svelte 5
- TypeScript
- Vite 8
- Tailwind CSS 4

## 快速开始

### 环境要求

- Node.js 18+（建议使用当前 LTS）

### 安装与运行

```bash
cd tagentnote
npm install
npm run dev
```

浏览器打开终端提示的本地地址（默认一般为 `http://localhost:5173`）。根路径 `/` 会自动跳转到 `/welcome`。

### 常用脚本

| 命令 | 说明 |
|------|------|
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 生产构建 |
| `npm run preview` | 预览生产构建 |
| `npm run check` | 类型与 Svelte 检查 |
| `npm run lint` | ESLint + Prettier 检查 |
| `npm run format` | Prettier 格式化 |

## 环境变量

在项目根目录创建或编辑 `.env`：

```env
# OpenNoteBook 嵌入地址（笔记本页 iframe）
PUBLIC_OPENNOTEBOOK_URL=http://localhost:8502
```

未配置时，笔记本页默认使用 `http://localhost:8502/notebooks`。

OpenNoteBook本地配置教程详见：https://gitee.com/kevin-zhengscuter/fixed_open_notebook。

## 项目结构

```
src/
├── lib/
│   ├── apis/agent.ts          # 模型列表与 Mock RAG 接口
│   └── components/
│       ├── chat/              # 答疑页聊天 UI
│       └── quiz/              # 测评面板
└── routes/
    ├── welcome/               # 欢迎页
    ├── agent-select/          # 智能体选择
    ├── qa/                    # 答疑
    ├── notebook/              # OpenNoteBook 嵌入
    └── exam-copy/             # 测评
```

## 说明

- 答疑与测评当前使用前端 Mock 数据与接口（见 `src/lib/apis/agent.ts`），便于演示与联调；可后续替换为真实 Agent / RAG 后端。
- 笔记本依赖外部 OpenNoteBook 服务；需先在本地或目标环境启动对应服务，并配置 `PUBLIC_OPENNOTEBOOK_URL`。

## License

Private（见 `package.json`）。
