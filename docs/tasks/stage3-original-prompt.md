# 第三阶段原始执行提示词（历史归档）

以下保留曾误嵌入计划书5.2节的提示词原文，供追踪使用，不作为当前代码契约。实际范围、拒绝语义、追踪与验证结果以[第三阶段说明](../stage3-walking-skeleton.md)和[模板验收](../template-review-2026-11-05.md)为准。

请先阅读 `@project-plan-v2.md`（重点关注 3.4、3.5、3.11.6 时序图 U06a/U06b、3.11.9 节及 5.2 节 W1 目标）与 `@docs/stage2-contracts.md`。

第二阶段的强类型契约、GoF 接口与 14 张 ORM 表迁移（`0002_core_schema`）已经验证通过。现在进入【第三阶段：打通 W1 最小端到端纵向闭环样板（Walking Skeleton）】。
请以 `PublishNotice`（发布通知命令）-> `NoticePublished`（通知已发布事件）为最小业务切片，串联起 API、PostgreSQL、Runtime、Outbox、Redis Streams、Cognition 与前端工作台，为三位组员提供标准编码样板。

请严格遵守 `docs/stage2-contracts.md` 中的契约约束，完成以下具体任务：

1. 最小初始化与提交/查询入口（API 进程）：
   - 提供一个最小实验/运行初始化入口（如 `POST /runs` 或启动种子数据），能在数据库中创建一条处于 `RUNNING` 状态的默认运行（含基础 `config_snapshot`、5 个地点与 8 名角色初始状态），以便端到端联调。
   - 实现 `CommandInbox` 与 `SimulationFacade.submit()`：处理 `request_id` 幂等（重复提交返回已有回执）；入库时自动补充必填的 `commands.correlation_id`（未提供时采用 `request_id`）；`commands.status` 严格写入 `"pending"`，返回 `202 Accepted` 与 `CommandReceipt`。
   - 实现 `POST /runs/{id}/commands`、`GET /runs/{id}/state`、`GET /runs/{id}/events?after_seq=` 以及 `WS /runs/{id}/updates`。

2. UnitOfWork 与 Runtime 命令处理闭环（Runtime 进程）：
   - 在 `infrastructure/postgres/` 中实现异步 `UnitOfWork` 及对应的仓储（负责 ORM `models.py` 与 `domain/` 对象之间的转换，严禁将 SQLAlchemy Session 传入 `World`；写入 JSONB 前统一使用 `model_dump(mode="json")` 处理 `FrozenJsonObject`）。
   - 实现 `RunningState` 与 `PausedState` 的最小授权逻辑，以及 `World.publish_notice()` 生成 `EventDraft(type=EventType.NoticePublished)`。
   - 实现 `CommandProcessor.process_next(run_id)`：在同一个短数据库事务内锁定 `Run` 行（`SELECT ... FOR UPDATE`）-> 选取下一条 `pending` 命令 -> `CommandCodec` 解码 -> 校验状态并执行命令 -> 递增 `Run.last_seq` 补全 `DomainEvent` 信封 -> 原子保存 `worlds`、`events`、`outbox` 并将命令状态更新为 `"applied"`（或拒绝时记为 `"rejected"` 并记录 `ActionRejected`）。
   - 在 `workers/runtime.py` 与 `workers/outbox.py` 中接通调度循环与 `OutboxDispatcher`：轮询未发布的 `OutboxRecord`，通过 `RedisStreamTransport`（XADD）发布事件并标记 `outbox` 已发布。

3. 双消费组与幂等消费样板（API 进程 & Cognition 进程）：
   - 展示消费组（API 进程）：`RealtimeObserver` 通过 `XREADGROUP` 消费 Redis Streams 事件，向 `WS /runs/{id}/updates` 连接推送包含最新 `seq` 的轻量通知，成功后 `XACK`。
   - 认知消费组（Cognition 进程）：`CognitionObserver` 通过 `XREADGROUP` 消费事件，在同一个短数据库事务内写入 `ConsumerReceipt(consumer_name, event_id)` 复合主键去重记录及一条最小观察记忆（`Memory`），事务提交后再执行 `XACK`（验证重复投递不产生重复副作用）。

4. 前端最小工作台联调样板（`frontend/`）：
   - 在前端页面打通闭环：展示当前 `run_id` 与运行状态；点击“发布活动通知”按钮发送 `POST /runs/{id}/commands`（携带唯一 `request_id`），界面立即显示“① 已接收”；收到 WebSocket 更新通知后，自动请求 `GET /runs/{id}/events?after_seq=` 补拉权威事件，将状态更新为“② 已生效”并在事件时间线列表中渲染该条 `NoticePublished` 事件。

5. 测试与六容器环境升级验证：
   - 补充端到端闭环集成测试（覆盖：命令幂等提交 -> `process_next` 原子落库与 Outbox 生成 -> 重复消费被 `ConsumerReceipt` 拦截 -> `after_seq` 增量查询）。
   - 将现有运行环境的数据库正式迁移升级至 `0002_core_schema`，重新构建并启动六容器，验证从前端/API 提交命令到事件分发回显的完整链路畅通。
