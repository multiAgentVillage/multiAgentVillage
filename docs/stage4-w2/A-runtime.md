# A施工计划：世界、生命周期与运行基础

你和你的agent负责本页列出的实现，不再组织规则或接口讨论。先读[统一施工契约](contracts.md)；它已经冻结字段、状态、地图、默认日程和失败语义。业务依据是主计划2.4、3.2—3.6、3.11.4及W2目标。

## 1. 你的交付结果

向B提供“提案如何进入并改变世界”的完整服务，向C提供“配置如何保存、运行如何创建和控制”的应用入口。你不实现认知策略或前端，不另造HTTP协议。

1. 实现契约第2、3、7节的ExperimentService、RunCreationService及固定模板。新实验角色ID全局独立；创建运行同事务复制快照和初始化5地点/8角色/1活动，状态DRAFT。编辑实验不回写旧快照。
2. 补齐ValidateConfig、StartRun、PauseRun、ResumeRun、StopRun的解码与World行为，按契约状态表返回事件或无变化回执。新增ConfigValidated仅表达原计划的READY迁移。
3. 接收ProposeAction的MOVE/WAIT，执行所有版本、时间、占用与资源校验。MOVE计算确定性路线、保存动作；WAIT也先由World验证，写DecisionRecorded和计划唤醒点，不创建计时动作。
4. 实现Scheduler和内部advance_time。每250ms检查、1×推进；所有权威写入经过World、运行锁与UoW，到期提交幂等CompleteAction，产生一次AgentArrived并完成日程项。
5. 停止原子递增epoch、中断动作并保存停止位置。恢复严格按主计划3.6处理所有未结束状态；首次恢复继续与普通继续的事件分支按契约执行，不沿用上版“仅恢复RUNNING”的缩小规则。
6. 提供事务内命令写入器和RuleContextReader，使B无需自行实现核心命令/世界仓储。补齐事件因果链及多结果回执，根追踪字段通过显式执行上下文传入World。

## 2. 架构与文件归属

使用**Command + State**：CommandProcessor控制事务，World执行领域行为，RunState控制授权。Scheduler只发起同一处理边界，不直接写ORM；世界事务内不等待Redis或模型。

你负责后端`domain/campus_world.py`、`domain/world.py`、`domain/run_states.py`、`domain/commands.py`、`domain/events.py`、`ports/repositories.py`、`application/command_processor.py`、`application/simulation_facade.py`、`workers/runtime.py`、核心PostgreSQL仓储/ORM与迁移。新增`application/experiments.py`、`application/runs.py`作为写服务入口；对应PostgreSQL实现由你负责。

你拥有新增0003迁移，覆盖ConfigValidated枚举/CHECK及实验创建幂等元数据；禁止修改0001/0002。B负责DecisionContext扩充与装配，不要同时编辑`domain/decisions.py`或`bootstrap.py`；你通过自己的新工厂模块导出契约要求的服务。

## 3. 固定输入与输出

- C传入实验/运行创建数据及命令信封；使用契约第3节的服务签名，返回规范化配置与创建结果。C决定HTTP201/200，业务事务由你完成。
- B传入现有ProposeAction字段和新增schedule_id；不得要求B提供坐标、路径或移动耗时。你返回的世界事实进入既有Outbox。
- 提供`PostgresTransactionalCommandWriter(session).append(...)`，写入时不commit，供B与任务结果一起提交；不能要求B调用独立提交的CommandInbox替代它。
- 返回状态所需的动作segments、时段、计划版本、角色位置及计划字段；C只做读取映射和展示。

所有字段、默认数值、事件payload与恢复细节直接使用统一契约，不再与B/C重新命名。

## 4. 必须避免的错误

控制命令必须越过DEFER提案；PAUSED拒绝新通知但保留提案和到期完成。不能让当前“最早pending”选择方式堵住继续/停止。相同请求复用结果，不同请求重复控制按固定No-op处理。

暂停/停机墙钟时间不能造成恢复后的时间跳跃；时钟推进失败不能更新进程锚点。状态查询已有运行共享锁，新增所有写路径继续使用同一运行锁。停止后的旧完成命令不得再次产生到达。

世界数据、事件、Outbox与命令结果同事务提交。commands.result_event_id只是首个事件指针，完整回执按直接因果事件查询；不要丢掉停止命令产生的多个结果。

## 5. 交付与验收

第1工作日交付固定类型/服务骨架和迁移；第2—3日交付可测试的生命周期、移动与时钟；第4日供B/C真实接线；第5日交付修复与证据。

必须验证：DRAFT到停止的流程；暂停冻结；到期/控制重复10次无重复效果；事务注入失败全回滚；停止后旧epoch提案失效；恢复所有未结束状态至PAUSED且继续前校验；未来日程能被唤醒；旧运行快照不变。陈宇不早于第5秒出发，到达按实际开始加10秒并计入固定调度容差，禁止回填时间。

交付代码、增量迁移、领域及真实PG测试和`docs/stage4-w2/acceptance-A.md`。只记录实际通过的结果；不实施模型、回放、对话或地点关闭。本页是未来施工要求，本轮文档修改不代表代码已经具备这些能力。
