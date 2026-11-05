"""Finish the terminology-only revision; no application code is edited."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PLAN = ROOT.parent / 'project-plan-v2.md'


def section(s, start, end, value):
    a,b=s.index(start),s.index(end)
    return s[:a]+value.strip()+'\n\n'+s[b:]


def main():
    s=PLAN.read_text(encoding='utf-8')
    s=section(s,'#### 3.11.3 ','#### 3.11.4 ','''#### 3.11.3 GoF应用总表

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
''')
    s=section(s,'#### 3.11.5 ','#### 3.11.6 ','''#### 3.11.5 认知、决策与模型类图

![U04 认知与模型类图](uml-v2/rendered/U04-cognition.png)

API和Cognition进程各自持有`EventHub`，通过`EventObserver.on_event(event)`通知本地对象；进程间由Redis Streams分发。同一消费组内的观察者按`observer_id`去重，必要处理全部成功后才ACK。`CognitionObserver`将去重记录、观察记忆和决策任务放在同一事务；`DecisionService`独立领取任务，模型调用不占用消费事务。

`DecisionService`向`DecisionStrategy`传入`DecisionContext`。两种策略返回相同的`ActionProposal`；模型失败或预算不足时选择`RuleDecisionStrategy`，记录`source=rule`与原因，不能以空结果代替降级。

`LLMDecisionStrategy`负责提示词、提案解析与格式校验；`ModelGateway`定义统一请求/响应，`ProviderAdapter`转换供应商协议、异常和用量；`World`校验行动合法性。WebSocket发送不与数据库提交构成原子事务，Web工作台断线或遗漏通知后主动同步状态并按seq补拉。

Python接口使用`Protocol`，不可变消息使用`dataclass(frozen=True)`，必要时使用`ABC`；输入仍需Pydantic运行时校验。[Python Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol)
''')
    # Remove repetition without dropping any requirement or numeric acceptance target.
    edits={
      '生成式智能体可以结合角色设定、经历与当前环境进行交流和决策。斯坦福Generative Agents以记忆、检索、反思和规划组织智能体行为，展示了25个角色组成的小镇。其研究说明这些认知机制有助于形成可信行为，但不能直接保证一个课程项目的运行可靠性或交付完整度。':
      '生成式智能体结合角色设定、记忆与环境进行交流和决策。斯坦福Generative Agents以记忆、检索、反思和规划组织25个角色的小镇，为本项目提供认知机制参考。',
      '本项目解决的工程问题是：多个异步智能体共同生活在一个持续变化的世界里时，怎样协调动作、处理外部干预、解释行为并可靠地保留历史？典型冲突包括：模型回复时场地已经关闭；用户暂停后迟到的动作仍改变世界；消息重试导致同一通知或动作重复执行；模型不可用使整个仿真停住。':
      '本项目协调持续变化的世界与异步决策，重点处理场地变化导致提案过期、暂停后的迟到响应、重复消息和模型不可用，并保留可解释、可回放的历史。',
      'EDA适合把世界变化表达为可订阅的事实，让感知、认知、展示与统计通过事件协作。本项目的价值在于完整实现这个过程，而不是仅为聊天调用增加一层消息队列。':
      'EDA将世界变化记录为事件，驱动感知、决策、展示与统计协作。',
      '本表统一定义组件名称；3.11的GoF表说明相同组件的模式角色。类名使用代码标识符，不再另设Experiment、Eventing、Read/Replay等模块别名。':
      '本表统一定义组件名称与职责；3.11的GoF表使用同名组件说明模式角色。',
      '关联日志、耗时、积压、调用量与降级记录属于上述组件的共同要求，不再单列Observability模块；日志不记录API密钥或无关敏感配置。':
      '各组件共同记录关联日志、耗时、积压、调用量与降级原因；日志不记录API密钥或无关敏感配置。',
      '本节是组员编写代码的设计契约。沿用3.1—3.10的产品范围、技术栈与一致性规则，不增加微服务、角色数量或新的产品功能。以下类名、方法名和目录均为建议的实现约定，尚非已完成的应用代码。':
      '本节用UML和GoF将3.2的职责落实为类、接口和协作约定，供组员实现与联调。',
      'UML是描述系统的建模语言；GoF是面向对象设计模式目录，两者分工不同：UML展示参与者、结构、关系、消息和状态；GoF解释接口与类如何协作、如何隔离变化。本节以OMG UML为建模依据，使用PlantUML保存图源；模式名称采用GoF原书目录。[UML规范](https://www.omg.org/spec/UML/2.5.1/About-UML)、[GoF原书](https://www.informit.com/store/design-patterns-elements-of-reusable-object-oriented-9780321770462)':
      'UML图使用PlantUML保存图源，模式名称采用GoF目录。',
      '先读用例和组件，再读类图、状态机，最后按时序图实现。所有图提供PNG预览和可编辑的`.puml`源文件，见[图源与生成说明](uml-v2/README.md)。图中的`<<Command>>`等标签是本项目的模式标记，不表示采用了额外UML Profile。':
      '按用例→组件→类与状态→时序图阅读。[图源与生成说明](uml-v2/README.md)提供9张PNG及`.puml`文件；`<<Command>>`等为项目标签，不是额外UML Profile。',
      '类图实线空心三角表示继承，虚线空心三角表示接口实现，虚线箭头表示使用依赖，实线箭头表示关联，实心菱形表示整体拥有组成部分。类图中的`1`、`0..1`、`0..*`表达数量约束，不等同于数据库外键或消息投递次数。':
      '类图：实线/虚线空心三角分别表示继承/接口实现，虚线箭头表示依赖，实线箭头表示关联，实心菱形表示组合；`1`、`0..1`、`0..*`表示数量约束。',
      '按3.4实现`CommandEnvelope → CommandCodec → WorldCommand → CommandProcessor → World`的协作关系：提交与解码是前置准备，`CommandProcessor`才是调用`WorldCommand.execute(world)`的执行者。':
      '`CommandProcessor`通过`CommandCodec`解码已保存的`CommandEnvelope`，再调用`WorldCommand.execute(world)`，执行顺序见3.4。',
      '本期不实现历史Undo。一个`World`对应一次运行的聚合，包含MVP的8名角色和5个地点。':
      '本期不实现历史Undo；一个`World`对应一次运行。',
      'FastAPI支持WebSocket；SQLAlchemy异步Session需按并发任务管理；Compose可统一定义多容器环境。这些能力支持选型，但本项目的性能和可靠性仍需实测。':
      '各并发任务独立使用SQLAlchemy Session；部署由Compose统一管理。',
      '所有关键模块至少有一名非作者完成审阅；每周合并一个可运行版本。不把测试留给单独一个人，也不让架构负责人独占全部文档与部署。':
      '关键组件由至少一名非作者审阅；每周合并可运行版本，三人共同承担测试、文档和部署。',
      '关键路径：命令/事件契约→规则世界→异步提案与校验→事件干预→持久化回放→端到端验收。W1即接一次真实模型，避免到W3才发现接口或额度不可用；W2起始终保留规则模式。':
      '关键路径：命令/事件契约→规则行为→异步提案→事件干预→历史回放→端到端验收。W1验证真实模型接口和额度，W2起保留规则模式。',
      'AI Town架构文档明确采用tick模型和Convex；因此本项目不直接继承它作为EDA完成证明，也不在三人八周内同时重构其完整引擎。':
      'AI Town采用tick模型和Convex，本项目借鉴分层和异步认知，自行实现事件协作与可靠性。',
      'PG/Streams协作':'PostgreSQL/Redis Streams协作',
      '真实PG/Redis集成测试':'真实PostgreSQL/Redis集成测试',
      '世界变化保留在PG并积压Outbox':'世界变化保留在PostgreSQL并积压Outbox',
      '按PG游标重新发布':'按PostgreSQL游标重新发布',
      'PG迁移':'PostgreSQL迁移',
      'PG＋Streams':'PostgreSQL＋Redis Streams',
      '一层自建Adapter':'ProviderAdapter',
      '不能在请求中同步调用引擎/模型':'不能在请求中同步执行World或模型请求',
      'Dispatcher先放Runtime进程':'OutboxDispatcher放Runtime进程',
      'OutboxOutboxDispatcher':'OutboxDispatcher',
    }
    for a,b in edits.items():s=s.replace(a,b)
    s=s.replace('    outbox.py              # Dispatcher异步循环','    outbox.py              # OutboxDispatcher异步循环')
    # Preserve the original algorithm verbatim; comments in the directory example are editorial.
    old=(ROOT/'revisions/project-plan-v2.0-before-terminology.txt').read_text(encoding='utf-8')
    assert re.findall(r'```python\n([\s\S]*?)```',old)==re.findall(r'```python\n([\s\S]*?)```',s)
    PLAN.write_text(s,encoding='utf-8',newline='\n')
    (ROOT/'design-section.md').write_text(s[s.index('### 3.11 '):s.index('## 4. ')],encoding='utf-8',newline='\n')
    print('Baseline / revised characters:',len(old),len(s))


if __name__=='__main__':main()
