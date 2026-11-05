# 基于EDA的多智能体校园仿真沙盒：八周项目规划（v2）

版本：v2.1 · 2026-11-04 · 团队：共3人 · 已选方案：轻量校园小镇

修订说明：统一采用UML图和GoF表中的组件、类与接口名称，合并重复职责说明；产品范围、调用顺序、事务边界、状态规则和验收要求沿用v2.0。术语见3.2，UML及模式实现见3.11。

本规划优先满足“架构设计与产品完整度”。范围、性能和工时均为规划目标，尚未通过实现验证。暂按每人每周18小时计算：3×8×18＝432人时，其中约324人时用于功能，108人时用于评审、联调、测试、部署与文档。若实际投入更少，按文末裁剪顺序收缩范围，保留核心闭环。

## 1. 项目背景与目标

### 1.1 背景与问题

生成式智能体结合角色设定、记忆与环境进行交流和决策。斯坦福Generative Agents以记忆、检索、反思和规划组织25个角色的小镇，为本项目提供认知机制参考。[论文](https://arxiv.org/abs/2304.03442)

本项目协调持续变化的世界与异步决策，重点处理场地变化导致提案过期、暂停后的迟到响应、重复消息和模型不可用，并保留可解释、可回放的历史。

EDA将世界变化记录为事件，驱动感知、决策、展示与统计协作。

### 1.2 产品定位

面向教学演示、行为观察与架构验证的Web仿真工具。用户作为观察者和实验操作者，配置角色、启动校园世界、注入受约束的事件，查看角色如何响应，并回看完整过程。

建议项目名：**校园涌现：基于事件驱动的多智能体仿真沙盒**。

主场景：校园社团活动筹备。组织者发布邀请，角色依据兴趣和安排选择行动；活动室临时关闭后，角色通过观察或消息获知变化，调整计划或通知他人。

### 1.3 交付目标与成功标准

| 目标 | 八周验收证据 |
| --- | --- |
| 完整产品闭环 | 新建仿真→配置→运行→干预→检查角色→停止→回放→导出摘要可连续完成 |
| 多智能体自主行为 | 默认8名角色可执行移动、交谈、等待、参与活动；同一通知下存在不同响应，不要求固定剧情 |
| EDA设计有效 | 同一事件可被认知、展示等独立订阅者处理；新增统计订阅者不修改世界状态处理逻辑 |
| 状态一致 | 重复消息、迟到模型响应、暂停/停止、场地变化均有明确规则和验证用例 |
| 可观察、可回放 | 每个已执行关键动作关联触发事件和决策摘要；历史回放不调用大模型 |
| 可运行、可交接 | 在约定环境用Docker Compose启动；提供初始化数据、配置示例、故障说明和演示脚本 |

### 1.4 范围边界

**必做P0：**1张二维地图、5个地点、默认8名角色、1个活动场景、角色设定编辑、运行/暂停/继续/停止、3种事件模板、记忆查看、决策依据、事件时间线、只读历史回放、基本指标、故障降级、部署与测试文档。

**选做P1：**扩展到12名角色、1×/2×节奏选择、记忆摘要、从同一配置发起多次运行并比较指标、角色关系视图。P1仅在P0验收后进入。

**本期不纳入：**3D、地图编辑器、完整物理碰撞、实时多人联机、通用插件市场、模型训练、多模型辩论、历史分支续跑、跨服务器世界、多租户和完善权限系统。MVP只在本地或受控教学环境部署；若要求公网访问，再安排认证与访问控制。

## 2. 用户画像与需求分析

### 2.1 用户画像

| 用户 | 主要任务 | 痛点 | 对应产品能力 |
| --- | --- | --- | --- |
| 实验操作者：学生、教师 | 调整角色和事件，观察行为差异 | 启动复杂；无法控制场景；重复实验难 | 预置模板、配置校验、事件干预、保存运行记录 |
| 观察者与评审者 | 在几分钟内理解系统与设计价值 | 只看到人物移动或聊天，不知道因果 | 地图、角色面板、事件时间线、行为依据、回放 |
| 项目维护者：开发团队 | 定位异常、扩展行为和事件 | 异步链路难排查，故障难重现 | 关联ID、结构化日志、重试记录、契约、规则模式 |

这三类是使用情境，不要求实现三套账号或权限。

### 2.2 核心用户旅程

1. 选择“社团活动筹备”模板，默认加载8名角色和5个地点。
2. 调整角色兴趣、目标与初始位置，检查模型连接并设置本次调用上限。
3. 启动仿真，观察日程驱动的移动和附近交流。
4. 发布活动通知，明确选择公告范围；随后关闭活动室。
5. 点击角色，查看其已知信息、相关记忆、当前计划及最近一次决策摘要。
6. 点击动作对应事件，查看其直接原因和后续结果。
7. 暂停或停止；进入历史回放，拖动时间轴，导出实验摘要。

### 2.3 功能需求与验收

| 编号/优先级 | 用户需求 | 验收方式 |
| --- | --- | --- |
| F01/P0 | 从模板创建并保存仿真 | 名称、8名角色、地图和活动配置持久化；缺失必填字段时定位提示 |
| F02/P0 | 编辑角色 | 可改角色简介、兴趣、目标、日程与起点；运行中锁定配置，避免历史含义改变 |
| F03/P0 | 控制运行 | 状态机约束按钮；重复点击不重复执行；刷新页面能恢复观察 |
| F04/P0 | 注入事件 | 支持发布通知、关闭地点、更改活动时间；提交后展示“已接收→已生效/被拒绝” |
| F05/P0 | 观察世界 | 显示位置、行动、仿真时间、场地状态；点击角色/地点展示详情 |
| F06/P0 | 检查认知 | 查看角色已感知事实、最近记忆、当前目标、决策摘要和引用记忆；未知事件不进入提示词 |
| F07/P0 | 检查事件 | 按角色、类型、时间过滤；从动作定位触发事件和结果 |
| F08/P0 | 保存并回放 | 完成或暂停的运行可只读回看；还原到事件序号，回放不改变原运行、不请求模型 |
| F09/P0 | 查看与导出结果 | 显示事件数、行动数、活动参与人数、模型调用/Token、失败与降级次数；导出JSON/CSV |
| F10/P0 | 获得故障反馈 | 模型超时、断线、队列积压、预算耗尽均可见；模型故障下可继续规则行为 |
| F11/P1 | 比较实验 | 同一初始配置新建两次独立运行，对比覆盖与参与情况；不承诺统计显著性 |

### 2.4 关键业务规则

- 地图为5个地点组成的可通行图：宿舍、教学楼、图书馆、食堂、活动室。移动依据固定路线与耗时；人物之间允许视觉重叠，本期不做物理避碰。
- 每名角色只有一个正在执行的动作，且最多一个有效认知任务。移动由`Scheduler`调度、`World`更新，模型不逐帧控制坐标。
- 对话限制为两人、同地点、双方可用；一段对话最多4条发言。对话占用双方状态，并有结束与超时机制。
- 角色只能获得同地点可观察信息、发给自己的消息及所选公告范围内的通知。模型不能读取完整世界日志。
- 场地关闭立即影响通行约束；在场角色感知关闭，其他角色通过通知或到达尝试得知。关闭时在场角色退出至相邻开放地点，行动被中断并记录原因。
- “更改活动时间”改变权威日程，但不会自动更新所有角色的知识；受影响组织者先获知，再通过交流传播。距离开始过近或已结束的修改可被规则拒绝。
- 不要求每个角色参加活动，也不预设通知一定传播给所有人。验证合法行为与信息边界，避免用“精彩故事”作为稳定性验收条件。

### 2.5 非功能目标

以一台约4核、8GB内存开发机、8名角色、单个运行、2个观察页面作为初始验证条件；模型服务在机外，条件需记录进测试报告。

| 指标 | 目标及口径 |
| --- | --- |
| 持续运行 | 规则模式连续30分钟无崩溃；真实模型模式完成一次10分钟实验 |
| 操作反馈 | 非模型API p95小于500ms；已提交世界变化到页面显示p95小于1秒，不含模型推理时间 |
| 暂停 | 请求后下一个调度边界进入暂停，目标1秒内；进入PAUSED后仿真时间与权威世界状态不变 |
| 重复处理 | 同一输入重复投递10次，世界效果只发生一次；允许重复传输，不允许重复业务效果 |
| 历史一致 | 保存快照对应状态与事件重放结果的规范化哈希一致；忽略传输时间等非世界字段 |
| 恢复 | 应用重启保留已提交记录；未完成输入可重处理；运行恢复为暂停，用户确认继续 |
| 成本 | 设置每次运行请求数与Token上限；达到上限后明确切换规则模式，Token未知时保留unknown标记 |
| 可用性 | 演示者无需读代码能完成主流程；覆盖空态、加载、错误、重连、禁用、结束状态 |

## 3. 总体架构与技术选型

### 3.1 架构决策

采用**模块化单体代码库＋异步任务＋持久化事件分发**。后端共用领域模型和数据库迁移，按API、Runtime、Cognition三种进程角色启动，支持三人并行开发与异步任务隔离。

全文以3.2和GoF表中的名称指代组件；API、Runtime、Cognition仅表示UML组件分组和进程角色。技术名称（如PostgreSQL）与数据表名（如`commands`）按原名使用。用户界面的“角色、当前行动、记忆、回放”等词保持面向使用者。

```mermaid
flowchart LR
    Web[Web工作台] -->|REST| API[FastAPI路由 / SimulationFacade]
    API --> Inbox[(CommandInbox / commands)]
    Inbox --> CommandProcessor[CommandProcessor / Scheduler]
    CommandProcessor -->|执行命令| World[World / RunState]
    World -->|EventDraft| CommandProcessor
    CommandProcessor -->|同一事务| PG[(PostgreSQL：世界状态 / events / outbox)]
    PG --> OutboxDispatcher[OutboxDispatcher]
    OutboxDispatcher --> Redis[Redis Streams / RedisStreamTransport]
    Redis -->|认知消费组 / EventHub| Cog[CognitionObserver]
    Cog -->|持久化决策任务| Decision[DecisionService / DecisionStrategy]
    Decision --> Gateway[ModelGateway / ProviderAdapter]
    Decision -->|ProposeActionCommand| Inbox
    Redis -->|展示消费组 / EventHub| Realtime[RealtimeObserver]
    Realtime -->|WebSocket通知| Web
    Web -->|按seq补拉| API
    API --> Read[ReadService / ReplayService]
    Read --> PG
```

两个数据库节点属于同一个PostgreSQL实例。PostgreSQL保存权威状态与历史；Redis Streams分发事件，消费组负责消息读取与确认，重复业务效果由3.5的去重机制防止。[Streams](https://redis.io/docs/latest/develop/data-types/streams/)、[XREADGROUP](https://redis.io/docs/latest/commands/xreadgroup/)

### 3.2 组件职责与边界

本表统一定义组件名称与职责；3.11的GoF表使用同名组件说明模式角色。

| 组件、类或接口 | 职责 | 边界 |
| --- | --- | --- |
| `SimulationFacade` | 提供配置、运行记录、命令提交与查询入口，组合`CommandInbox`、`ReadService`、`ReplayService` | 运行后锁定初始配置；提交回执不代表命令生效；不在请求中同步执行模型或世界动作 |
| `CommandInbox`、`CommandCodec` | 保存`CommandEnvelope`；按类型和版本解码为`WorldCommand` | 只接受白名单JSON；不直接修改世界状态 |
| `CommandProcessor`、`Scheduler` | 串行处理命令、控制事务；推进仿真时间并提交到期动作命令 | 模型与网络调用放在世界事务外；普通调度不触发全体角色调用模型 |
| `World`、`RunState` | 管理地点、角色、行动、日程、对话占用；校验动作、授权状态操作 | `World`是权威世界状态的唯一修改入口；不访问数据库、Redis或模型服务 |
| `UnitOfWork`、状态仓储、`EventStore`、`OutboxStore` | 原子保存状态、领域事件、Outbox和命令结果 | 事务由`CommandProcessor`控制，仓储不作角色决策 |
| `OutboxDispatcher`、`EventPublisher` | 顺序发布已提交事件，记录发送结果并重试 | 不在世界事务中等待Redis；发送成功不等于消费者处理成功 |
| `RedisStreamTransport`、`EventHub`、`EventObserver` | 消费组间分发；进程内注册和调用观察者 | 投递、ACK、去重和顺序规则见3.5；不修改权威世界状态 |
| `CognitionObserver`、`PerceptionService`、`MemoryService` | 筛选可见信息、写入和检索记忆、创建决策任务 | 角色上下文只包含其可知信息；消费事务提交后再ACK |
| `DecisionService`、`DecisionStrategy` | 执行决策任务；选择`LLMDecisionStrategy`或`RuleDecisionStrategy`，生成`ActionProposal` | 行动提案通过`ProposeActionCommand`交给`CommandProcessor`；不直接改世界 |
| `ModelGateway`、`ProviderAdapter` | 将内部模型请求与供应商协议、响应、异常、用量相互转换 | 不承担感知、角色规划或世界合法性校验 |
| `RealtimeObserver`、`ReadService` | WebSocket更新提示、当前视图查询、摘要统计 | 断线或通知丢失后按seq补拉；不把传输缓存作为权威历史 |
| `WorldMemento`、`SnapshotStore`、`ReplayService` | 封装与保存快照；还原隔离的只读历史视图 | 由`World`导出/还原；回放不执行命令、不调用模型、不覆盖当前运行 |

各组件共同记录关联日志、耗时、积压、调用量与降级原因；日志不记录API密钥或无关敏感配置。

**写入规则：**`CommandProcessor`通过`World`修改权威世界状态，并用`UnitOfWork`提交；`CognitionObserver`和`DecisionService`仅保存各自的记忆、任务、结果与提案命令。

### 3.3 事件与命令

`WorldCommand`表达可被拒绝的意图，如`CloseLocationCommand`、`ProposeActionCommand`；`CommandEnvelope`保存其消息数据，类型标识仍为`CloseLocation`、`ProposeAction`。`DomainEvent`记录已生效的事实，如`LocationClosed`、`ActionStarted`。`202 Accepted`只表示命令已保存，处理成功后页面才显示“已生效”。

核心领域事件：`RunStarted`、`RunPaused`、`RunResumed`、`RunStopped`、`NoticePublished`、`LocationClosed`、`ActivityTimeChanged`、`AgentObserved`、`DecisionRequested`、`DecisionRecorded`、`ActionStarted`、`AgentArrived`、`MessageDelivered`、`ActionInterrupted`、`ActionRejected`。处理失败等运维记录放在独立任务/日志数据中，避免递归生成领域事件。

每个事件统一携带：

```json
{
  "event_id": "evt-00042",
  "run_id": "run-001",
  "seq": 42,
  "type": "LocationClosed",
  "schema_version": 1,
  "sim_time_ms": 420000,
  "occurred_at": "2026-11-02T02:00:00Z",
  "correlation_id": "trace-007",
  "causation_id": "cmd-007",
  "payload": {"location_id": "activity-room", "reason": "临时维护"}
}
```

`seq`只在单次运行内递增，不依赖机器墙钟排序。首个原因可以是命令ID，后续原因引用事件ID。事件结构改动需要明确版本，回放代码按版本处理。

### 3.4 完整调用流程

以“关闭活动室”为例，流程中的名称与UML类图、GoF表一致：

1. FastAPI路由校验请求格式，`SimulationFacade`通过`CommandInbox`保存`CommandEnvelope`并返回`command_id`，页面显示“已接收”。
2. `CommandProcessor`在短事务中锁定run行、读取命令，通过`CommandCodec`得到`CloseLocationCommand`，加载`World`并由`RunState`决定执行、暂存或拒绝。
3. `WorldCommand.execute(world)`调用`World`领域方法。`World`校验约束、修改内存状态并返回`EventDraft`；`CommandProcessor`分配事件ID和seq，使用`UnitOfWork`一起保存世界状态、`DomainEvent`、Outbox和命令结果，再提交。此时事件才“已生效”。
4. `OutboxDispatcher`发布事件到Redis Streams，成功后标记发送结果；标记失败可能重复发布，由消费者去重。
5. 认知消费组通过`EventHub`调用`CognitionObserver`。`PerceptionService`筛选受影响角色，`MemoryService`保存记忆；去重记录、观察记忆和决策任务提交后才ACK。其他角色不会自动获知关闭事实。
6. `DecisionService`独立领取任务，选择`LLMDecisionStrategy`或`RuleDecisionStrategy`。前者经`ModelGateway`调用`ProviderAdapter`；保存结构化`ActionProposal`、决策摘要和引用记忆，并写入`ProposeActionCommand`。
7. `CommandProcessor`再次加载`World`，校验角色状态、地点开放情况、run_epoch、agent_plan_version、相关资源版本及有效期；合法动作提交并产生事件，无效提案拒绝或触发重规划。
8. 展示消费组通过`EventHub`调用`RealtimeObserver`，向Web工作台发更新提示；工作台通过`ReadService`按seq补拉权威数据。历史回放由`ReplayService`处理。

### 3.5 时间模型与一致性

- **三种时间分离：**仿真时间用于移动、日程和动作；墙钟时间用于请求超时；前端帧时间只用于平滑插值。
- `Scheduler`每250ms检查到期动作，`CommandProcessor`读取待处理命令，仿真默认1×。只有有意义的状态变化写领域事件，不记录每帧渲染位置。
- 持久化动作的起点、终点、开始与结束仿真时间；任意时刻位置由确定性插值计算。暂停后sim_time停止，前端不能继续外推。
- **单run串行执行：**锁住run行后执行短事务；模型调用与网络分发都在事务外。MVP只运行一个Runtime进程，数据库约束作为重复启动保护。[PostgreSQL锁机制](https://www.postgresql.org/docs/current/explicit-locking.html)
- **短事务原子提交：**世界状态、领域事件、Outbox和输入处理结果要一起提交。
- **投递至少一次：**`(consumer_name,event_id)`唯一约束；去重标记与该消费者的数据库副作用在同一事务；提交后才ACK。
- **广播与分工区分：**认知和展示使用不同消费组；同一组的多个Worker分担工作，不把同一组误当成多模块广播。
- **顺序控制：**单个`OutboxDispatcher`按run内seq发布；消费者检查版本和缺口。严格依赖先后关系的处理从事件表补读，不假设并行Worker完成顺序一致。
- **失败回收：**过期pending由`XAUTOCLAIM`等方式接管；数据库任务记录尝试次数，超过3次进入失败记录，可手动重试。与模型请求超时分开配置，避免长请求被反复抢占。[XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/)
- **Redis中断：**世界变化保留在PostgreSQL并积压Outbox，恢复后继续分发；Redis数据丢失可按PostgreSQL游标重新发布，幂等消费者承受重复。不是以Redis备份替代持久化设计。
- **外部调用边界：**`DecisionService`所在Worker崩溃时无法总能判断模型服务是否已收费；因此不承诺模型请求恰好一次，预算需为有限重试留余量。

### 3.6 暂停、停止与恢复

运行状态：`DRAFT → READY → RUNNING ↔ PAUSED → FINISHED`，RUNNING也可直接停止到FINISHED；不可恢复的异常进入FAILED。

- 暂停命令在调度边界生效并产生`RunPaused`。不再推进仿真时间，不应用世界行动；控制命令仍可处理。
- 暂停期间模型请求可结束并保存任务结果，但提案暂存，继续后重新验证；注入新事件的入口暂时禁用，避免“暂停却改变世界”的语义冲突。
- 停止操作需要一次确认；将run_epoch递增，未应用提案全部失效。结束状态只能观察与回放。
- 应用重启后把未结束运行恢复为PAUSED，记录恢复原因；用户继续后处理未完成输入。重新分配任务时使用唯一键防止重复。
- 校验提案使用角色计划版本与相关资源版本，不用“整个世界版本必须完全一致”，避免无关角色移动使所有提案失效。

### 3.7 智能体设计与费用控制

每名角色包括：简介、兴趣、目标、简化日程、当前位置/动作、已知信息与记忆。认知流程为“观察→写记忆→选取相关上下文→提出结构化行动→`World`校验执行”。

记忆先用PostgreSQL保存自然语言内容、来源事件、仿真时间、重要性标签与主题。检索按时间衰减、主题匹配和重要性加权，取Top-K；MVP不引入独立向量数据库。反思和向量检索保留为P1，研究项目中的完整认知机制不作为本期硬性要求。

模型只在新通知、重要交流、目标完成、动作失败等决策点调用；普通移动、等待、日程切换由规则驱动。多条近邻刺激合并，每名角色最多一个未完成任务，并记录是否需要在任务结束后再评估。

输出Schema限制动作枚举为`MOVE/TALK/WAIT/JOIN_ACTIVITY`，包含目标、短决策摘要、引用记忆ID；摘要是产品解释信息，不索取或展示模型隐含推理过程。对话内容按文本渲染，不当作指令或HTML执行。[Pydantic模型与校验](https://docs.pydantic.dev/latest/concepts/models/)

初始参数：全局模型并发2、单次请求超时20秒、最多1次请求重试、单次输出不超过约300 Token；参数须在第3—4周用真实服务校正。失败后执行等待或合法日程动作，并明确标记降级来源。

初始运行上限建议120次请求，输入上限约2000 Token/次、输出约300 Token/次，对应最多约24万输入和3.6万输出Token的预算估计；修复、重试、对话均计入请求上限。并发任务通过预算预留防止超发。真实费用按所选服务当天价格计算，不固定货币金额；需要价格时另行核验。

### 3.8 技术栈

| 层次 | 推荐 | 选择理由与边界 |
| --- | --- | --- |
| Web应用 | React＋TypeScript＋Vite | 配置表单、面板、状态可维护；版本在第1周固定并提交锁文件 |
| UI组件 | Ant Design | 减少表单、抽屉、表格和反馈组件开发量；地图使用独立样式 |
| 二维地图 | SVG＋CSS插值 | 8名角色、5地点足够；点击、路径和状态容易实现，不引入游戏引擎 |
| 前端状态 | TanStack Query＋少量Zustand状态 | 区分服务器查询缓存与当前选择/回放游标；权威世界以服务端为准 |
| 后端API | Python＋FastAPI＋Pydantic | 异步接口、事件契约、OpenAPI和WebSocket统一；不在API进程做长时认知 |
| 数据访问 | SQLAlchemy＋Alembic | 事务与迁移可审查；每个并发任务独立Session |
| 权威存储 | PostgreSQL | 世界状态、命令、事件、Outbox、任务、记忆和快照存于同一事务体系 |
| 消息分发 | Redis Streams | 消费组、ACK、pending回收；不使用只有即时通知能力的Pub/Sub替代可靠事件分发 |
| 模型接入 | ProviderAdapter | 实现一种真实服务接口与FakeModelGateway/规则模式；不同时叠加多个Agent编排框架 |
| 实时更新 | REST命令＋WebSocket通知 | 单向更新为主；断线按事件seq补拉或重新加载快照 |
| 测试 | pytest＋真实PostgreSQL/Redis集成测试＋Playwright | 核心验证事务、重复消费、状态规则与用户闭环 |
| 部署 | Docker Compose | frontend、api、runtime、cognition、postgres、redis；数据库迁移作为启动步骤 |

各并发任务独立使用SQLAlchemy Session；部署由Compose统一管理。[FastAPI](https://fastapi.tiangolo.com/advanced/websockets/)、[SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)、[Docker Compose](https://docs.docker.com/compose/)

### 3.9 最小数据模型与API

| 数据 | 关键字段/约束 |
| --- | --- |
| experiments / agent_profiles | 模板、角色、可编辑配置；运行时复制为不可变config_snapshot |
| runs | 状态、sim_time、run_epoch、last_seq、配置、预算 |
| agent_states / location_states / activities | 当前权威状态、计划版本、资源版本、活动安排与参与记录 |
| commands | request_id唯一、类型、payload、pending/applied/rejected、结果事件ID |
| events | event_id唯一、(run_id,seq)唯一、type、version、时间、因果ID、payload |
| outbox | event_id唯一、发布时间、重试次数、下一次尝试时间 |
| consumer_receipts | (consumer_name,event_id)唯一；与消费者副作用原子提交 |
| memories / decision_jobs | 来源事件、角色、内容、状态、唯一任务键、输入上下文版本 |
| model_calls | 耗时、请求状态、Token、模型/提示词版本、规则或模型来源 |
| snapshots | run_id、seq、sim_time、schema_version、世界状态和规范化hash |

API主干：`POST /experiments`、`PATCH /experiments/{id}`、`POST /runs`、`POST /runs/{id}/commands`、`GET /runs/{id}/state`、`GET /runs/{id}/events?after_seq=`、`GET /runs/{id}/agents/{agent_id}`、`GET /runs/{id}/replay?seq=`、`GET /runs/{id}/summary`、`WS /runs/{id}/updates`。

`ReplayService`从最近`WorldMemento`开始，按seq应用已保存的领域事件；不重新进行规则决策或模型推理。所有影响世界的变化必须记录足够重放的信息，包括动作参数、对话文本、资源变化、随机选择的最终结果。建议每100个事件或每60仿真秒产生快照。回放中的角色详情只展示当时已发生的认知记录，避免把未来记忆泄漏进过去。

本期采用“当前状态＋完整领域事件记录＋Outbox＋快照”，不扩展到全系统事件溯源、CQRS基础设施或历史分支。只读回放恢复的是历史世界视图，不恢复模型内部状态。

### 3.10 开源借鉴与原创工作

| 来源 | 借鉴 | 本项目自行完成 |
| --- | --- | --- |
| Stanford Generative Agents | 记忆、检索、计划的组织方式 | 精简角色机制、事件感知和约束执行 |
| AI Town | 世界/引擎/智能体/前端分层，异步认知思路 | PostgreSQL/Redis Streams协作、幂等、暂停语义与回放 |

AI Town采用tick模型和Convex，本项目借鉴分层和异步认知，自行实现事件协作与可靠性。[AI Town架构文档](https://github.com/a16z-infra/ai-town/blob/main/ARCHITECTURE.md)

建立第三方来源清单，记录复用代码/素材路径、版本和许可证。仓库代码许可证不能自动覆盖所有美术素材；地图优先自绘简单图形。

### 3.11 UML与GoF实现约定

本节用UML和GoF将3.2的职责落实为类、接口和协作约定，供组员实现与联调。

UML图使用PlantUML保存图源，模式名称采用GoF目录。

#### 3.11.1 阅读顺序、图例与追踪关系

按用例→组件→类与状态→时序图阅读。[图源与生成说明](uml-v2/README.md)提供9张PNG及`.puml`文件；`<<Command>>`等为项目标签，不是额外UML Profile。

类图：实线/虚线空心三角分别表示继承/接口实现，虚线箭头表示依赖，实线箭头表示关联，实心菱形表示组合；`1`、`0..1`、`0..*`表示数量约束。

| UML视图 | 回答的问题 | 对应需求/原章节 | 主责与使用时机 |
| --- | --- | --- | --- |
| U01 用例图 | 谁通过系统完成什么任务？ | F01—F10；第2节 | C主责，W1确认产品边界 |
| U02 组件图 | 原架构图的节点对应哪些软件组件？ | 3.1、3.2、3.8 | A主责，W1约定依赖方向 |
| U03 命令/世界/状态类图 | 谁接收命令，谁执行，谁允许改世界？ | F03、F04；3.3、3.5、3.6 | A主责，W1—W2建立接口 |
| U04 认知类图 | 谁感知事件、选择算法、接入模型？ | F06、F10；3.7 | B主责，W2—W3实现 |
| U05 运行状态图 | 暂停、恢复、停止时什么行为允许执行？ | F03；3.6 | A与C共同审阅，W2实现 |
| U06a 命令生效时序图 | 命令何时真正生效，事件何时发布？ | F04、F07；3.4、3.5 | A/B/C共同联调，W2 |
| U06b 认知与行动时序图 | 模型等待与世界状态变化如何协调？ | F05、F06、F10 | B主责，A审查，W3—W4 |
| U07 快照类图 | 如何封装状态并只读还原历史？ | F08；3.9 | A主责，W5 |
| U08 部署图 | 组件放在哪个进程，哪些资源共享？ | 3.1、3.8；部署验收 | B主责，W1建立、W7复核 |

#### 3.11.2 用例与组件视图

![U01 用例图](uml-v2/rendered/U01-use-cases.png)

U01沿用2.1的使用角色；`include`表示每次必执行的子用例。“查看行为依据”可直接进入。

![U02 组件图](uml-v2/rendered/U02-components.png)

U02使用3.2定义的组件名称与职责，进程分组见U08。数据节点分开绘制仅表示数据职责，`commands`、世界状态、`events`和`outbox`属于同一个PostgreSQL实例。

#### 3.11.3 GoF应用总表

组件职责以3.2为准。本表定义模式角色与扩展点；共享接口的小类可放在同一文件。

| 模式 / 类型 | GoF角色与组件 | 实现与扩展约定 |
| --- | --- | --- |
| Command / 行为型 | Client=`SimulationFacade`、`DecisionService`；Invoker=`CommandProcessor`；Command=`WorldCommand`；ConcreteCommand=`PublishNoticeCommand/CloseLocationCommand/ProposeActionCommand`；Receiver=`World` | 用户命令与行动提案统一排队和执行。新增命令时补充契约、解码注册及测试；复用3.4的事务流程 |
| Observer / 行为型 | Subject=`EventHub`；Observer=`EventObserver`；ConcreteObserver=`CognitionObserver/RealtimeObserver` | 按事件类型注册观察者；跨进程分发使用Redis Streams消费组，可靠性遵循3.5 |
| Strategy / 行为型 | Context=`DecisionService`；Strategy=`DecisionStrategy`；ConcreteStrategy=`LLMDecisionStrategy/RuleDecisionStrategy` | 替换决策算法，统一返回`ActionProposal`；失败切换记录来源与原因，提案仍由`World`校验 |
| State / 行为型 | Context=`World`；State=`RunState`；ConcreteState=`DraftState/ReadyState/RunningState/PausedState/FinishedState/FailedState` | 状态对象控制授权、迁移与时钟；运行规则见3.6及U05，实例与数据库状态码保持一致 |
| Adapter / 结构型 | Client=`LLMDecisionStrategy`；Target=`ModelGateway`；Adapter=`ProviderAdapter`；Adaptee=供应商SDK/HTTP客户端 | 更换供应商时保留`generate(ModelRequest)`接口，仅转换协议、异常与用量 |
| Facade / 结构型 | Facade=`SimulationFacade`；子系统=`CommandInbox/ReadService/ReplayService` | 保持前端提交与查询入口稳定；`submit()`保存命令后返回回执，不同步执行世界动作或模型请求 |
| Memento / 行为型 | Originator=`World`；Memento=`WorldMemento`；Caretaker=`SnapshotStore/ReplayService` | `World`封装、导出及还原状态，存储组件只保管；按3.11.7隔离回放 |

UML用于表达结构和交互，GoF用于约定对象协作。Outbox、Repository、UnitOfWork和跨进程发布订阅属于其他设计机制。注册表不称为Factory Method，单Runtime部署不称为Singleton；命令表、状态枚举、Redis和JSON备份各自都不足以构成完整GoF模式。[UML规范](https://www.omg.org/spec/UML/2.5.1/About-UML)、[GoF原书](https://www.informit.com/store/design-patterns-elements-of-reusable-object-oriented-9780321770462)

#### 3.11.4 命令与状态类图

![U03 命令与世界类图](uml-v2/rendered/U03-command-world.png)

`CommandProcessor`通过`CommandCodec`解码已保存的`CommandEnvelope`，再调用`WorldCommand.execute(world)`，执行顺序见3.4。命令对象不持有数据库Session、Redis连接或模型客户端；只保存白名单JSON，禁止pickle和按请求类名动态导入。

`World`返回`EventDraft`，由`CommandProcessor`在持锁事务中补全事件信封。领域拒绝保存原因并提交；数据库异常等技术失败回滚后有限重试。本期不实现历史Undo；一个`World`对应一次运行。

![U05 运行状态图](uml-v2/rendered/U05-run-state.png)

| 当前状态 | 控制命令 | 新注入事件/到期动作 | 已返回行动提案 | 仿真时钟 |
| --- | --- | --- | --- | --- |
| DRAFT | 校验配置到READY | 拒绝 | 拒绝 | 停止 |
| READY | 启动到RUNNING | 拒绝 | 拒绝 | 停止 |
| RUNNING | 暂停到PAUSED；停止到FINISHED | 校验后执行 | 校验后执行或拒绝 | 推进 |
| PAUSED | 继续到RUNNING；停止到FINISHED | 新注入拒绝；到期动作保留 | `DEFER`，继续后重新校验 | 冻结 |
| FINISHED/FAILED | 查询/回放；不接受新世界控制 | 拒绝 | 拒绝/失效 | 停止 |

控制命令优先，避免被DEFER提案阻塞。相同request_id返回原回执；不同request_id的重复控制操作根据当前状态返回幂等无变化或拒绝，不重复产生效果。

`RunState.classify(kind)`决定处理方式，`transition(kind)`返回目标状态，`can_advance()`决定时钟是否推进。数据库存状态码，加载时映射为状态对象；状态迁移与`World`一起提交，失败不更新进程缓存。恢复和run_epoch规则见3.6；终止性失败同样递增run_epoch。

#### 3.11.5 认知、决策与模型类图

![U04 认知与模型类图](uml-v2/rendered/U04-cognition.png)

API和Cognition进程各自持有`EventHub`，通过`EventObserver.on_event(event)`通知本地对象；进程间由Redis Streams分发。同一消费组内的观察者按`observer_id`去重，必要处理全部成功后才ACK。`CognitionObserver`将去重记录、观察记忆和决策任务放在同一事务；`DecisionService`独立领取任务，模型调用不占用消费事务。

`DecisionService`向`DecisionStrategy`传入`DecisionContext`。两种策略返回相同的`ActionProposal`；模型失败或预算不足时选择`RuleDecisionStrategy`，记录`source=rule`与原因，不能以空结果代替降级。

`LLMDecisionStrategy`负责提示词、提案解析与格式校验；`ModelGateway`定义统一请求/响应，`ProviderAdapter`转换供应商协议、异常和用量；`World`校验行动合法性。WebSocket发送不与数据库提交构成原子事务，Web工作台断线或遗漏通知后主动同步状态并按seq补拉。

Python接口使用`Protocol`，不可变消息使用`dataclass(frozen=True)`，必要时使用`ABC`；输入仍需Pydantic运行时校验。[Python Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol)

#### 3.11.6 时序图：陈宇收到通知后前往活动室

陈宇在教学楼收到全体活动通知，决定前往活动室。两张图通过`event_id/correlation_id`关联，具体步骤遵循3.4。

![U06a 通知生效时序](uml-v2/rendered/U06a-notice-sequence.png)

U06a区分命令保存、世界事务提交和异步发布三个时点：保存后返回202，提交后生效，随后由`OutboxDispatcher`分发。

![U06b 认知与行动时序](uml-v2/rendered/U06b-decision-sequence.png)

U06b展示`CognitionObserver → DecisionService → DecisionStrategy → ModelGateway → ProviderAdapter`生成提案，再以`ProposeActionCommand`进入`CommandProcessor → World`。到达时间由`Scheduler`检查并提交`CompleteActionCommand`，通过相同事务边界生成`AgentArrived`。

暂停、过期与模型失败分支分别遵循3.6、3.5和3.7；模型等待不持有世界数据库锁。提案使用角色计划及相关资源版本，不能因为无关世界变化失效。任务重试可能重复计费；唯一结果与命令键只防止世界效果重复。

#### 3.11.7 快照与回放类图

![U07 快照与回放类图](uml-v2/rendered/U07-memento.png)

`World.create_memento()`导出`WorldMemento`，封装状态及run_id、seq、sim_time、schema_version、hash。`SnapshotStore`只保存和读取；`World.from_memento()`校验版本与完整性，创建脱离生产仓储的只读`World`。

`ReplayService`读取最近快照，通过`World.apply_event()`顺序应用后续历史事件，并按指定仿真时间插值。角色详情按时间/seq截断，避免读取未来记忆。可重放数据与快照频率见3.9。

回放对象不持有生产`World`仓储的写入引用，接口不暴露submit/execute；不调用`WorldCommand.execute()`、`DecisionStrategy`或`ModelGateway`。Memento负责封装快照，事件序列补齐快照后的历史；本期不恢复可继续推理的历史分支。

#### 3.11.8 部署视图与建议代码目录

![U08 部署图](uml-v2/rendered/U08-deployment.png)

MVP部署保持6个Compose服务：frontend、api、runtime、cognition、postgres、redis。OutboxDispatcher放Runtime进程；ReplayService放API进程；`ProviderAdapter`放Cognition进程。外部模型服务不计入本地容器。组件可拆分不等于本期必须拆进程。

```text
backend/app/
  api/                     # FastAPI路由、WebSocket、传输DTO
  application/
    simulation_facade.py   # Facade：提交与查询入口
    command_processor.py   # Command的Invoker；事务边界
    decision_service.py    # Strategy的Context；回退选择
    replay_service.py      # Memento的Caretaker；只读重放
  domain/
    world.py               # Command的Receiver；Memento的Originator
    commands.py            # WorldCommand与具体命令
    events.py              # 不可变领域事件
    run_states.py          # State接口及状态对象
    decisions.py           # DecisionContext / ActionProposal
    strategies.py          # 决策接口及规则策略
    memento.py             # WorldMemento，封装状态
  cognition/
    observers.py           # CognitionObserver
    perception.py          # 感知范围
    memory.py              # 记忆与检索
    llm_strategy.py        # LLMDecisionStrategy
  ports/
    model_gateway.py       # Adapter目标接口
    repositories.py        # 数据/消息端口
  infrastructure/
    postgres/              # SQLAlchemy、仓储、UnitOfWork、CommandCodec
    redis/                 # RedisStreamTransport、EventHub
    providers/             # ProviderAdapter与测试替身
    realtime.py            # RealtimeObserver
  workers/
    runtime.py             # 调度和命令执行入口
    outbox.py              # OutboxDispatcher异步循环
    cognition.py           # 消费事件、领取认知任务
  bootstrap.py             # 装配对象、注册命令/观察者，管理连接生命周期
```

依赖方向：domain不导入FastAPI、SQLAlchemy、Redis或供应商SDK；application依赖领域对象与端口；infrastructure实现端口；bootstrap把具体实现注入应用服务。处理器在事务内可以调用领域对象，但领域对象不能反向开启数据库事务。

#### 3.11.9 给组员的接口与执行约定

[参考接口文件](uml-v2/reference_interfaces.py)展示名称、类型与协作关系，只用于设计讨论和起步，不含数据库/网络实现，不是可运行后端。

| 契约 | 方法形状 | 关键后置条件 |
| --- | --- | --- |
| `SimulationFacade` | `submit(envelope) -> CommandReceipt` | 唯一请求已保存；不代表世界已改变 |
| `WorldCommand` | `execute(world) -> tuple[EventDraft, ...]` | 只调用World；由CommandProcessor补全事件信封，不得包含网络I/O |
| `CommandProcessor` | `process_next(run_id) -> ProcessResult` | 状态、事件、Outbox、命令结果原子提交；DEFER不阻挡控制命令 |
| `RunState` | `classify(kind)`、`transition(kind)`、`can_advance()` | 对同一输入返回明确授权、迁移与时钟语义 |
| `EventObserver` | `on_event(event)` | 消费副作用按观察者去重；不写权威世界 |
| `DecisionStrategy` | `async decide(context) -> ActionProposal` | 所有策略返回相同动作契约并标明来源 |
| `ModelGateway` | `async generate(request) -> ModelResponse` | 供应商响应归一化；提案仍需策略解析和世界校验 |
| `World` | `create_memento()`、`from_memento()`、`apply_event()` | 回放只还原已保存结果，脱离生产写入链 |

命令处理伪代码（事务方法名表达意图，具体ORM实现由A/B对齐）：

```python
def process_next(run_id):
    with unit_of_work() as tx:
        run = tx.runs.lock(run_id)       # 持锁后再读命令，避免过期缓存
        record = tx.commands.next_eligible(run_id, control_first=True)
        if record is None:
            return IDLE
        if record.is_final:             # 已执行或已拒绝，复用结果
            return record.result
        world = tx.worlds.load(run)
        cmd = codec.decode(record.envelope)
        disposition = world.state.classify(cmd.kind)
        if disposition == DEFER:
            tx.commands.defer(record)  # 继续/停止必须仍可被下一轮选中
            tx.commit()
            return DEFERRED
        if disposition == REJECT:
            events = world.record_rejection(cmd, "run_state")
            result = REJECTED
        else:
            outcome = world.validate(cmd)  # 失败是领域结果，不靠外层异常吞掉
            if not outcome.allowed:
                events = world.record_rejection(cmd, outcome.reason)
                result = REJECTED
            else:
                events = cmd.execute(world)  # Command -> Receiver
                result = APPLIED
        tx.worlds.save(world)
        events = tx.events.append_with_seq(run_id, events)
        tx.outbox.add(events)
        tx.commands.finish(record, result)
        tx.commit()                    # 事务外再分发；异常自动回滚
```

所有世界变化，包括Scheduler生成的到期动作与状态控制，都必须通过同一命令/事务边界；不得由定时器、观察者、`ProviderAdapter`或WebSocket直接更新角色状态。参考代码中省略的业务拒绝、任务领取、事务回滚、取消和恢复逻辑，在对应实现周补齐，不能因为有UML图就视为已完成。

#### 3.11.10 实现顺序与模式验收

人员职责见5.1，逐周交付见5.2，UML图主责见3.11.1。模式实现纳入既有八周计划：W2完成`SimulationFacade`、`WorldCommand`、`RunState`及`EventObserver`闭环；W3完成`DecisionStrategy`与`ProviderAdapter`；W4验证时序图；W5完成`WorldMemento`及`ReplayService`。

模式按以下行为验收：

- 新增`EventObserver`实现无需修改`World`。
- 替换`ProviderAdapter`无需修改`DecisionService`；切换`DecisionStrategy`无需修改`CommandProcessor`。
- `PausedState`阻止提案执行；新增`WorldCommand`复用既有事务处理。
- `ReplayService`还原历史时不调用决策、模型或生产状态写入。

需求、事件契约、UML图、参考接口与实际代码采用相同名称。变更时在同一PR中更新相关图源、预览、接口版本和测试。

## 4. 产品交互原型设计

此处为低保真设计规格，配套PNG是静态线框图，尚未实现可点击应用或后端服务。

### 4.1 信息架构与页面

| 页面 | 核心内容 | 首要操作 |
| --- | --- | --- |
| P01 仿真实验列表 | 模板、新建入口、已有运行、状态、最近时间、空态 | 新建 / 继续观察 / 回放 |
| P02 创建与配置 | 名称→8名角色→活动与调用上限；模型连接检查；默认模板 | 保存草稿 / 创建运行 |
| P03 运行工作台 | 顶部运行控制；左侧角色列表；中央地图；右侧角色/地点详情；底部事件时间线 | 暂停 / 注入事件 / 选择角色 |
| P04 事件注入弹窗 | 模板、目标、范围、内容/参数、校验提示 | 提交命令并跟踪结果 |
| P05 历史与摘要 | 只读地图、时间轴、事件详情、结果统计、导出 | 拖动回放 / 查看原因 / 导出 |

运行工作台线框图：[prototype/workbench.png](prototype/workbench.png)。配置、事件注入、回放线框图：[prototype/journey.png](prototype/journey.png)。

### 4.2 工作台布局

```text
┌ 实验名 / 运行状态 / 仿真时间 ───── 暂停  注入事件  停止 ┐
│ 角色列表       │ 二维校园地图                 │ 角色详情 │
│ 搜索/状态      │ 5个地点、路线、角色          │ 目标/行动 │
│ 学生/组织者    │ 点击角色定位并打开详情       │ 已知信息  │
│ 教师           │ 点击地点查看开放状态         │ 相关记忆  │
│                │                              │ 决策依据  │
├ 事件时间线：角色筛选 / 类型筛选 / 点击查看前因后果 ──────┤
└ 运行概况：活动参与、模型调用、异常与降级                ┘
```

主界面使用“发布通知”“场地关闭”“当前行动”等用户语言。技术ID、消费重试等内容放在“技术详情”折叠区。角色面板提供：概况、记忆、决策记录三项切换。

### 4.3 三条关键交互

**流程A：创建并启动。**选择模板→填名称→检查角色与地点→设调用上限→创建→READY工作台→点击启动→RUNNING。模型检查失败时提供重试或明确选择规则模式；不把调用失败伪装成模型成功。

**流程B：干预并解释。**点击注入事件→选择“场地关闭”→选活动室→填原因→提交→显示已接收→等待已生效→地图更新关闭状态→选择受影响角色→查看“原行动中断/新计划”→点击原因跳转关闭事件。若规则拒绝，弹窗保留输入并给出原因；双击提交不生成两条命令。

**流程C：停止与回放。**点击停止→确认后进入结束摘要→打开回放→拖动时间轴→按事件步进→选择角色查看当时的目标和已知信息→退出回放回到摘要。历史查看与当前运行状态使用独立视图状态，不相互覆盖。

### 4.4 交互状态规范

| 状态 | 界面行为 |
| --- | --- |
| 加载 | 骨架与明确加载区域；避免空白地图被误认为无人 |
| 运行 | 显示仿真时间、可暂停与干预；模型等待显示“正在决策”，其他角色继续运行 |
| 暂停请求中 | 按钮显示处理中；收到RunPaused再显示已暂停 |
| 已暂停 | 地图与仿真时间冻结；继续/停止可用，注入事件禁用并解释原因 |
| 断线 | 显示重连；禁用操作按钮，连接恢复后重取状态并按seq补拉 |
| 模型故障 | “本角色暂用规则行动”；提供运行级故障摘要，页面仍可操作 |
| 预算耗尽 | 明确显示规则模式；已预留请求按规则收尾，不继续分配新额度 |
| 空结果 | 说明尚无事件/记忆/历史，并给出启动或选择角色的下一步 |
| 回放 | 显著“历史回放”标识；禁用世界控制，只保留播放、拖动、步进 |

### 4.5 原型走查标准

找至少2名未参与开发的同学，分别完成创建、干预、定位行为原因、回放四项任务。记录完成与失败原因；每项不超过2次口头提示，优先修复阻断任务的问题。第2周走查静态原型，第6周走查真实应用。

## 5. 开发迭代计划

### 5.1 人员职责

| 成员 | 主责 | 必须共同承担 |
| --- | --- | --- |
| A：架构与运行负责人 | `World`、`CommandProcessor`、`Scheduler`、`RunState`、`ReplayService`；事件契约与PostgreSQL事务 | 与B共审并发/幂等；与C联调状态接口 |
| B：认知与可靠性负责人 | `CognitionObserver`、`PerceptionService`、`MemoryService`、`DecisionService`、`ProviderAdapter`、`OutboxDispatcher`；故障恢复 | 真实服务验证、集成测试、部署 |
| C：产品与前端负责人 | Web工作台；`SimulationFacade`公开DTO与API联调；配置、地图、时间线、历史、摘要 | E2E、可用性走查、演示材料 |

关键组件由至少一名非作者审阅；每周合并可运行版本，三人共同承担测试、文档和部署。

### 5.2 八周迭代与验收门槛

| 周 | A：World / CommandProcessor / ReplayService | B：CognitionObserver / DecisionService / OutboxDispatcher | C：产品/前端 | 当周必须演示的结果 |
| --- | --- | --- | --- | --- |
| W1 范围与技术骨架 | 场景规则、数据模型、事件v1、状态机、API契约；PostgreSQL迁移 | Compose；Streams往返；真实模型最小调用＋FakeModelGateway | 完成需求、静态线框图、列表/配置/工作台骨架 | Web工作台提交命令→CommandInbox保存→CommandProcessor调用World→OutboxDispatcher分发→页面显示；三人能启动环境 |
| W2 规则闭环 | World的5地点/8角色移动；Scheduler动作完成；RunState运行控制 | OutboxDispatcher发布、EventObserver消费去重、任务Schema、结构化日志 | 配置保存、地图、角色选择、控制反馈；原型走查 | 不用模型完成新建→运行→暂停→继续→停止；重启后能看到记录 |
| W3 智能体最小版 | 行动校验、角色占用、epoch/计划版本防护 | 观察范围、记忆Top-K、`LLMDecisionStrategy`决策、并发/超时/预算、规则降级 | 角色概况/记忆/决策面板、模型状态 | 8角色中有真实模型驱动的合法行为；模拟超时后仍能继续；无全知信息泄漏 |
| W4 场景联动 | 通知、地点关闭、活动时间变更、对话与参与规则 | 受影响角色筛选、对话调用上限、事件合并、pending回收 | 注入弹窗、已接收/生效反馈、事件筛选、因果跳转 | “通知→交流→关闭→重规划”闭环；重复注入不重复生效；提交后旧提案不能进入关闭场地 |
| W5 历史与恢复 | WorldMemento、World.apply_event()、ReplayService按seq回放、恢复为暂停 | 故障重试/失败记录、进程崩溃与Redis中断验证 | 历史列表、回放时间轴、按事件步进、摘要初版 | 历史回放零模型调用；快照hash一致；杀进程后未确认消息可恢复且无重复效果 |
| W6 产品完成 | 补齐边界规则和数据导出 | 调用量/延迟/积压指标、真实模型成本校准 | 加载/空态/错误/重连/结束页、导出、可用性走查 | P0全功能可用；E2E四条主流程通过；进入功能冻结 |
| W7 验收与修复 | 集成/一致性/回放用例、修复高优先缺陷 | 30分钟规则运行＋真实模型实验、故障注入、部署复核 | 页面验收、跨页面回归、操作手册和演示脚本 | 无阻断/严重缺陷；所有目标有记录，未达项有测量结果和调整决定 |
| W8 交付与答辩 | C4/模块图、状态机、ADR、数据模型、最终标签 | 干净环境部署、备份说明、离线规则方案、来源清单 | 答辩材料、演示录屏、最终交互检查 | 新环境完成部署与完整演示；提交代码、文档、测试报告、录屏与已知限制 |

关键路径：命令/事件契约→规则行为→异步提案→事件干预→历史回放→端到端验收。W1验证真实模型接口和额度，W2起保留规则模式。

若2026-11-02开工，W1为11月2—8日，W8为12月21—27日；实际开工不同时按周平移。

### 5.3 工作节奏与变更控制

- 每周一确定可演示目标，每周中至少一次短联调，每周末验收并更新风险。
- 需求、接口和事件Schema先评审再并行实现。接口示例放入仓库，前端用Fake数据也须符合相同契约。
- 主分支保持可运行；短分支PR，包含行为变化、验证结果和必要迁移。数据库迁移纳入CI检查。
- 第6周结束冻结P0范围；第7—8周只修复问题和完善交付。新增功能必须替换等量已有工作，不能直接叠加。
- 架构决策记录至少包括：模块化单体、单一世界写入、PostgreSQL＋Redis Streams、至少一次投递、时间与暂停语义、历史回放边界。

### 5.4 必须验证的核心用例

| 用例 | 通过条件 |
| --- | --- |
| UnitOfWork原子性 | 世界状态、events、outbox和命令结果一起提交或回滚；提交后OutboxDispatcher重启可继续发布 |
| 重复消费 | 发布后未标记/处理后未ACK两种崩溃均不重复产生世界效果 |
| 迟到决策 | 目标关闭、计划过期、run已停止时拒绝旧提案，并记录原因 |
| 暂停中模型返回 | PAUSED期间世界与sim_time不变，继续后才重新校验应用 |
| 信息边界 | 非公告接收者且不在现场的角色上下文中不出现关闭事实 |
| 资源与对话 | 同一角色不能同时移动与对话；关闭中断行动且不会困在不可用位置 |
| 故障与预算 | 超时/无效JSON/额度耗尽时切换RuleDecisionStrategy，界面明确显示，预算不因重试无限突破 |
| 重连与缺口 | 页面断线后恢复到权威状态，无重复事件、无遗漏导致的旧视图 |
| 历史重放 | 存储快照与重放状态hash一致；角色面板不读取未来记忆；回放期间模型调用数为零 |
| 完整用户流程 | 创建启动、事件干预、定位原因、结束回放四条E2E通过 |

### 5.5 风险与范围裁剪

| 风险/触发点 | 处理与裁剪 |
| --- | --- |
| W2仍没有规则闭环 | 停止地图美化与P1，保持8角色；简化日程和对话文案，优先打通状态流 |
| W3真实模型延迟或成本过高 | 合并触发、减少对话轮次和调用频率；保留8角色，关键决策用模型、日常行动用规则 |
| W4后可靠性进度不足 | 不加新事件类型，不扩角色；优先完成幂等、过期校验与回放 |
| 人员有效工时低于预期 | 先删P1、关系图和记忆摘要；再将自由角色编辑收为有限字段；不删控制/干预/解释/回放闭环 |
| 涌现行为不明显 | 保留主场景，改进角色目标和信息可见性；不硬编码全部参与，不把效果失败藏成模型成功 |
| 演示时网络/服务不可用 | 清楚标记规则模式并展示已保存真实运行回放；提前录屏，不声称回放是实时生成 |

## 6. 交付清单与答辩设计

最终交付：源码与锁文件、Compose配置与迁移、初始场景、`.env.example`、README、需求与原型、架构图与ADR、事件/API契约、数据模型、测试报告、性能/调用量记录、运行手册、演示录屏、第三方来源与已知限制。

建议8分钟演示：1分钟说明问题和架构→1分钟从模板启动→2分钟发布通知并关闭地点→1分钟查看一个角色的已知信息与重规划依据→1分钟演示重复/失败处理→1分钟回放与摘要→1分钟说明设计取舍。真实生成结果可变化，架构与控制行为必须稳定。

## 7. 参考资料

以下为已核对的原始资料；本规划中的范围、架构组合、工作量和验收阈值是针对三人八周的设计建议。

- [Generative Agents论文](https://arxiv.org/abs/2304.03442)
- [Stanford Generative Agents官方代码](https://github.com/joonspk-research/generative_agents)
- [AI Town架构文档](https://github.com/a16z-infra/ai-town/blob/main/ARCHITECTURE.md)
- [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/)
- [Redis XREADGROUP](https://redis.io/docs/latest/commands/xreadgroup/)
- [Redis XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/)
- [PostgreSQL显式锁](https://www.postgresql.org/docs/current/explicit-locking.html)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)
- [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Pydantic模型](https://docs.pydantic.dev/latest/concepts/models/)
- [Vite](https://vite.dev/guide/)
- [Docker Compose](https://docs.docker.com/compose/)
- [Playwright](https://playwright.dev/docs/intro)


### v2新增设计参考

- [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/About-UML)
- [GoF原书与模式目录](https://www.informit.com/store/design-patterns-elements-of-reusable-object-oriented-9780321770462)
- [PlantUML类图](https://plantuml.com/class-diagram)
- [PlantUML时序图](https://plantuml.com/sequence-diagram)
- [Python Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol)
