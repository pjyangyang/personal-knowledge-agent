# Personal Knowledge Agent

基于 RAG（检索增强生成）的个人知识库系统。用户可以上传文档或导入网页，然后使用自然语言检索、提问和总结；系统会在回答中返回文件名、页码、网页地址和原文证据。

> 当前版本是可运行的单用户 MVP，适合个人学习、科研资料管理和项目演示。

## 主要功能

- 创建、修改、切换和删除知识库
- 上传 PDF、DOCX、Markdown 和 TXT 文档
- 导入公开网页并清理导航栏、脚本等无关内容
- 自动识别扫描版 PDF，支持中文和英文 OCR
- 使用 SHA-256 检测知识库内的重复文件
- 使用中文 Embedding 和 Qdrant 进行语义向量检索
- 使用 Ollama 或其他 OpenAI 兼容接口生成回答
- 流式显示大模型回答
- 返回文件名、PDF 页码、网页 URL 和原文片段
- 生成单文档或知识库综合总结
- 保存、查看和删除对话历史
- 可选择论文分析、文献综述、合同审查、会议纪要、学习辅导等内置 Skill
- 删除文档并清理对应索引
- 重建知识库向量索引

## 工作流程

```text
上传文档 / 导入网页
        ↓
文本解析 / PDF OCR
        ↓
文本切分与元数据保存
        ↓
FastEmbed 中文向量化
        ↓
Qdrant 本地向量索引
        ↓
问题检索与证据过滤
        ↓
Ollama / OpenAI 兼容模型
        ↓
流式答案与来源引用
```

## 技术栈

| 模块 | 技术 |
|---|---|
| 前端 | React、Vite |
| 后端 | Python 3.11、FastAPI |
| 元数据 | SQLite、SQLAlchemy |
| PDF 解析 | PyMuPDF |
| Word 解析 | python-docx |
| 网页解析 | HTTPX、BeautifulSoup |
| OCR | Tesseract（`chi_sim` + `eng`） |
| Embedding | FastEmbed、`BAAI/bge-small-zh-v1.5` |
| 向量数据库 | Qdrant Local Mode |
| 大语言模型 | Ollama 或 OpenAI 兼容 API |

## 环境要求

- Windows 10/11、Linux 或 macOS
- Conda
- Node.js 18 或更高版本
- 推荐至少 16 GB 内存
- Ollama，可选；用于本地生成自然语言答案
- 独立显卡不是必需条件，小型模型可以使用 CPU 运行

## 快速开始

### 1. 克隆项目

```powershell
git clone https://github.com/pjyangyang/personal-knowledge-agent.git
cd personal-knowledge-agent
```

### 2. 创建 Conda 环境

推荐使用仓库提供的环境文件。该方式会安装 Python、Tesseract 和后端依赖：

```powershell
conda env create -f environment.yml
conda activate personal-kb-agent
```

如果已经创建了 `personal-kb-agent` 环境，可以只安装或更新 Python 依赖：

```powershell
conda activate personal-kb-agent
python -m pip install -r backend\requirements.txt
```

### 3. 配置大语言模型

在项目根目录创建 `.env` 文件。

使用本地 Ollama：

```env
LLM_API_KEY=ollama
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=gemma3:4b
```

查看本地已有模型：

```powershell
ollama list
```

如果 Ollama 没有运行：

```powershell
ollama serve
```

也可以配置其他 OpenAI 兼容服务：

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-compatible-endpoint/v1
LLM_MODEL=your-model-name
```

未配置大语言模型时，文档解析和检索仍然可用，但系统只返回相关证据，不生成整理后的自然语言回答。

### 4. 启动后端

在项目根目录执行：

```powershell
conda activate personal-kb-agent
python -m uvicorn app.main:app --app-dir backend --reload
```

后端地址：

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

### 5. 启动前端

另开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

打开：http://127.0.0.1:5173

前端开发服务器会自动把 `/api` 请求代理到 FastAPI。

## 使用方法

1. 点击知识库区域的 `＋` 创建知识库。
2. 点击“上传资料”，选择 PDF、DOCX、Markdown 或 TXT 文件。
3. 也可以点击“导入网页”，输入公开网页地址。
4. 等待文档状态变为“已建立索引”。
5. 在问答框中输入问题。
6. 查看流式答案以及下方的文件名、页码和原文证据。
7. 点击“生成总结”可生成当前知识库的综合总结。

首次上传文档时，系统会下载约 90 MB 的中文 Embedding 模型，并缓存到 `data/models/`。

## 生产构建前端

```powershell
cd frontend
npm run build
```

构建完成后重新启动 FastAPI，然后访问：

http://127.0.0.1:8000/app

## 常用 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/knowledge-bases` | 获取知识库列表 |
| `POST` | `/api/knowledge-bases` | 创建知识库 |
| `PATCH` | `/api/knowledge-bases/{id}` | 修改知识库 |
| `DELETE` | `/api/knowledge-bases/{id}` | 删除知识库 |
| `POST` | `/api/knowledge-bases/{id}/documents` | 上传文档 |
| `GET` | `/api/knowledge-bases/{id}/documents` | 查看文档列表 |
| `DELETE` | `/api/documents/{id}` | 删除文档 |
| `POST` | `/api/knowledge-bases/{id}/webpages` | 导入网页 |
| `POST` | `/api/knowledge-bases/{id}/query` | 普通问答 |
| `POST` | `/api/knowledge-bases/{id}/query/stream` | NDJSON 流式问答 |
| `POST` | `/api/knowledge-bases/{id}/summarize` | 生成带引用的总结 |
| `GET` | `/api/knowledge-bases/{id}/conversations` | 获取对话列表 |
| `GET` | `/api/conversations/{id}` | 查看对话及引用 |
| `DELETE` | `/api/conversations/{id}` | 删除对话 |
| `POST` | `/api/knowledge-bases/{id}/reindex` | 重建向量索引 |
| `GET` | `/api/skills` | 获取可用 Skill 列表 |

## 项目结构

```text
personal-knowledge-agent/
├── backend/
│   ├── app/
│   │   ├── api.py                 # API 路由
│   │   ├── config.py              # 环境配置
│   │   ├── db.py                  # 数据库连接
│   │   ├── main.py                # FastAPI 入口
│   │   ├── models.py              # SQLAlchemy 数据模型
│   │   ├── schemas.py             # API 数据结构
│   │   └── services/
│   │       ├── document_parser.py # 多格式文档解析
│   │       ├── generation.py      # 大模型生成与流式输出
│   │       ├── pdf_parser.py      # PDF 解析与 OCR
│   │       ├── retrieval.py       # 检索逻辑
│   │       ├── vector_store.py    # Embedding 与 Qdrant
│   │       └── web_import.py      # 网页抓取与正文清理
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   └── styles.css
│   └── package.json
├── tests/
│   └── test_api.py
├── environment.yml
├── pytest.ini
└── README.md
```

## 数据与隐私

- 原始文件、SQLite 数据库、向量索引和模型缓存默认保存在本地 `data/`。
- `.env` 和 `data/` 已加入 `.gitignore`，不会被 Git 提交。
- 使用本地 Ollama 时，问答内容不会发送到外部模型服务。
- 如果配置第三方模型 API，请自行确认服务商的数据保留和隐私政策。

## 运行测试

```powershell
conda activate personal-kb-agent
python -m pytest -q
```

## 当前限制

- 当前是单用户模式，没有登录、角色和企业权限体系。
- 文档处理仍在请求过程中执行，大文件尚未进入后台任务队列。
- DOCX、Markdown 和 TXT 没有稳定的物理页码，目前使用逻辑页码进行引用。
- 网页导入不支持登录页面、付费墙和完全依赖 JavaScript 渲染的网页。
- OCR 效果取决于扫描清晰度、版面、倾斜角度和字体。
- 引用已经与检索片段绑定，但尚未实现独立的自动引用一致性评分。

## 后续计划

- 后台异步任务和处理进度
- 多用户登录与知识库权限
- 引用一致性评估
- 检索质量评测数据集
- Docker 和生产环境部署
- 更完善的错误监控与安全策略
