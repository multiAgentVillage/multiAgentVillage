"""Editorial revision of v2: preserve design contracts and archive the baseline."""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
PLAN = ROOT.parent / 'project-plan-v2.md'


def replace_section(text, heading, next_heading, body):
    start, end = text.index(heading), text.index(next_heading)
    return text[:start] + body.strip() + '\n\n' + text[end:]


def main():
    old = PLAN.read_text(encoding='utf-8')
    assert '版本：v2.0' in old, 'This editorial migration applies once to v2.0.'
    baseline = ROOT / 'revisions' / 'project-plan-v2.0-before-terminology.txt'
    baseline.parent.mkdir(exist_ok=True)
    if baseline.exists():
        assert baseline.read_text(encoding='utf-8') == old
    else:
        baseline.write_text(old, encoding='utf-8')
    s = old.replace('版本：v2.0 · 2026-11-03', '版本：v2.1 · 2026-11-04', 1)
    s = re.sub(r'修订说明：.*?\n\n',
        '修订说明：统一采用UML图和GoF表中的组件、类与接口名称，合并重复职责说明；产品范围、调用顺序、事务边界、状态规则和验收要求沿用v2.0。术语见3.2，UML及模式实现见3.11。\n\n', s, count=1)

    s = replace_section(s, '### 3.1 ', '### 3.2 ', '''### 3.1 架构决策

采用**模块化单体代码库＋异步任务＋持久化事件分发**。后端共用领域模型和数据库迁移，按API、Runtime、Cognition三种进程角色启动，支持三人并行开发与异步任务隔离。

全文以3.2和GoF表中的名称指代组件；API、Runtime、Cognition仅表示UML组件分组和进程角色。技术名称（如PostgreSQL）与数据表名（如`commands`）按原名使用。用户界面的“角色、当前行动、记忆、回放”等词保持面向使用者。

```mermaid
flowchart LR
    Web[Web工作台] -->|REST| API[FastAPI路由 / SimulationFacade]
    API --> Inbox[(CommandInbox / commands)]
    Inbox --> Processor[CommandProcessor / Scheduler]
    Processor -->|执行命令| World[World / RunState]
    World -->|EventDraft| Processor
    Processor -->|同一事务| PG[(PostgreSQL：世界状态 / events / outbox)]
    PG --> Dispatcher[OutboxDispatcher]
    Dispatcher --> Redis[Redis Streams / RedisStreamTransport]
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
''')

    s = replace_section(s, '### 3.2 ', '### 3.3 ', '''### 3.2 组件职责与边界

本表统一定义组件名称；3.11的GoF表说明相同组件的模式角色。类名使用代码标识符，不再另设Experiment、Eventing、Read/Replay等模块别名。

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

关联日志、耗时、积压、调用量与降级记录属于上述组件的共同要求，不再单列Observability模块；日志不记录API密钥或无关敏感配置。

**写入规则：**`CommandProcessor`通过`World`修改权威世界状态，并用`UnitOfWork`提交；`CognitionObserver`和`DecisionService`仅保存各自的记忆、任务、结果与提案命令。
''')

    s = replace_section(s, '### 3.4 ', '### 3.5 ', '''### 3.4 完整调用流程

以“关闭活动室”为例，流程中的名称与UML类图、GoF表一致：

1. FastAPI路由校验请求格式，`SimulationFacade`通过`CommandInbox`保存`CommandEnvelope`并返回`command_id`，页面显示“已接收”。
2. `CommandProcessor`在短事务中锁定run行、读取命令，通过`CommandCodec`得到`CloseLocationCommand`，加载`World`并由`RunState`决定执行、暂存或拒绝。
3. `WorldCommand.execute(world)`调用`World`领域方法。`World`校验约束、修改内存状态并返回`EventDraft`；`CommandProcessor`分配事件ID和seq，使用`UnitOfWork`一起保存世界状态、`DomainEvent`、Outbox和命令结果，再提交。此时事件才“已生效”。
4. `OutboxDispatcher`发布事件到Redis Streams，成功后标记发送结果；标记失败可能重复发布，由消费者去重。
5. 认知消费组通过`EventHub`调用`CognitionObserver`。`PerceptionService`筛选受影响角色，`MemoryService`保存记忆；去重记录、观察记忆和决策任务提交后才ACK。其他角色不会自动获知关闭事实。
6. `DecisionService`独立领取任务，选择`LLMDecisionStrategy`或`RuleDecisionStrategy`。前者经`ModelGateway`调用`ProviderAdapter`；保存结构化`ActionProposal`、决策摘要和引用记忆，并写入`ProposeActionCommand`。
7. `CommandProcessor`再次加载`World`，校验角色状态、地点开放情况、run_epoch、agent_plan_version、相关资源版本及有效期；合法动作提交并产生事件，无效提案拒绝或触发重规划。
8. 展示消费组通过`EventHub`调用`RealtimeObserver`，向Web工作台发更新提示；工作台通过`ReadService`按seq补拉权威数据。历史回放由`ReplayService`处理。
''')

    s = replace_section(s, '#### 3.11.2 ', '#### 3.11.3 ', '''#### 3.11.2 用例与组件视图

![U01 用例图](uml-v2/rendered/U01-use-cases.png)

U01沿用2.1的使用角色；`include`表示每次必执行的子用例。“查看行为依据”可直接进入。

![U02 组件图](uml-v2/rendered/U02-components.png)

U02使用3.2定义的组件名称与职责，进程分组见U08。数据节点分开绘制仅表示数据职责，`commands`、世界状态、`events`和`outbox`属于同一个PostgreSQL实例。
''')

    s = replace_section(s, '#### 3.11.4 ', '#### 3.11.5 ', '''#### 3.11.4 命令与状态类图

![U03 命令与世界类图](uml-v2/rendered/U03-command-world.png)

按3.4实现`CommandEnvelope → CommandCodec → WorldCommand → CommandProcessor → World`的协作关系：提交与解码是前置准备，`CommandProcessor`才是调用`WorldCommand.execute(world)`的执行者。命令对象不持有数据库Session、Redis连接或模型客户端；只保存白名单JSON，禁止pickle和按请求类名动态导入。

`World`返回`EventDraft`，由`CommandProcessor`在持锁事务中补全事件信封。领域拒绝保存原因并提交；数据库异常等技术失败回滚后有限重试。本期不实现历史Undo。一个`World`对应一次运行的聚合，包含MVP的8名角色和5个地点。

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
''')

    s = replace_section(s, '#### 3.11.6 ', '#### 3.11.7 ', '''#### 3.11.6 时序图：陈宇收到通知后前往活动室

陈宇在教学楼收到全体活动通知，决定前往活动室。两张图通过`event_id/correlation_id`关联，具体步骤遵循3.4。

![U06a 通知生效时序](uml-v2/rendered/U06a-notice-sequence.png)

U06a区分命令保存、世界事务提交和异步发布三个时点：保存后返回202，提交后生效，随后由`OutboxDispatcher`分发。

![U06b 认知与行动时序](uml-v2/rendered/U06b-decision-sequence.png)

U06b展示`CognitionObserver → DecisionService → DecisionStrategy → ModelGateway → ProviderAdapter`生成提案，再以`ProposeActionCommand`进入`CommandProcessor → World`。到达时间由`Scheduler`检查并提交`CompleteActionCommand`，通过相同事务边界生成`AgentArrived`。

暂停、过期与模型失败分支分别遵循3.6、3.5和3.7；模型等待不持有世界数据库锁。提案使用角色计划及相关资源版本，不能因为无关世界变化失效。任务重试可能重复计费；唯一结果与命令键只防止世界效果重复。
''')

    s = replace_section(s, '#### 3.11.7 ', '#### 3.11.8 ', '''#### 3.11.7 快照与回放类图

![U07 快照与回放类图](uml-v2/rendered/U07-memento.png)

`World.create_memento()`导出`WorldMemento`，封装状态及run_id、seq、sim_time、schema_version、hash。`SnapshotStore`只保存和读取；`World.from_memento()`校验版本与完整性，创建脱离生产仓储的只读`World`。

`ReplayService`读取最近快照，通过`World.apply_event()`顺序应用后续历史事件，并按指定仿真时间插值。角色详情按时间/seq截断，避免读取未来记忆。可重放数据与快照频率见3.9。

回放对象不持有生产`World`仓储的写入引用，接口不暴露submit/execute；不调用`WorldCommand.execute()`、`DecisionStrategy`或`ModelGateway`。Memento负责封装快照，事件序列补齐快照后的历史；本期不恢复可继续推理的历史分支。
''')

    s = replace_section(s, '#### 3.11.10 ', '## 4. ', '''#### 3.11.10 实现顺序与模式验收

人员职责见5.1，逐周交付见5.2，UML图主责见3.11.1。模式实现纳入既有八周计划：W2完成`SimulationFacade`、`WorldCommand`、`RunState`及`EventObserver`闭环；W3完成`DecisionStrategy`与`ProviderAdapter`；W4验证时序图；W5完成`WorldMemento`及`ReplayService`。

模式按以下行为验收：

- 新增`EventObserver`实现无需修改`World`。
- 替换`ProviderAdapter`无需修改`DecisionService`；切换`DecisionStrategy`无需修改`CommandProcessor`。
- `PausedState`阻止提案执行；新增`WorldCommand`复用既有事务处理。
- `ReplayService`还原历史时不调用决策、模型或生产状态写入。

需求、事件契约、UML图、参考接口与实际代码采用相同名称。变更时在同一PR中更新相关图源、预览、接口版本和测试。
''')

    # Consistent identifiers in prose; process roles and GoF role names remain distinct.
    replacements = [
        ('Outbox Dispatcher', 'OutboxDispatcher'),
        ('世界引擎', '`World`'), ('认知模块', '`CognitionObserver`与`DecisionService`'),
        ('认知订阅者', '`CognitionObserver`'), ('认知观察者', '`CognitionObserver`'),
        ('展示订阅者', '`RealtimeObserver`'), ('模型适配器', '`ProviderAdapter`'),
        ('本地Hub', '本地`EventHub`'), ('单Dispatcher', '单个`OutboxDispatcher`'),
        ('Dispatcher', 'OutboxDispatcher'), ('FakeProvider', 'FakeModelGateway'),
        ('模型Adapter', '`ProviderAdapter`'), ('模型决策', '`LLMDecisionStrategy`决策'),
        ('模型策略', '`LLMDecisionStrategy`'), ('规则策略', '`RuleDecisionStrategy`'),
        ('命令执行器', '`CommandProcessor`'),
        ('| A：架构与引擎负责人 | 事件契约、世界规则、调度、PG事务、回放 |',
         '| A：架构与运行负责人 | `World`、`CommandProcessor`、`Scheduler`、`RunState`、`ReplayService`；事件契约与PostgreSQL事务 |'),
        ('| B：智能体与可靠性负责人 | 感知、记忆、`ProviderAdapter`、Streams、Outbox、故障恢复 |',
         '| B：认知与可靠性负责人 | `CognitionObserver`、`PerceptionService`、`MemoryService`、`DecisionService`、`ProviderAdapter`、`OutboxDispatcher`；故障恢复 |'),
        ('| C：产品与前端负责人 | 需求/原型、配置、地图、时间线、历史、摘要 |',
         '| C：产品与前端负责人 | Web工作台；`SimulationFacade`公开DTO与API联调；配置、地图、时间线、历史、摘要 |'),
        ('| 周 | A：引擎/架构 | B：认知/消息 |', '| 周 | A：World / CommandProcessor / ReplayService | B：CognitionObserver / DecisionService / OutboxDispatcher |'),
        ('浏览器提交一个命令→落库→引擎产生事件→分发→页面显示',
         'Web工作台提交命令→CommandInbox保存→CommandProcessor调用World→OutboxDispatcher分发→页面显示'),
        ('| W2 规则闭环 | 5地点路线、8角色规则移动、动作完成、运行/暂停/停止 | Outbox发布、消费去重、任务Schema、结构化日志 |',
         '| W2 规则闭环 | World的5地点/8角色移动；Scheduler动作完成；RunState运行控制 | OutboxDispatcher发布、EventObserver消费去重、任务Schema、结构化日志 |'),
        ('| W5 历史与恢复 | 快照、确定性reducer、seq回放、恢复为暂停 |',
         '| W5 历史与恢复 | WorldMemento、World.apply_event()、ReplayService按seq回放、恢复为暂停 |'),
        ('数据库异常等技术失败', '数据库异常等技术失败'),
        ('无效JSON/额度耗尽时降级', '无效JSON/额度耗尽时切换RuleDecisionStrategy'),
        ('| 世界状态与Outbox原子性 | 事务失败时三者一起回滚；提交后OutboxDispatcher重启可继续发 |',
         '| UnitOfWork原子性 | 世界状态、events、outbox和命令结果一起提交或回滚；提交后OutboxDispatcher重启可继续发布 |'),
    ]
    # Do not modify code, data schemas, API paths, directory paths or external links.
    parts = re.split(r'(```[\s\S]*?```)', s)
    for i in range(0, len(parts), 2):
        for a,b in replacements:
            parts[i] = parts[i].replace(a,b)
        parts[i] = parts[i].replace('OutboxOutboxDispatcher', 'OutboxDispatcher')
        parts[i] = re.sub(r'(?<![A-Za-z])Processor(?![A-Za-z])', 'CommandProcessor', parts[i])
        parts[i] = parts[i].replace('``World``', '`World`').replace('``ProviderAdapter``', '`ProviderAdapter`')
    s = ''.join(parts)
    s = s.replace('世界合法性由Runtime负责', '世界合法性由`World`校验')
    s = s.replace('Runtime按运行串行', '`CommandProcessor`按运行串行')
    s = s.replace('Runtime可以每250ms检查到期动作和输入', '`Scheduler`每250ms检查到期动作，`CommandProcessor`读取待处理命令')
    s = s.replace('MVP只运行一个Runtime实例', 'MVP只运行一个Runtime进程')
    s = s.replace('Worker读取任务', '`DecisionService`领取任务')
    s = s.replace('Worker崩溃时', '`DecisionService`所在Worker崩溃时')
    s = s.replace('模型不逐帧控制坐标', '模型不逐帧控制坐标')
    s = s.replace('移动由引擎持续推进', '移动由`Scheduler`调度、`World`更新')
    s = s.replace('→引擎校验执行', '→`World`校验执行')
    s = s.replace('只读回放：从最近快照开始', '`ReplayService`从最近`WorldMemento`开始')
    s = s.replace('### 3.11 UML建模与GoF设计模式落地（v2新增）', '### 3.11 UML与GoF实现约定')
    # The existing implementation pseudocode is an executable-design invariant.
    old_code = re.findall(r'```python\n([\s\S]*?)```', old)
    new_code = re.findall(r'```python\n([\s\S]*?)```', s)
    assert old_code == new_code
    PLAN.write_text(s, encoding='utf-8', newline='\n')
    section = s[s.index('### 3.11 '):s.index('## 4. ')]
    (ROOT/'design-section.md').write_text(section, encoding='utf-8', newline='\n')
    print(f'Characters: {len(old)} -> {len(s)} ({(1-len(s)/len(old))*100:.1f}% shorter)')
    print('Archived baseline:', baseline)
    print('Implementation pseudocode: unchanged')


if __name__ == '__main__':
    main()
