# Personal Knowledge Agent

个人知识库 Agent 的第一阶段后端 MVP：支持知识库管理、PDF 上传、按页解析、文本切分、SQLite 元数据保存、中文向量检索、证据引用和对话历史。

## 当前状态

- 已实现：知识库 CRUD、PDF 上传、重复文件检测、按页解析、文本切分、文档删除、FastEmbed 中文向量检索、Qdrant Local Mode、证据引用、对话历史
- 可选配置：OpenAI 兼容的大语言模型 API；未配置时返回检索证据，不会编造答案
- 预留：网页导入、OCR、DOCX/Markdown/TXT、多用户权限、React 前端和复杂 Agent 任务

## 启动

```powershell
conda activate personal-kb-agent
cd D:\code\codex\project
python -m pip install -r backend\requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

打开 http://127.0.0.1:8000/docs 查看 API 文档。

前端开发模式（需要 Node.js）：

```powershell
cd frontend
npm install
npm run dev
```

然后打开 http://127.0.0.1:5173。前端会自动将 `/api` 请求代理到 FastAPI。

构建前端后，也可以通过后端访问：

```powershell
cd frontend
npm run build
```

然后访问 http://127.0.0.1:8000/app。

首次上传或重建索引时会下载并缓存 `BAAI/bge-small-zh-v1.5` Embedding 模型，默认缓存目录是 `data/models`。

如需接入大语言模型，在项目根目录创建 `.env`：

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-compatible-endpoint/v1
LLM_MODEL=your-model-name
```

常用接口：

- `POST /api/knowledge-bases`：创建知识库
- `POST /api/knowledge-bases/{id}/documents`：上传 PDF
- `POST /api/knowledge-bases/{id}/webpages`：导入网页正文
- `POST /api/knowledge-bases/{id}/query`：检索并回答问题
- `POST /api/knowledge-bases/{id}/summarize`：生成带引用的总结
- `GET /api/knowledge-bases/{id}/conversations`：查看对话列表
- `GET /api/conversations/{id}`：查看带引用的对话详情
- `POST /api/knowledge-bases/{id}/reindex`：重建知识库向量索引

## 运行测试

```powershell
conda activate personal-kb-agent
python -m pytest -q
```

数据默认保存在 `data/`，可通过 `DATABASE_URL` 和 `STORAGE_DIR` 环境变量覆盖。
