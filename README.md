# SunPath · 阳光志愿

一个可运行的前后端分离高考志愿规划 MVP。采用 Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + Axios + ECharts，后端采用 FastAPI + SQLAlchemy + Pydantic + JWT，支持 MySQL 8，并提供便于本地体验的 SQLite 配置。

**所有院校的录取、选科、学费及招生计划都是人工生成的模拟样本，不是官方数据。冲稳保是规则估算，不代表录取概率或录取承诺。正式填报须核实省考试院及高校当年的信息。**

**AI 问答** 页面位于 `/ai-chat`，登录后从左侧导航进入。后端统一接入 OpenAI 兼容模型网关，默认使用 Pollinations 免费公共通道（GPT-OSS-20B，无需 API Key；可在 `backend/.env` 切换智谱 GLM-4-Flash / DeepSeek 官方）。支持 SSE 流式问答（首字到达即显示）、多轮问答、推荐问题、新对话、停止生成和失败重试。问答 skill 默认结合本人最新考生画像和已保存方案，可关闭引用或选择指定方案；回复支持 Markdown 渲染，对话仅保留在当前页面，不写入数据库。**智能院校匹配** 支持由同一模型通过项目内 skill 从已收录的 60 所高校中选择专业组，所有结果均经后端硬约束校验。模型回答可能有误，具体招生信息须核实官方来源。

## 交付物与需求追踪

课程项目的最终过程文档位于 `docs/`：

- [需求跟踪矩阵 V2.0](docs/需求跟踪矩阵_2026-11-13_V2.0.xlsx)：M1–M11 共 54 条功能需求，按“需求 → AC → UC → 设计/代码 → 测试 → 结论”建立双向追溯；含需求追溯明细、覆盖统计与遗留缺口计划。
- [需求跟踪矩阵验收核查报告](docs/需求跟踪矩阵验收核查报告_2026-11-13.xlsx)：逐条核查说明、问题清单与运行证据。
- [交付说明](docs/交付说明.md)：范围、验证基线、演示账号与已知边界。

当前验证基线：后端 pytest **147 项**、前端 vitest **31 项**、运行时接口冒烟 **72/72**。

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

启动器按顺序寻找可用解释器：`backend/.venv` → 仓库旁的便携版 `../Python311` → `SUNPATH_PYTHON` 指定的路径；找到后会先校验 Python 版本（3.11+）和依赖是否齐全，不满足时给出明确提示而不是闪退。

后端会监听 `backend/app` 下的 Python 文件并自动重载，前端由 Vite 热更新。旧版本的启动进程须关闭后重新运行一次 `start.bat` 才能启用这一行为；修改 `.env` 仍需重启。若出现“后端尚未加载 AI 匹配接口”的提示，也请先关闭原启动窗口再重新启动。

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

## 大模型配置（免费 / 付费平台可切换）

所有大模型请求（问答、院校精选）统一经过 `backend/app/services/llm.py`，走 **OpenAI 兼容协议**；密钥只从 `backend/.env` 读取，不能放入前端、源码或 Git。后端已使用现有 `httpx` 依赖，无需安装额外 SDK。换平台 = 改 `.env` 里 3~4 行，代码不用动。

| 平台 | 是否免费 | 是否需要注册 | 速度 | 适合 |
| --- | --- | --- | --- | --- |
| Pollinations 公共通道（`text.pollinations.ai`，模型 GPT-OSS-20B） | 免费、无需 Key | 不需要 | 慢（单次 10–90 秒；公共通道约每 45 秒限 1 次） | **默认演示**，开箱即用 |
| 智谱 `GLM-4-Flash` | 免费 | 需手机号注册拿 Key | 快（数秒） | 日常使用推荐 |
| ModelScope 魔搭免费推理（如 `Qwen2.5-72B-Instruct`） | 每日免费额度 | 需注册拿 access token | 较快 | 想要更聪明时 |
| DeepSeek 官方 API | 按量计费 | 需注册充值 | 快 | 正式运营 |

当前仓库默认配置（免注册、零成本，适合演示）：

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://text.pollinations.ai/openai
DEEPSEEK_MODEL=openai-fast
DEEPSEEK_MODEL_LABEL=GPT-OSS-20B（免费公共通道）
DEEPSEEK_TIMEOUT_SECONDS=150
```

免费公共通道的取舍（已实测）：问答全文约 6–13 秒（SSE 流式首字约 4.6–7.8 秒），AI 匹配约 10 秒，**同一 IP 约每 45 秒只能调用 1 次**（连续操作会提示「免费通道限速」）；它是推理模型，匹配模式已自动加 `reasoning_effort=low` 并压缩上下文（仅可选的 67 个组、约 19KB），避免输出 token 被思考过程吃光。质量明显强于小模型，但深度不如付费模型，回答仍须核对官方信息、不构成填报建议。

换成免费且更快的智谱 GLM-4-Flash（推荐）：

```dotenv
DEEPSEEK_API_KEY=<智谱 API Key>
DEEPSEEK_BASE_URL=https://open.bigmodel.cn/api/paas/v4
DEEPSEEK_MODEL=glm-4-flash
DEEPSEEK_MODEL_LABEL=GLM-4-Flash（免费）
DEEPSEEK_TIMEOUT_SECONDS=60
```

其他 OpenAI 兼容平台同理：填写该平台的 HTTPS Base URL（不含 `/chat/completions`）、Key 与模型标识，不要混用。`.env.example` 里已给出 Pollinations / 智谱 / ModelScope / DeepSeek 官方四组示例。公共通道不需要 Key 也视为已配置；其他平台没配 Key 时，其他页面仍可运行，问答接口会明确提示服务未配置，鉴权、额度、模型不支持或超时错误不会伪装成 AI 回答。免费公共通道有速率限制且不保证稳定性，正式上线建议换成自己账号的免费额度平台或官方 API。

页面显示的是 `DEEPSEEK_MODEL_LABEL`，实际请求使用 `DEEPSEEK_MODEL`；前端不能自行选择或覆盖模型。后续新增大模型功能应复用同一调用层。

问答通过 [问答 SKILL.md](backend/app/skills/chat-advisor/SKILL.md) 定义资料使用和事实边界。默认附带当前登录账号的最新考生画像（省份、年份、分数、位次、选科和偏好），以及最近最多 10 份已保存方案的完整志愿顺序、院校专业组信息、风险分布和保存时的画像快照；不发送账号名、邮箱、密码或账号 ID。可分别关闭画像或方案引用，也可从最近 50 份方案中指定最多 10 份。更改引用范围会清空当前对话，避免旧消息继续携带已关闭的资料。

每次提问从数据库重新读取本人资料，不能访问其他账号的方案，也不会读取浏览器中未保存的草稿。方案保持保存时的历史快照；与当前画像不一致时，skill 要求说明差异并建议重新匹配，不能把旧风险等级当作最新判断。资料上下文限制为约 100,000 字符，超过数量或容量时只附带完整方案，并在页面显示实际引用数量、名称和未附带数量；可选定目标方案重新提问。缺少画像或方案时，助手须明确说明，不得编造。

AI 回复由前端安全渲染 Markdown，支持标题、列表、加粗、代码块和表格；禁用原始 HTML 和外部图片加载，用户消息按纯文本显示。最多携带最近 10 轮对话，每次提问最多 1000 字；没有联网检索或操作志愿方案的工具。点击“停止等待”仅取消浏览器等待，已经提交到模型平台的请求可能继续执行。

## 完整演示流程

1. 注册或登录，进入考生画像，填写总分、位次、省份、年份、三门选科和兴趣偏好并保存。
2. 在招生数据中心浏览高校、专业、历年录取和招生计划；支持关键词、院校地区、层次、选科要求、生源省份和计划年份筛选。
3. 在智能院校匹配先查看规则初筛候选，设置 3–30 个专业组（默认 12），点击“开始 AI 匹配”。系统将考生画像和本库全部院校及专业组资料发送给 DeepSeek，通过匹配 skill 精选，并从数据库重建展示信息。也可打开院校详情查看选科条件、趋势、推荐理由和风险提示。
4. AI 匹配成功后，点击“生成志愿方案”，保留 AI 选择及同梯度内的优先顺序。匹配前该按钮不可用；若调整推荐数量，须重新匹配。原规则生成入口已从页面移除，规则仅用于候选过滤、数量和风险校验。优先按 1:2:1 分配冲稳保；选择 3 个时，如三个梯度都有候选则各 1 个。候选不足时仅使用实际可选项并提示，绝不放宽选科、位次或招生要求凑数。
5. 在规划中心用上下箭头调整顺序、删除或添加志愿，填写方案名称并保存。每份方案最多 30 个专业组。
6. 在我的志愿方案中查看完整历史快照、重新编辑、选择两份进行对比、删除或导出 UTF-8 BOM CSV（可用 Excel 打开）。
7. 在个人中心修改称呼或密码、退出登录。改密码和退出会使该账号既有 JWT 失效。

## 数据与算法边界

### 招生数据中心地图

招生数据中心在同一主区域展示院校列表与交互地图。点击院校会定位标记，点击标记会选中对应院校并切到其所在列表页，可继续查看专业组。地图随关键词、地区、层次和选科筛选更新，包含全部筛选院校，不受专业组分页影响。鼠标移入地图即可用滚轮缩放（到达最小/最大级别后把滚动交还页面，避免页面被“卡住”），也可拖动平移；点击点位选中院校。移动端上下排列。

**默认底图：内置省级行政区划示意（无需任何账号 / Key）**。使用 ECharts 渲染内置的中国省级行政区划 GeoJSON（来源：阿里云 [DataV GeoAtlas](https://datav.aliyun.com/portal/school/atlas/area_selector)，仅用于位置示意），叠加院校 WGS84 参考坐标点位；不加载任何第三方地图 SDK、不请求任何瓦片服务，可离线运行，院校密集时按点位大小区分规模，选中院校放大并显示名称。该底图只用于“学校大概在哪个省/城市”的示意，不作为国界、测绘成果或导航依据。

**可选底图：天地图**。需要更真实的街道/影像底图时，由**部署方**在[天地图控制台](https://console.tianditu.gov.cn/)用自己的账号申请 Web 端 Key（浏览器端），写入 `backend/.env`：

```dotenv
# backend/.env —— 运行时下发，换 Key 只重启后端，前端无需重新构建
TIANDITU_WEB_KEY=YOUR_TIANDITU_WEB_KEY
# auto（默认）：有 Key 用天地图、没有就用内置示意；也可强制 schematic / tianditu
MAP_PROVIDER=auto
```

纯静态部署（没有后端）时，才需要在前端打包前用 `frontend/.env` 的 `VITE_TIANDITU_KEY` 兜底；两份 `.env` 均已加入 Git 忽略，仓库示例只含占位值，不共享真实 Key，也不应把服务器密钥或 DeepSeek 密钥填在这里。天地图 Key 必须具备 JavaScript API 权限，并按控制台要求设置域名白名单。

**独立运营**：默认方案**完全不依赖地图账号**——底图数据内置在仓库中，任何部署方开箱即用，原开发者的账号状态不影响地图使用。选择天地图时，Key 属于部署方自己的账号，不随源码或构建产物分发；轮换/更换 Key 只需改 `backend/.env` 并重启后端。正式运营建议用项目专用账号（控制台可升级为「政府/企业开发者」，需要单位资质）申请 Key。

未配置、授权失败或网络错误时显示明确状态和重试入口，院校列表及招生查询仍可使用。天地图模式保留官方 SDK 提供的审图号和版权显示，不做瓦片预下载；示意模式保留 DataV 数据来源署名。公开发布时仍需按实际用途核对数据来源与地图服务条款，不能把更换底图当作对整个应用的合规认证。

位置来自独立的 [院校坐标文件及说明](backend/app/data/README.md)，使用 WGS84；天地图模式经 `T.LngLat(经度, 纬度)` 展示，示意模式直接用经纬度落点，不使用高德/百度偏移坐标替代。当前 58 所为学校参考位置、2 所为明确标注的城市级位置，不能用于校区导航；没有收录坐标的新学校不会伪造标记。页面不请求用户当前位置，不向地图服务发送考生画像。招生和录取信息仍是模拟数据。

### 真实数据采集模板

组员收集真实资料时，使用 [data/templates/填写说明.md](data/templates/填写说明.md) 及同目录的两份 CSV。02 收集历年录取数据；03 沿用“专业与招生计划”文件名，字段与 02 一致，仅额外增加“选科要求”，不再收集学费、学制和计划人数，两份可按需要选用。模板为 UTF-8 BOM 编码，只有表头；保留学校、专业、生源省份、年份、科类、录取数值及官方来源。不同范围的数据有区别时可写备注。当前数据库尚需扩展字段和导入校验，不能将模板直接当作现有种子数据导入。

### 当前模拟数据

- 60 所高校、120 个专业组、2160 条 2023–2025 年录取记录、720 条 2026 年计划，覆盖浙江、江苏、山东、广东、河南、四川六省模拟生源，院校地区覆盖北京、上海等 20 个省级地区。每校两个专业组及其录取、计划、选科和学费均为模拟资料，不能视为该校实际招生设置。
- 仅在同一生源省份比较位次；先过滤选科不符合、缺少录取记录或当年没有计划的专业组。
- 使用考生考试年份之前三年的记录，按由旧到新的 `1, 2, 3` 权重计算参考位次（缺少年度时使用可用记录的递增权重）。
- `位次比 = 考生位次 / 加权参考位次`：`≤ 0.80` 为保底，`≤ 1.08` 为稳妥，`≤ 1.35` 为冲刺，超过 1.35 不推荐。
- 地区和专业偏好只影响排序；先按偏好命中数排序，再优先接近参考位次的候选。没有任何“真实录取概率”或百分比成功率。
- 显示历年位次波动和风险说明；目前不建模批次、投档规则、专业调剂、体检限制或专项招生。分数只用于显示，不能由模拟分数反推出官方位次。
- 默认示例有三个梯度，但不同画像可能只匹配部分梯度或没有候选；不会为填满方案伪造候选。
- 2027 年暂无模拟招生计划，会返回空推荐；界面明确提示。
- `backend/app/services/recommender.py` 负责确定硬约束候选和冲稳保分级。`backend/app/services/ai_matching.py` 加载 [院校匹配 SKILL.md](backend/app/skills/match-universities/SKILL.md)，把最小必要的考生画像、全部已收录院校及其专业组资料、可选 ID、数量及梯度配额交给 DeepSeek。画像不含姓名、邮箱或用户 ID。
- AI 只返回 JSON 格式的专业组 ID，不能返回或修改院校名称、分数、位次、计划等展示字段。后端拒绝库外或不合格 ID、重复 ID、非整数、数量不符、额外字段及梯度配额不符的输出；通过后从原始数据库记录重建全部结果。历史位次最小/最大值仅描述历史区间，不当作当年录取线。
- 数量硬范围 3–30，默认 12；实际合格候选不足请求数量时，只返回现有候选，少于 3 个会明确提示。没有合格候选时不调用模型。后端提供各梯度可选 ID 列表；结构或约束校验失败时，最多再请求模型纠正一次，仍不合格则报错，不能用规则结果冒充 AI 输出。网络和鉴权失败不自动重试。当前单次上下文最多 500 个专业组，超出时明确拒绝，不静默截断。
- 院校目录名称可参考 [教育部全国高校名单](https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/202606/t20260618_1441074.html)，历史 985 标签可参考 [教育部 985 工程名单](https://www.moe.gov.cn/srcsite/A22/s7065/200612/t20061206_128833.html)。这些名录不是本原型模拟招生数据的来源，模型也没有实时联网核实能力。
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
| POST | `/api/recommendations/ai` | 根据画像与数据库目录运行匹配 skill；JSON 请求 `{"count":12}`，范围 3–30 |
| POST | `/api/recommendations/generate?count=12` | 生成梯度方案 |
| GET / POST | `/api/plans` | 列表 / 新建方案 |
| GET / PUT / DELETE | `/api/plans/{id}` | 查看 / 更新 / 删除本人方案 |
| GET | `/api/plans/{id}/export` | 导出本人方案 CSV |
| GET | `/api/chat/config` | 获取问答是否配置及模型显示名，不返回密钥 |
| GET | `/api/chat/context` | 获取本人画像可用状态及可选的已保存方案摘要 |
| POST | `/api/chat` | 问答 skill；默认附带本人画像及已保存方案，支持 `use_profile`、`use_saved_plans`、`plan_ids`，返回实际引用摘要 |

## 验证与构建

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

cd ../frontend
npm test
npm run build
# 预览生产构建；后端需运行，预览自动将 /api 代理到本机 8000
npm run preview
```

接口测试使用临时 SQLite 文件，覆盖认证与输入校验、同省与选科匹配、梯度计算、生成/重排/保存/快照/导出/删除、账号数据隔离、Token 撤销、过滤分页、无计划年份和初始化幂等性，不接触开发数据库。另已在本机 MySQL 8.0.38 实例验证建表初始化、注册登录、画像 JSON 存储、院校查询与匹配、方案保存修改及快照、CSV 导出、删除与 Token 撤销，并验证初始化可重复执行。本机开发 `.env` 已切换到 MySQL；SQLite 文件仍保留，已有账号和方案不自动迁移。

大模型测试使用 MockTransport，不读取真实密钥发起模型调用，也不消耗额度；覆盖统一模型选择、画像最小化、鉴权与额度错误、超时、无效响应、消息角色校验、问答接口登录校验、本人方案隔离、历史与当前画像区分、引用选择和数量/容量限制、实时重新读取、JSON 模式、AI 匹配数量边界、库外/重复/不合格 ID 拒绝、事实字段重建、候选不足及无候选、模型失败不静默降级、有限纠正重试和 AI 方案保存。后端共 **147 项**自动化测试；前端共 **31 项**测试，覆盖 Markdown 安全渲染、天地图官方 SDK 加载、无 Key 阻断、分阶段就绪、失败重试和坐标/标记联动，以及 RTM/数据版本相关页面逻辑。已使用临时 MySQL 账号完成真实模型调用，核对当前位次、两份方案名称及历史位次；临时账号和数据在验证后清理。

已有 24 所高校的开发库可在 `backend` 目录执行 `python -m app.seed` 增量扩充到 60 所；原账号、画像和已保存方案不会被覆盖。启动脚本仍只启动服务，不自动导入数据。

开发模式 Vite 自动将 `/api` 代理到 `http://127.0.0.1:8000`。独立域名部署时复制 `frontend/.env.example` 为 `.env`，将 `VITE_API_BASE_URL` 设为后端 `/api` 绝对地址，并将前端来源加入后端 `CORS_ORIGINS`，然后重新构建。部署静态文件时需为 Vue history 路由配置回退到 `index.html`。

## 常见问题

- **后端提示配置缺失**：执行 `scripts/setup_env.py`，或从 `.env.example` 配置数据库地址和随机密钥。
- **没有表或没有院校数据**：在 backend 目录执行 `python -m app.seed`；服务启动不自动写入数据。
- **前端提示连接失败**：检查后端 8000 端口与前端 API 地址；不要直接用文件协议打开 HTML。
- **5173 端口被占用**：停止已有开发服务，或修改 Vite 端口并同步 CORS；配置使用严格端口以免静默变更。
- **修改画像后无法保存草稿**：重新智能匹配并生成方案，确保每个专业组符合最新选科与位次要求。
- **生产预览**：`vite preview` 同样代理 `/api` 到本机 8000；生产发布仍须自行配置反向代理或显式 API 地址。

这是本地可运行 MVP，尚未接入真实数据或线上运维。上线前需补充官方数据授权与更新、各省规则、登录限流、HTTPS、备份、密钥管理及正式数据库迁移。
