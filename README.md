# 校园涌现：多智能体仿真沙盒

基于[计划书2.1](docs/project-plan-v2.md)的Monorepo工程，已完成基础环境、数据契约和第三阶段“发布活动通知”纵向闭环。前端采用React、TypeScript、Vite、Ant Design、TanStack Query和Zustand；后端采用FastAPI、Pydantic v2、SQLAlchemy 2.0 asyncio、asyncpg、Alembic和redis-py asyncio。

当前可初始化5地点/8角色的开发运行、发布全体通知、查看权威事件和角色观察记忆。命令幂等、Runtime原子提交、Outbox、Redis独立消费组、消费去重与故障补偿已接通。模型决策、角色行动、完整运行控制和历史回放仍待后续迭代。

第二阶段的字段约定、GoF接口位置、表与类的对应关系、迁移及测试说明见[数据模型与核心代码契约](docs/stage2-contracts.md)。计划书正文及其落实逻辑保持不变。

第三阶段的调用链、三人开发样板、接口、故障恢复、实际验证与未完成事项见[W1最小端到端纵向闭环](docs/stage3-walking-skeleton.md)。

组员从[开发模板使用说明](docs/development-template.md)开始；计划书Word与可编辑答辩PPT见[汇报材料](deliverables/README.md)。上传前的独立审查及复测范围见[模板验收记录](docs/template-review-2026-11-05.md)。

下一阶段按W2完成规则闭环，三人分工、协作接口和验收目标见[下一阶段计划](docs/stage4-w2/README.md)。

## 目录

```text
.
├── backend/
│   ├── app/
│   │   ├── api/                 # HTTP路由、健康检查、DTO
│   │   ├── application/         # SimulationFacade、CommandProcessor等接口
│   │   ├── domain/              # World、WorldCommand、RunState等领域边界
│   │   ├── cognition/           # CognitionObserver、PerceptionService等接口
│   │   ├── ports/               # ModelGateway、仓储契约
│   │   ├── infrastructure/
│   │   │   ├── postgres/       # SQLAlchemy Base与14张表的ORM
│   │   │   ├── redis/          # redis.asyncio连接
│   │   │   ├── providers/      # ProviderAdapter接入位置
│   │   │   └── realtime.py
│   │   ├── workers/            # runtime、outbox、cognition入口
│   │   └── bootstrap.py        # 共享配置、资源装配与关闭
│   ├── alembic/                # 异步迁移环境、0001基线与0002数据模型
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                   # UI骨架、查询Provider、API客户端和UI状态
├── docs/                       # 计划书、UML和原型
├── .env.example
└── docker-compose.yml
```

完整后端包和文件名按计划书3.11.8保留。`domain/`不导入FastAPI、SQLAlchemy、Redis或模型SDK；具体连接和资源装配位于`infrastructure/`与`bootstrap.py`。

## 使用Docker Compose启动

需要已运行的Docker Engine或Docker Desktop（Linux容器模式），以及Docker Compose v2.24或更高版本。命令均从仓库根目录执行；首次构建需要连接Python、npm及容器镜像仓库。

先复制环境配置。PowerShell：

```powershell
Copy-Item .env.example .env
```

Bash：

```bash
cp .env.example .env
```

然后校验配置、构建并启动：

```bash
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
docker compose logs --tail=100 api runtime cognition
docker compose exec -T api python -m app.seed
```

初始化默认创建`demo-campus-run`，陈宇位于教学楼；重复执行返回`created:false`且不覆盖已有数据。需要独立运行可传`--run-id another-demo-run`。初始化完成后在工作台输入通知内容并点击“发布全体通知”，先显示已接收，查到对应权威事件后显示已生效。

默认访问地址：

| 入口 | 地址 | 功能 |
| --- | --- | --- |
| 前端 | http://localhost:5173 | 通知工作台、事件时间线、角色记忆与依赖状态 |
| API文档 | http://localhost:8000/docs | FastAPI OpenAPI文档 |
| API存活 | http://localhost:8000/health/live | API进程响应 |
| API就绪 | http://localhost:8000/health/ready | 实际检测PostgreSQL与Redis，失败返回503 |
| 前端代理 | http://localhost:5173/api/health/ready | 验证浏览器→Nginx→API链路 |

若修改`.env`中的端口，请同步调整上述地址。

## 六个服务与启动顺序

| 服务 | 镜像/入口 | 职责 |
| --- | --- | --- |
| frontend | Vite构建产物＋Nginx | 提供静态页面，代理`/api/`与预留的`/ws/`路径 |
| api | 共享后端镜像，`app.api.main:app` | 先执行`alembic upgrade head`，再启动Uvicorn |
| runtime | 同一后端镜像，`python -m app.workers.runtime` | 处理持久化命令，原子提交事件并发布Outbox |
| cognition | 同一后端镜像，`python -m app.workers.cognition` | cognition组消费、观察记忆与PostgreSQL补偿 |
| postgres | PostgreSQL 17 | 同一数据库供三个后端进程共享 |
| redis | Redis 7.4 | Streams运行环境，启用AOF持久化 |

`api`是后端镜像的唯一构建入口，`runtime`和`cognition`复用相同`BACKEND_IMAGE`。PostgreSQL与Redis健康后，API执行迁移并启动；API就绪后再启动Worker和前端。没有额外的迁移服务。依赖检查失败时，Worker应暴露启动失败而非假装运行成功。

API负责真实依赖就绪检查及display组消费；前端`/healthz`只检查静态服务器。`/ws/runs/{run_id}/updates`向浏览器发送增量提示，浏览器再按seq补拉权威事件。Redis暂时不可用时就绪检查返回503，已运行API仍可将通知保存到PostgreSQL，后台循环在故障恢复后继续处理。

Alembic保留空的`0001_baseline`，新增`0002_core_schema`创建计划书3.9节的14张表。新环境执行`alembic upgrade head`会依次应用两版；已有第一阶段数据库会从`0001`增量升级。API与Worker不调用`metadata.create_all()`。回退到`0001_baseline`会删除第二阶段全部业务表，仅用于可丢弃的测试库。

## 环境变量

根目录`.env`由Compose读取并显式传入后端；`.env.example`提交到仓库，真实`.env`被忽略。

| 配置 | 用法 |
| --- | --- |
| `BACKEND_IMAGE` | 三个后端服务共用的镜像标签 |
| `APP_ENV` | 当前运行环境 |
| `POSTGRES_HOST/PORT/USER/PASSWORD/DB` | 数据库连接；容器中主机名为`postgres`，端口5432 |
| `DATABASE_URL` | 可选覆盖，使用`postgresql+asyncpg://`；留空时从`POSTGRES_*`构造 |
| `REDIS_URL` | 容器中默认`redis://redis:6379/0` |
| `WORKER_POLL_INTERVAL_SECONDS` | 命令、Outbox和消费轮询间隔；不代表仿真tick配置 |
| `EVENT_STREAM` | 通知事件Stream，默认`campus:events` |
| `CONSUMER_RETRY_IDLE_MS` | pending消息回收前的最小空闲毫秒数 |
| `CONSUMER_RECONCILE_INTERVAL_SECONDS` | 各消费组独立PG补偿间隔，默认3秒 |
| `BIND_ADDRESS` | 宿主机绑定地址，默认127.0.0.1 |
| `FRONTEND_PORT/API_PORT` | 宿主机HTTP端口 |
| `POSTGRES_PUBLISHED_PORT/REDIS_PUBLISHED_PORT` | 本机开发工具使用的映射端口；不改变容器内部端口 |
| `VITE_PROXY_TARGET` | 本机Vite代理目标，默认本机8000端口 |

浏览器HTTP请求使用相对`/api`路径，WebSocket使用同源`/ws`路径。Vite开发服务器和Nginx去掉对应代理前缀；业务API自身不增加该前缀。后端配置中的模型密钥不得通过`VITE_*`暴露到浏览器，本阶段不需要模型账户。

## 本机开发与检查

本机开发需要Python 3.12、Node.js 22.12或更高版本。容器镜像负责容器内依赖；本机调试使用独立虚拟环境。

先只启动基础依赖：

```bash
docker compose up -d --wait postgres redis
python -m venv .venv
```

PowerShell从仓库根目录安装并设置本机连接：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '5432'
$env:REDIS_URL = 'redis://127.0.0.1:6379/0'
$env:DATABASE_URL = ''
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.seed
..\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

数据库用户名、密码、名称及发布端口如有修改，本机环境变量也应使用同一组值。另开终端可从`backend/`运行`python -m app.workers.runtime`或`python -m app.workers.cognition`，使用同一虚拟环境和本机连接变量。Worker接收Ctrl+C或容器SIGTERM后关闭连接并退出。

前端另开终端：

```bash
cd frontend
npm ci
npm run dev
```

前端默认代理到本机8000端口；也可将`VITE_PROXY_TARGET`设为其他API地址。若同机已运行Compose前端，需先停止它或选择其他Vite端口。

检查命令：

```powershell
# 从仓库根目录运行后端测试
.\.venv\Scripts\python.exe -m pytest backend/tests
```

```bash
cd frontend
npm run typecheck
npm run build
npm test
```

后端的版本以`backend/pyproject.toml`中的固定值为准；前端直接依赖固定版本并提交`package-lock.json`，容器使用`npm ci`安装。

## 更新与停止

工程文件构建进镜像，不默认挂载宿主机源代码。修改后重建：

```bash
docker compose up --build -d --wait
docker compose down
```

`down`保留命名卷；PostgreSQL和Redis数据保存在各自卷中。仅需清空本地开发数据时使用`docker compose down --volumes`。已有PostgreSQL卷不会因修改`.env`自动重建用户或密码。

## 当前切片与下一阶段

`SimulationFacade → CommandInbox → CommandProcessor → World`及`OutboxDispatcher → RedisStreamTransport → EventHub`已针对PublishNotice实现。其它命令、`DecisionService → DecisionStrategy → ModelGateway`与历史回放仍保留接口，不能作为已实现功能使用。完整运行控制及应用重启转PAUSED规则留待下一阶段；当前开发运行固定仿真时间，重启会继续处理持久化通知。

## 第一阶段验证记录

已通过前端TypeScript检查与构建、后端5项配置/健康/退出测试、依赖兼容性检查、Alembic离线迁移、目录与领域依赖边界检查，以及官方Compose JSON Schema校验。健康测试使用测试替身，不替代真实PostgreSQL/Redis联调。

2026-11-05已在用户授权的Ubuntu 26.04服务器上完成镜像构建与六容器实际启动验证：四个带探针服务healthy，两个Worker持续running且无异常重启。真实PostgreSQL/Redis连接、Alembic基线、Nginx代理、静态资源、共享后端镜像ID、容器内5项测试及Worker正常退出/重启检查均通过。

详见[服务器验证记录与访问方式](docs/server-verification-2026-11-04.md)及[机器可读验收结果](docs/server-verification-2026-11-05.json)。首次构建使用了用户批准的腾讯云Docker镜像源；为解决官方PyPI下载缓慢，后端构建另外使用了项目级临时SSH代理与构建网络覆盖，Dockerfile及依赖版本未改，代理通道已关闭且未写入运行镜像环境。现有镜像可用`docker compose up -d --no-build --pull never --wait`直接启动。

## 第二阶段验证记录

本地101项测试通过，真实PostgreSQL测试默认跳过；在服务器的独立测试库显式启用后，全部116项测试通过。已实际验证空库升级、14张表、ORM结构比对、回退至`0001_baseline`及重新升级；重新升级后的15项数据库集成测试也通过。

第二阶段验收时独立测试库已清理，运行实例仍为第一阶段版本。该历史记录之后，第三阶段已将原运行实例实际升级至`0002_core_schema`，见下文。接口约定与迁移命令见[第二阶段说明](docs/stage2-contracts.md)。

## 第三阶段验证记录

已完成前后端镜像构建，并将原六容器环境升级到`0002_core_schema`，保留原PostgreSQL/Redis容器及数据卷。默认运行已初始化；现在可以发布通知、查看时间线和陈宇等角色的观察记忆。

后端本地135项测试通过；最终镜像连接真实PostgreSQL/Redis时175项通过。前端6项逻辑测试、类型检查和构建通过。实际服务器浏览器10项检查，以及Runtime/Cognition重启、重复投递和Redis临时中断恢复检查均通过。验收快照中6条通知产生48条记忆，两组分别处理8次投递，pending和lag均为0。

完整启动、SSH访问、实际结果及未完成事项见[第三阶段说明](docs/stage3-walking-skeleton.md)，结构化证据见[第三阶段验收结果](docs/stage3-verification-results.json)。模型决策、角色行动、完整运行控制和历史回放不在本阶段交付范围。
