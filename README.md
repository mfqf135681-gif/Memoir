# Memoir

> AI 长期记忆框架 - 文件即记忆，透明可追溯，联想式检索

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.109+-0097F5?style=flat-square" alt="FastAPI">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

## 项目概述

**Memoir** 是一个轻量级的 AI 长期记忆框架，让 AI 助手具备"记忆"能力。

核心理念：
- **文件即记忆**：每条记忆存储为独立的 Markdown 文件，可直接编辑
- **透明**：所有操作记录在案，可追溯 AI 的检索过程
- **联想检索**：多维度扩展检索，模拟人类记忆联想

---

## 功能特性

### 核心能力

| 功能 | 描述 |
|------|------|
| 📝 **文件即记忆** | 记忆存储为 Markdown 文件，带 YAML frontmatter 元数据 |
| 🔍 **透明可追溯** | 操作日志记录每次记忆访问，AI 回复可查看引用来源 |
| 🧠 **联想检索** | 会话扩展 + 时间邻近 + 相似记忆，三种检索策略 |
| 🔎 **混合搜索** | 向量搜索 (ChromaDB) + 全文搜索 (SQLite FTS5) |

### 扩展功能

| 功能 | 描述 |
|------|------|
| 👥 **多用户支持** | 通过 `X-User-ID` 隔离不同用户的记忆 |
| 📎 **文件上传** | 支持 TXT、PDF、DOCX、图片 (OCR)，自动提取文本 |
| 🎛️ **多模型支持** | Ollama / OpenAI / DeepSeek / 硅基流动等 |
| 🎨 **Web UI** | 现代化毛玻璃风格界面，支持拖拽上传 |

---

## 快速开始

### 环境要求

- Python 3.11+
- Ollama (本地模型) 或 DeepSeek/OpenAI API Key

### 方式一：交互式安装脚本（推荐 for Linux）

```bash
# 克隆项目
git clone https://github.com/your-repo/memoir.git
cd memoir

# 运行安装脚本（仅支持 Linux）
./install.sh
```

安装脚本会自动完成以下工作：
- 环境检查（Python 3.9+、pip、venv）
- LLM 提供商配置（Ollama 或 OpenAI 兼容服务）
- 安全设置（API Key 自动生成、端口自动检测）
- 数据目录创建（`~/.memory-chat`）
- 可选定时备份配置
- 依赖安装与服务启动

### 方式二：手动安装

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/memoir.git
cd memoir

# 2. 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或: venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -e .
```

### 配置 LLM

编辑 `config.yaml`：

```yaml
llm:
  provider: "openai"  # 或 "ollama"

  # DeepSeek 示例
  openai:
    api_key: "sk-xxxxxxxx"
    model: "deepseek-chat"
    base_url: "https://api.deepseek.com/v1"

  # 或 Ollama 本地模型
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen2.5:7b"
```

### 启动服务

```bash
# 方式一：使用管理脚本（推荐，安装脚本自动生成）
./memoir.sh start

# 方式二：直接运行
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 方式三：Python 模块
python -m src.main
```

**管理脚本命令：**

| 命令 | 说明 |
|------|------|
| `./memoir.sh start` | 启动服务 |
| `./memoir.sh stop` | 停止服务 |
| `./memoir.sh restart` | 重启服务 |
| `./memoir.sh status` | 查看状态 |
| `./memoir.sh log` | 查看日志 |

### 访问前端

浏览器打开 **http://localhost:8000**

---

## 配置说明

主要配置项在 `config.yaml` 中：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `server.host` | 服务监听地址 | `0.0.0.0` |
| `server.port` | 服务端口 | `8000` |
| `auth.enabled` | 是否启用 API 认证 | `true` |
| `auth.api_key` | API 认证密钥 | (自动生成) |
| `storage.base_dir` | 数据存储目录 | `./data` |
| `memory.short_term_max_messages` | 短期记忆保留条数 | `1000` |
| `retrieval.top_k` | 检索返回条数 | `5` |
| `retrieval.similarity_threshold` | 相似度阈值 | `0.7` |
| `retrieval.expand_session_turns` | 会话扩展轮数 | `3` |
| `retrieval.expand_time_days` | 时间邻近天数 | `7` |
| `backup.enabled` | 是否启用自动备份 | `false` |
| `backup.cron` | 备份定时任务 | `0 2 * * 0` |
| `backup.keep` | 保留备份份数 | `3` |
| `backup.path` | 备份存储路径 | `~/.memory-chat/backups` |

### 支持的 LLM 提供商

| 提供商 | Base URL | 示例模型 |
|--------|----------|----------|
| DeepSeek | `https://api.deepseek.com/v1` | deepseek-chat |
| 硅基流动 | `https://api.siliconflow.cn/v1` | Qwen/Qwen2.5-7B-Instruct |
| OpenAI | `https://api.openai.com/v1` | gpt-4o |
| 月之暗面 | `https://api.moonshot.cn/v1` | moonshot-v1-8k |
| 阿里通义 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-turbo |
| Ollama | `http://localhost:11434` | llama2, qwen2.5:7b |

---

## API 文档

### 1. 聊天接口

```bash
POST /v1/chat
```

**请求头：**
```
X-User-ID: your-user-id
Content-Type: application/json
```

**请求体：**
```json
{
  "message": "你好，记住我喜欢科幻电影",
  "session_id": "可选会话ID",
  "use_memory": true,
  "temperature": 0.7,
  "enhanced_mode": false
}
```

**响应：**
```json
{
  "response": "好的，我已经记住你喜欢科幻电影了...",
  "session_id": "会话ID",
  "used_memories": [{"id": "xxx", "title": "偏好"}],
  "context_used": true
}
```

### 2. 记忆管理

```bash
# 列出所有记忆
GET /v1/memories?include_content=true

# 创建记忆
POST /v1/memories
{
  "content": "记忆内容",
  "title": "可选标题",
  "tags": ["标签1", "标签2"]
}

# 删除记忆
DELETE /v1/memories/{memory_id}

# 搜索记忆
POST /v1/memories/search
{
  "query": "关键词",
  "top_k": 5
}
```

### 3. 文件上传

```bash
POST /v1/files/upload?extract_content=true
Content-Type: multipart/form-data

# 参数
file: 二进制文件
```

**响应：**
```json
{
  "file_id": "uuid",
  "filename": "文档.pdf",
  "size": 12345,
  "extracted_content": "提取的文本内容..."
}
```

### 4. 配置管理

```bash
# 获取用户配置
GET /v1/config/user

# 保存用户配置
PUT /v1/config/user
{
  "llm": {
    "provider": "deepseek",
    "api_key": "sk-xxx",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat"
  }
}

# 测试 API 连接
POST /v1/config/user/test
{
  "provider": "deepseek",
  "api_key": "sk-xxx",
  "base_url": "https://api.deepseek.com/v1",
  "model": "deepseek-chat"
}

# 获取支持提供商列表
GET /v1/config/providers
```

### 5. 日志查看

```bash
# 操作日志
GET /v1/logs

# 短期记忆（对话历史）
GET /v1/logs/short-term?session_id=xxx
```

---

## 项目架构

```
Memoir
├── src/
│   ├── main.py              # FastAPI 应用入口
│   ├── core/               # 核心业务逻辑
│   │   ├── config.py       # 配置管理
│   │   ├── memory_store.py    # 存储层
│   │   ├── memory_index.py    # 索引层 (ChromaDB + FTS5)
│   │   ├── memory_retriever.py # 检索层
│   │   ├── dialogue_engine.py  # 对话引擎
│   │   ├── llm_client.py      # LLM 客户端
│   │   └── user_config.py     # 用户配置
│   ├── api/                # REST API
│   │   ├── dependencies.py  # 依赖注入
│   │   └── routes/         # 路由
│   │       ├── chat.py      # 聊天
│   │       ├── memories.py  # 记忆
│   │       ├── files.py     # 文件
│   │       ├── config.py    # 配置
│   │       └── logs.py      # 日志
│   └── utils/              # 工具
│       ├── logger.py        # 日志
│       └── file_extractor.py # 文件提取
├── static/
│   └── index.html          # Web UI
├── config.yaml             # 配置文件
└── pyproject.toml          # 项目配置
```

### 核心模块职责

| 模块 | 职责 |
|------|------|
| **memory_store** | 短期记忆 (JSONL)、长期记忆 (Markdown)、文件存储、操作日志 |
| **memory_index** | ChromaDB 向量索引 + SQLite FTS5 全文索引 |
| **memory_retriever** | 联想检索：会话扩展、时间邻近、相似记忆 |
| **dialogue_engine** | 组装提示词、调用 LLM、整合记忆 |
| **llm_client** | 统一 LLM 接口，支持 Ollama/OpenAI/Dynamic |

### 数据目录结构

使用安装脚本时，数据默认存储在 `~/.memory-chat`：

```
~/.memory-chat/
├── config.yaml           # 配置文件
├── users/{user_id}/      # 用户数据
│   ├── short_term/       # 短期记忆 (JSONL)
│   ├── long_term/        # 长期记忆 (Markdown)
│   ├── files/            # 上传文件
│   ├── meta/             # 文件元数据
│   ├── logs/             # 操作日志
│   └── index/            # 索引数据
│       ├── chroma/       # ChromaDB
│       └── search.db     # SQLite FTS5
├── backups/              # 备份文件 (启用自动备份时)
└── meta/                 # 安装日志、进程ID等
    ├── install.log       # 安装时间记录
    ├── memoir.pid        # 服务进程ID
    └── memoir.log        # 服务运行日志
```

> 手动安装时，数据目录默认为 `./data`

---

## 开发指南

### 开发环境搭建

```bash
# 1. 安装开发依赖
pip install -e ".[dev]"

# 2. 安装预提交钩子 (可选)
pre-commit install

# 3. 运行测试
pytest

# 4. 代码格式化
ruff format .
```

### 代码结构说明

- `src/core/` - 核心业务逻辑，无外部依赖
- `src/api/` - FastAPI 路由和依赖注入
- `src/utils/` - 通用工具函数
- `static/` - 前端静态资源

### 运行测试

```bash
# 运行所有测试
pytest

# 运行指定测试
pytest tests/test_api.py

# 带覆盖率
pytest --cov=src
```

---

## 设计亮点

### 1. 透明可追溯

- 每条记忆独立文件存储，可直接查看和编辑
- 操作日志记录 AI 的每次检索过程
- 回复消息中显示引用了哪些记忆

### 2. 联想式检索

```
用户query
    ↓
┌─────────────────────────────────────────┐
│           检索策略                       │
├─────────────────────────────────────────┤
│ 1. 会话扩展: 同会话的历史消息            │
│ 2. 时间邻近: 同一时间段的其他记忆       │
│ 3. 相似记忆: 向量检索的相似内容         │
└─────────────────────────────────────────┘
    ↓
混合结果排序 → 返回 Top-K
```

### 3. 轻量设计

- 无需数据库服务器 (SQLite + 文件系统)
- 可选向量数据库 (ChromaDB 嵌入式)
- 支持纯 FTS 全文搜索 (无需向量模型)

---

## 许可证

MIT License - 请查看 `LICENSE` 文件

---

## 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Web 框架
- [ChromaDB](https://www.trychroma.com/) - 轻量向量数据库
- [Vue 3](https://vuejs.org/) - 前端框架
- [Tailwind CSS](https://tailwindcss.com/) - CSS 框架
