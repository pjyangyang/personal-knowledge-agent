# Personal Knowledge Agent

个人知识库 Agent 的第一阶段后端 MVP：支持知识库管理、PDF 上传、按页解析、文本切分、SQLite 元数据保存和基础检索。

## 当前状态

- 已实现：知识库 CRUD、PDF 上传、重复文件检测、按页解析、文本切分、文档删除、关键词检索
- 预留：Embedding/向量数据库、LLM 问答、引用一致性检查、网页导入、OCR、React 前端

## 启动

```powershell
conda activate personal-kb-agent
cd D:\code\codex\project
python -m pip install -r backend\requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

打开 http://127.0.0.1:8000/docs 查看 API 文档。

## 运行测试

```powershell
conda activate personal-kb-agent
python -m pytest -q
```

数据默认保存在 `data/`，可通过 `DATABASE_URL` 和 `STORAGE_DIR` 环境变量覆盖。
