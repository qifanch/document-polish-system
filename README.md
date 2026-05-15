# 文档润色系统

一个基于大语言模型的文档润色系统，支持单篇文本润色、批量文档处理、润色评分、历史记录管理和统计分析。

## 技术栈

- 前端：Vue 3、Vue Router、Vite
- 后端：FastAPI、Uvicorn
- 数据库：MySQL
- 文档处理：python-docx、PyMuPDF、Pillow
- 模型服务：DeepSeek API

## 目录结构

```text
document-polish-system/
├─ frontend/              # 前端项目
├─ backend/               # 后端项目
│  ├─ app/                # 后端业务代码
│  ├─ storage/data/       # 必要的静态种子数据
│  ├─ .env.example        # 环境变量示例
│  └─ requirements.txt    # 后端依赖
└─ README.md              # 仓库说明
```

## 环境准备

建议准备以下环境：

- Node.js 18 或更高版本
- Python 3.12 或更高版本
- MySQL 8.x
- 可用的 DeepSeek API Key

## 后端启动

1. 进入 `backend` 目录。
2. 创建并激活 Python 虚拟环境。
3. 安装依赖：

```bash
pip install -r requirements.txt
```

4. 复制环境变量示例文件：

```bash
cp .env.example .env
```

5. 按实际环境填写 `backend/.env`：

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`

6. 启动后端服务：

```bash
uvicorn app.main:app --reload
```

默认地址：

- 后端接口：[http://127.0.0.1:8000](http://127.0.0.1:8000)
- 健康检查：[http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

## 前端启动

1. 进入 `frontend` 目录。
2. 安装依赖：

```bash
npm install
```

3. 启动开发环境：

```bash
npm run dev
```

默认地址：

- 前端页面：[http://127.0.0.1:5173](http://127.0.0.1:5173)

## 数据库与模型配置说明

- 系统默认使用 MySQL 存储用户、模板、记录、统计等结构化数据。
- `backend/storage/data/polish_templates.json` 保留为仓库内的静态种子数据，用于初始化模板。
- 润色与评分能力依赖 DeepSeek 模型接口，请确保 API Key 可用且账户具有调用权限。

## 隐私与仓库裁剪说明

为保证仓库可公开上传，本仓库已经移除或忽略以下内容：

- 本地环境文件，如 `.env`、虚拟环境、编辑器缓存
- 本地上传文件、润色结果、导出文件和运行日志
- 构建产物和依赖目录
- 论文工作区、论文脚本、测试证据图和个人文档

如果你准备继续二次开发，请自行在本地重新创建运行环境和测试数据。
