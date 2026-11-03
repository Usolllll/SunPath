# SunPath · 阳光志愿

一个可运行的前后端分离高考志愿规划 MVP。采用 Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + Axios + ECharts，后端采用 FastAPI + SQLAlchemy + Pydantic + JWT，支持 MySQL 8，并提供便于本地体验的 SQLite 配置。

**所有院校的录取、选科、学费及招生计划都是人工生成的模拟样本，不是官方数据。冲稳保是规则估算，不代表录取概率或录取承诺。正式填报须核实省考试院及高校当年的信息。**

新增 **AI 问答** 页面（`/ai-chat`，登录后从左侧导航进入）。当前仅为界面预览，提供推荐问题、输入区与考生画像参考；推荐问题可填入输入框，发送按钮暂不可用，不调用模型或后端问答接口，也不保存输入内容。

## 环境要求

- Node.js 22 LTS（或支持 Vite 6 的 Node.js 20.19+），npm 10+
- Python 3.11+
- MySQL 8.0+ / 8.4（正式技术栈）；SQLite 仅用于无 MySQL 的本地演示
- 桌面 Chrome / Edge / Firefox，兼容常见移动端宽度

## 一键启动（已安装依赖后）

在项目根目录直接双击 **`start.bat`**，即可同时启动现有后端与前端，并自动打开 <http://127.0.0.1:5173>。启动窗口保留两边的运行日志；按回车、Ctrl+C，或在 Windows 上关闭该窗口，会停止本次启动的前后端及其子进程。

也可以在项目根目录的 PowerShell 中执行（脚本内部使用自身路径定位项目，不依赖调用时的工作目录）：

```powershell
.\start.bat
# 不自动打开浏览器
.\start.bat --no-browser
```

脚本只启动 Uvicorn 和 Vite 开发服务，**不会安装依赖、执行 build、重新建表、导入数据或改写 `.env`**。如依赖、配置缺失或 8000 / 5173 端口已被占用，会提示原因并退出，不会结束其他已有服务。数据库沿用 `backend/.env` 的配置；若使用 MySQL，须先确保数据库服务已运行。

## 首次安装：本地演示

以下命令仅用于首次配置，在 Windows PowerShell 中执行。已经配置好的项目直接使用上方 `start.bat`，无需重复安装或初始化。

### 1. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 仅在 .env 不存在时生成本地 SQLite 配置和随机 JWT 密钥
.\.venv\Scripts\python.exe scripts/setup_env.py
# 建表 + 初始化样本，重复执行不会覆盖用户或方案
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. 新终端启动前端

```powershell
cd frontend
npm install
npm run dev
```

- 前端：<http://127.0.0.1:5173>
- 后端：<http://127.0.0.1:8000>
- OpenAPI / Swagger：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

macOS / Linux 使用 `python3 -m venv .venv`、`.venv/bin/python` 代替以上 Python 路径，其余命令相同。

### 演示账号

| 邮箱 | 密码 |
| --- | --- |
| `demo@sunpath.cn` | `Sunpath2026!` |

登录页提供“体验演示账号”按钮。演示账号由显式初始化命令创建，不会在服务启动时自动创建。默认画像为浙江 / 2026 / 628 分 / 22,580 位 / 物理、化学、生物；可自行修改。新注册账号没有画像，需先填写。

## 使用 MySQL

1. 准备 MySQL 8，创建数据库及专用用户，例如在管理员 MySQL 会话中执行（替换密码）：

```sql
CREATE DATABASE sunpath CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sunpath'@'localhost' IDENTIFIED BY 'YOUR_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON sunpath.* TO 'sunpath'@'localhost';
```

2. 将 `backend/.env.example` 复制为 `backend/.env`，填写：

```dotenv
DATABASE_URL=mysql+pymysql://sunpath:YOUR_URL_ENCODED_PASSWORD@127.0.0.1:3306/sunpath?charset=utf8mb4
JWT_SECRET=YOUR_RANDOM_SECRET_AT_LEAST_32_CHARACTERS
JWT_EXPIRE_MINUTES=1440
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
DEMO_EMAIL=demo@sunpath.cn
DEMO_PASSWORD=Sunpath2026!
```

用 `python -c "import secrets; print(secrets.token_urlsafe(48))"` 生成 JWT 密钥。密码中的 `@`、`#` 等字符必须进行 URL 编码。`.env` 不进入 Git，配置通过 Pydantic Settings 从文件读取，环境变量可覆盖。示例占位密钥会被拒绝。

3. 执行 `python -m app.seed` 建立全部表并初始化数据，再启动服务。表结构由 `backend/app/models/entities.py` 定义；建表命令使用 SQLAlchemy `create_all`，只创建不存在的表，不负责已有表的结构迁移。

也可使用根目录 `docker-compose.yml` 启动 MySQL：

```powershell
$env:MYSQL_PASSWORD = 'YOUR_STRONG_PASSWORD'
$env:MYSQL_ROOT_PASSWORD = 'YOUR_ROOT_PASSWORD'
docker compose up -d
```

然后在 `backend/.env` 填入相同的专用用户密码。Docker 不是运行前后端的必需依赖。

## 完整演示流程

1. 注册或登录，进入考生画像，填写总分、位次、省份、年份、三门选科和兴趣偏好并保存。
2. 在招生数据中心浏览高校、专业、历年录取和招生计划；支持关键词、院校地区、层次、选科要求、生源省份和计划年份筛选。
3. 在智能院校匹配查看冲稳保候选，打开院校详情查看选科条件、趋势、推荐理由和风险提示。
4. 点击“一键生成志愿方案”，或逐个加入候选。生成器优先按 1:2:1 分配冲稳保，默认 12 个专业组；样本不足时补齐并提示缺失梯度。
5. 在规划中心用上下箭头调整顺序、删除或添加志愿，填写方案名称并保存。每份方案最多 30 个专业组。
6. 在我的志愿方案中查看完整历史快照、重新编辑、选择两份进行对比、删除或导出 UTF-8 BOM CSV（可用 Excel 打开）。
7. 在个人中心修改称呼或密码、退出登录。改密码和退出会使该账号既有 JWT 失效。

## 数据与算法边界

- 24 所高校、48 个专业组、864 条 2023–2025 年录取记录、288 条 2026 年计划，覆盖浙江、江苏、山东、广东、河南、四川六省模拟生源。
- 仅在同一生源省份比较位次；先过滤选科不符合、缺少录取记录或当年没有计划的专业组。
- 使用考生考试年份之前三年的记录，按由旧到新的 `1, 2, 3` 权重计算参考位次（缺少年度时使用可用记录的递增权重）。
- `位次比 = 考生位次 / 加权参考位次`：`≤ 0.80` 为保底，`≤ 1.08` 为稳妥，`≤ 1.35` 为冲刺，超过 1.35 不推荐。
- 地区和专业偏好只影响排序；先按偏好命中数排序，再优先接近参考位次的候选。没有任何“真实录取概率”或百分比成功率。
- 显示历年位次波动和风险说明；目前不建模批次、投档规则、专业调剂、体检限制或专项招生。分数只用于显示，不能由模拟分数反推出官方位次。
- 默认示例有三个梯度，但不同画像可能只匹配部分梯度或没有候选；不会为填满方案伪造候选。
- 2027 年暂无模拟招生计划，会返回空推荐；界面明确提示。
- `backend/app/services/recommender.py` 是后续接入模型的业务边界，接口已与页面分离；当前不调用任何大模型 API。
- 草稿按账号保存在当前浏览器；正式保存的方案和画像保存在数据库。历史方案保存完整画像和分析快照；修改画像后旧快照不会变化，旧草稿须重新匹配。

## 项目结构

```text
SunPath/
├── frontend/
│   ├── src/
│   │   ├── api/          # Axios 入口、类型与 API 函数
│   │   ├── assets/       # 统一设计样式与响应式布局
│   │   ├── components/   # 院校卡片、分析详情、ECharts 趋势等
│   │   ├── layouts/      # 侧栏与顶栏
│   │   ├── views/        # 登录、概览、画像、数据、分析、规划、历史、账号
│   │   ├── router/       # 路由及鉴权守卫
│   │   ├── stores/       # 用户状态与账号隔离草稿
│   │   └── utils/        # 格式化与下载
│   └── .env.example
├── backend/
│   ├── app/
│   │   ├── api/          # 身份、招生分析、方案 REST API
│   │   ├── core/         # 配置、数据库、密码和 JWT
│   │   ├── models/       # SQLAlchemy 模型
│   │   ├── schemas/      # Pydantic 输入输出约束
│   │   ├── services/     # 数据序列化、可解释推荐与梯度生成
│   │   ├── utils/        # CSV 输出与公式注入防护
│   │   ├── main.py       # FastAPI 入口与 CORS
│   │   └── seed.py       # 幂等建表与模拟数据
│   ├── scripts/setup_env.py
│   ├── tests/test_workflow.py
│   ├── .env.example
│   └── requirements.txt
├── docker-compose.yml
└── .gitignore
```

## API 概览

除注册、登录和健康检查外，全部业务 API 需要 `Authorization: Bearer <token>`。

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| POST | `/api/auth/register`、`/api/auth/login` | 注册 / 登录，返回 JWT 和用户资料 |
| GET / PATCH | `/api/auth/me` | 获取 / 修改个人资料 |
| PUT | `/api/auth/profile`、`/api/auth/password` | 保存画像 / 修改密码 |
| POST | `/api/auth/logout` | 撤销账号当前 JWT 版本 |
| GET | `/api/meta`、`/api/overview` | 样本说明 / 工作台统计 |
| GET | `/api/catalog`、`/api/catalog/{group_id}` | 分页筛选 / 院校专业组详情 |
| GET | `/api/recommendations` | 当前画像规则推荐 |
| POST | `/api/recommendations/generate?count=12` | 生成梯度方案 |
| GET / POST | `/api/plans` | 列表 / 新建方案 |
| GET / PUT / DELETE | `/api/plans/{id}` | 查看 / 更新 / 删除本人方案 |
| GET | `/api/plans/{id}/export` | 导出本人方案 CSV |

## 验证与构建

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

cd ../frontend
npm run build
# 预览生产构建；后端需运行，预览自动将 /api 代理到本机 8000
npm run preview
```

接口测试使用临时 SQLite 文件，覆盖认证与输入校验、同省与选科匹配、梯度计算、生成/重排/保存/快照/导出/删除、账号数据隔离、Token 撤销、过滤分页、无计划年份和初始化幂等性，不接触开发数据库。另已在本机 MySQL 8.0.38 实例验证建表初始化、注册登录、画像 JSON 存储、院校查询与匹配、方案保存修改及快照、CSV 导出、删除与 Token 撤销，并验证初始化可重复执行。本机开发 `.env` 已切换到 MySQL；SQLite 文件仍保留，已有账号和方案不自动迁移。

开发模式 Vite 自动将 `/api` 代理到 `http://127.0.0.1:8000`。独立域名部署时复制 `frontend/.env.example` 为 `.env`，将 `VITE_API_BASE_URL` 设为后端 `/api` 绝对地址，并将前端来源加入后端 `CORS_ORIGINS`，然后重新构建。部署静态文件时需为 Vue history 路由配置回退到 `index.html`。

## 常见问题

- **后端提示配置缺失**：执行 `scripts/setup_env.py`，或从 `.env.example` 配置数据库地址和随机密钥。
- **没有表或没有院校数据**：在 backend 目录执行 `python -m app.seed`；服务启动不自动写入数据。
- **前端提示连接失败**：检查后端 8000 端口与前端 API 地址；不要直接用文件协议打开 HTML。
- **5173 端口被占用**：停止已有开发服务，或修改 Vite 端口并同步 CORS；配置使用严格端口以免静默变更。
- **修改画像后无法保存草稿**：重新智能匹配并生成方案，确保每个专业组符合最新选科与位次要求。
- **生产预览**：`vite preview` 同样代理 `/api` 到本机 8000；生产发布仍须自行配置反向代理或显式 API 地址。

这是本地可运行 MVP，尚未接入真实数据或线上运维。上线前需补充官方数据授权与更新、各省规则、登录限流、HTTPS、备份、密钥管理及正式数据库迁移。
