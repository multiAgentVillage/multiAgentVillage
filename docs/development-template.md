# 小组开发模板使用说明

当前模板覆盖一条可运行的业务链：发布通知 → 命令持久化 → Runtime执行 → 事件与Outbox提交 → 双消费组 → 角色记忆与前端回显。模型决策、角色行动、完整运行控制与历史回放仍是后续工作。

## 启动与阅读顺序

1. 按根目录[README](../README.md)配置环境、启动六服务并执行`python -m app.seed`。初始化重复执行不会覆盖已有数据。
2. 阅读[第二阶段契约](stage2-contracts.md)，确认正式字段、数据库状态、领域依赖边界。
3. 阅读[第三阶段调用链](stage3-walking-skeleton.md)，沿发布通知样板追踪一次请求，再阅读对应测试。
4. 总体设计以[计划书v2.1](project-plan-v2.md)和[可编辑UML](uml-v2/README.md)为依据；历史答辩材料不代替当前代码契约。

## 三人扩展入口

| 方向 | 先读的样板 | 扩展约束 |
| --- | --- | --- |
| A：领域与事务 | `domain/campus_world.py`、`application/command_processor.py`、`infrastructure/postgres/repositories.py` | 命令只转发领域行为；先锁运行，再原子提交状态、事件、Outbox与结果 |
| B：消息与认知 | `application/outbox_dispatcher.py`、`infrastructure/redis/transport.py`、`cognition/observers.py` | 网络等待在世界事务之外；收据与消费副作用一起提交，成功后ACK |
| C：接口与产品 | `api/workbench.py`、`frontend/src/features/workbench/` | 已接收不代表已生效；按匹配command_id的权威事件确认，支持原请求重试与断线补拉 |

## 新功能合入前

- 保持Facade、Command、State和Observer的职责，领域不导入数据库或消息客户端。
- 改字段、枚举或事件语义时同步契约、图源与有实际行为意义的测试；已发布迁移不原地改写。
- 所有世界写入遵守同一运行锁；工作台状态读取持运行共享锁。新增写路径不得绕开该约定。
- 通知在暂停期间拒绝；后续行动提案暂存与通知拒绝是两种不同业务规则。
- 当前通知用command_id作为根correlation_id；以后引入衍生命令时必须传播根追踪标识。
- 运行后端测试、前端`npm test`和`npm run build`。真实数据库测试只使用独立测试库，跳过不算通过。

代码仍有后续阶段接口占位；不要把占位方法当作已实现能力。独立审查范围与已知限制见[模板验收记录](template-review-2026-11-05.md)。
