# 第二阶段：数据模型与核心代码契约

依据计划书2.1的3.3、3.9及3.11节冻结接口与存储结构，沿用原组件职责、事务边界和运行规则。本文是代码入口说明，不替代或修改计划书。

## 1. 范围与使用方式

本阶段交付事件/命令信封、GoF核心接口、14张ORM表和增量迁移。具体命令的`execute()`只向`World`转发；状态机、命令选择、事件分发、认知处理、模型调用及回放仍待实现。连接生命周期和六服务部署方式沿用第一阶段。

`domain/`仅依赖Python标准库与Pydantic，不导入FastAPI、SQLAlchemy、Redis或模型SDK。ORM位于`infrastructure/postgres/models.py`；后续通过仓储将ORM记录转换为领域对象，避免把数据库会话传入`World`。

## 2. 事件与命令

| 契约 | 文件 | 约定 |
| --- | --- | --- |
| `DomainEvent` | `backend/app/domain/events.py` | 3.3节完整事件信封，具有`event_id`及运行内正整数`seq` |
| `EventDraft` | 同上 | 尚未分配`event_id/seq`的事件，其他信封字段齐全 |
| `CommandEnvelope` | `backend/app/domain/commands.py` | `command_id/request_id/run_id/type/schema_version/payload` |
| `WorldCommand`及具体命令DTO | 同上 | 解码后调用强类型`World`方法，不访问外部基础设施 |
| 公共校验与JSON类型 | `backend/app/domain/contract_types.py` | 非空字符串ID、严格整数、时区时间与不可变JSON对象 |

正式JSON字段统一为`type`和`payload`，不使用`payload_json`；`.kind`是内部只读兼容属性，不进入序列化结果。ID允许`evt-00042`、`run-001`等字符串，不强制UUID。`seq/schema_version`为正整数，`sim_time_ms`非负；事件时间必须带时区，验证后转换为UTC。未知字段、未知枚举、非法JSON值均拒绝。

Pydantic模型冻结属性赋值；`FrozenJsonObject`将嵌套对象复制为只读映射、数组复制为tuple。写入JSONB或发送HTTP/Redis前使用`model_dump(mode="json")`获得标准dict/list，不能直接把不可变包装对象交给数据库驱动。

```python
from app.domain.events import DomainEvent

event = DomainEvent.model_validate({
    "event_id": "evt-00042", "run_id": "run-001", "seq": 42,
    "type": "LocationClosed", "schema_version": 1,
    "sim_time_ms": 420000, "occurred_at": "2026-11-02T02:00:00Z",
    "correlation_id": "trace-007", "causation_id": "cmd-007",
    "payload": {"location_id": "activity-room", "reason": "临时维护"},
})
wire_data = event.model_dump(mode="json")
payload_for_jsonb = wire_data["payload"]
```

`EventType`包含计划书的15种事件：`RunStarted`、`RunPaused`、`RunResumed`、`RunStopped`、`NoticePublished`、`LocationClosed`、`ActivityTimeChanged`、`AgentObserved`、`DecisionRequested`、`DecisionRecorded`、`ActionStarted`、`AgentArrived`、`MessageDelivered`、`ActionInterrupted`、`ActionRejected`。

`CommandKind`包含10种命令：`ValidateConfig`、`StartRun`、`PauseRun`、`ResumeRun`、`StopRun`、`PublishNotice`、`CloseLocation`、`ChangeActivityTime`、`ProposeAction`、`CompleteAction`。

`CommandReceipt`中的`accepted`表示已保存；持久化的`commands.status`只使用`pending/applied/rejected`。暂停时暂存的命令仍为`pending`，不能把`accepted/deferred`直接写入该列。`commands.correlation_id`是额外的请求追踪元数据，由后续`CommandInbox`从请求上下文补充，未提供时可采用`request_id`；不能只展开信封就忽略该必填字段。

## 3. GoF核心接口位置

| GoF模式 | 计划书名称与代码位置 | 本阶段边界 |
| --- | --- | --- |
| Command | `domain/commands.py`中的`WorldCommand`和具体命令；`domain/world.py`中的`World`；`application/command_processor.py`中的`CommandProcessor` | 仅契约和命令转发；`ports/repositories.py`定义`CommandCodec`及事务内仓储 |
| Observer | `cognition/observers.py`中的`EventObserver`；`infrastructure/redis/transport.py`中的`EventHub` | 声明订阅/通知接口；`CognitionObserver/RealtimeObserver`保留实现入口 |
| Strategy | `domain/strategies.py`中的`DecisionStrategy`；`application/decision_service.py`中的`DecisionService` | `RuleDecisionStrategy/LLMDecisionStrategy`共享输入与输出契约，暂无决策算法 |
| State | `domain/run_states.py`中的`RunState/RunStatus/Disposition` | 状态接口与枚举；具体状态授权规则后续实现 |
| Adapter | `ports/model_gateway.py`中的`ModelGateway/ModelRequest/ModelResponse` | `ProviderAdapter`保留接入入口，不调用外部服务；未知Token使用`None` |
| Facade | `application/simulation_facade.py`中的`SimulationFacade` | 注入`CommandInbox/ReadService/ReplayService`，暂无业务路由或持久化实现 |
| Memento | `domain/memento.py`中的`WorldMemento/ReadOnlyView`；`ports/repositories.py`中的`SnapshotStore`；`application/replay_service.py`中的`ReplayService` | 只读回放返回`ReadOnlyView`，不向调用者暴露世界写接口；暂无回放算法 |

`UnitOfWork`统一提供`worlds/commands/events/outbox`和事务生命周期。后续`CommandProcessor`在同一事务内保存权威状态、事件、Outbox及命令结果；定义接口不代表已经实现原子提交。Redis发布与模型等待仍在世界事务之外。

## 4. ORM与约束

数据库ID采用`String(128)`，JSON使用PostgreSQL JSONB，真实时间使用带时区的`DateTime`，仿真时间使用整数毫秒。枚举列采用字符串加命名CHECK，保存枚举的值；新增事件或命令类型时需同步更新契约、ORM、迁移与兼容处理。

| 表 | ORM类 | 关键存储与约束 |
| --- | --- | --- |
| `experiments` | `Experiment` | 可编辑实验配置、名称与时间戳 |
| `agent_profiles` | `AgentProfile` | 实验内角色资料、兴趣、目标、日程与配置 |
| `runs` | `Run` | 状态、仿真时间、epoch、last_seq、config_snapshot及调用预算 |
| `agent_states` | `AgentState` | `(run_id,agent_id)`主键；计划版本、位置、动作参数与起止时间 |
| `location_states` | `LocationState` | `(run_id,location_id)`主键；开放状态、容量、资源版本 |
| `activities` | `Activity` | `(run_id,activity_id)`主键；时间、资源版本、参与者JSON数组 |
| `commands` | `CommandRecord` | `request_id`全局唯一；类型、payload、处理状态、结果事件与追踪字段 |
| `events` | `EventRecord` | `event_id`主键；`(run_id,seq)`唯一；完整事件信封 |
| `outbox` | `OutboxRecord` | `event_id`唯一；发布时间、重试次数、下次尝试时间 |
| `consumer_receipts` | `ConsumerReceipt` | `(consumer_name,event_id)`复合主键，提供所需去重唯一性 |
| `memories` | `Memory` | 角色、来源事件、内容、仿真时间、重要度与主题 |
| `decision_jobs` | `DecisionJob` | `task_key`唯一；输入上下文及版本、租约、重试、结果；每角色最多一个pending/running任务的部分唯一索引 |
| `model_calls` | `ModelCall` | 任务、模型/规则来源、请求状态、模型/提示词版本、延迟与可空Token |
| `snapshots` | `Snapshot` | 运行、seq、仿真时间、schema_version、world_state、canonical_hash；游标三元组唯一 |

事件、来源事件、地点、活动和任务之间的复合外键限制跨运行关联。`events.causation_id`可以引用命令或事件，因此不强制绑定单一表的外键。角色运行状态取自运行配置快照，不外键关联后续可编辑的角色资料。

`config_snapshot`的不可变性、事件追加、预算预留、消费去重的原子性、快照hash生成及历史重放仍由后续应用服务实现；本阶段不通过数据库触发器实现业务。ORM的`updated_at`在SQLAlchemy更新时刷新，直接SQL写入者应自行更新。快照允许同一seq对应不同仿真时间，以保存没有新事件时推进的时钟。

## 5. 迁移与检查

保持`0001_baseline`不变，新增独立、固定DDL的`0002_core_schema`；迁移不导入实时ORM元数据。配置连接后，从`backend/`执行：

```bash
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest -q
```

普通测试不要求数据库；PostgreSQL集成测试默认跳过。只对已迁移的独立测试数据库显式启用：

```powershell
# 数据库应由测试使用者事先创建，名称包含test，连接变量指向该库
$env:POSTGRES_DB = 'campus_stage2_test'
$env:RUN_POSTGRES_TESTS = '1'
python -m alembic upgrade head
python -m pytest tests/test_postgres_integration.py -q
```

若设置过`DATABASE_URL`，它优先于`POSTGRES_*`，必须一并指向独立测试库。集成测试不创建/删除表，每项测试在事务结束时回滚。迁移回退仅用于可丢弃测试库：`python -m alembic downgrade 0001_baseline`会删除全部14张业务表及其数据，再以`upgrade head`验证重新升级。

第一阶段服务器六容器验收记录保留原状态，不表示第二阶段已经部署到现有运行数据库。

## 6. 验证记录（2026-11-05）

本地Python 3.12环境：101项测试通过，PostgreSQL集成测试模块按默认配置跳过。Windows沙箱中的异步健康测试挂起，使用已授权的沙箱外环境完成回归。

在已授权Ubuntu服务器上，复用第一阶段后端镜像的固定依赖，将本轮代码只读挂载到临时容器，连接PostgreSQL 17.11中的独立测试库；未替换现有API或Worker代码，未对现有`campus`数据库应用第二阶段迁移。

| 检查 | 结果 |
| --- | --- |
| 从空库升级到head | 成功，版本为`0002_core_schema`，14张业务表 |
| ORM与迁移结构比对 | `alembic check`通过，无新增升级操作 |
| 全部后端测试，显式启用真实PG | 116项通过，其中15项真实PG集成测试 |
| 回退到`0001_baseline` | 成功，业务表数量为0，保留迁移历史 |
| 从`0001_baseline`重新升级 | 成功，`alembic check`再次通过，15项PG集成测试再次通过 |
| 验证后清理与原环境 | 独立测试库已删除；原六服务保持运行，原数据库仍为`0001_baseline` |

测试覆盖JSONB及时区时间、未知Token保留NULL、运行内事件序号、请求幂等、Outbox、消费收据、决策任务唯一性、未完成任务部分索引、跨运行外键、快照游标及失败事务回滚。测试仅证明契约与数据库约束，不表示`CommandProcessor`、可靠消费、预算策略或历史回放已经实现。

本轮上传的后端源码归档SHA-256：`b4ea72c6fc3b55e6a867fd89af8da386d9ec5d35c5b0e35e01bacae0d964d647`。测试复用镜像为`campus-sandbox-backend:verify-bcb02f6b`，固定依赖来自第一阶段构建，业务源码通过临时只读挂载提供。现有服务后续升级时应按README重新构建镜像并由API执行迁移。
