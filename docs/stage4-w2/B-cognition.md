# B施工计划：规则任务、可靠投递与系统组装

你和你的agent按本页与[统一施工契约](contracts.md)执行，不再向A/C重新定义规则。对应主计划3.2、3.5、3.7、3.11.5和W2的消息/任务/日志交付。为让规则闭环实际运行，本轮启用最小RuleDecisionStrategy；LLM、Top-K与预算仍在W3。

## 1. 你的交付结果

1. 新建稳定观察者`rule-decisions-v1`，复用现有cognition组。严格采用契约第6节事件白名单和角色范围，收据与任务创建/合并一起提交，PG补偿也覆盖这些事件。原通知记忆观察者和收据保持。
2. 实现DecisionService→RuleDecisionStrategy及上下文兼容扩充。规则仅取本角色未完成日程，决定MOVE或WAIT，返回source=rule及简短原因；不理解通知自由文本，不计算路线或写坐标。
3. 实现持久化任务领取、15秒租约、最多3次尝试、1/2秒两次退避，以及契约规定的人工重试维护命令。每角色一个未完成任务，按固定字段合并新刺激，旧claim不得提交；前一提案未最终处理时不领取后续任务。
4. MOVE和WAIT结果均与唯一ProposeAction命令、任务completed状态同事务保存，request_id稳定派生自job_id。使用A的事务内写入器，不能调用自行提交的CommandInbox拼接原子性。
5. 实现仿真时间唤醒：每250ms读取A已保存的计划到期点，按固定wake任务键和真实DecisionRecorded来源创建任务。没有后续日程不空转；暂停不领取或推进唤醒，继续重新读取权威时间。
6. 维护Outbox顺序、两个消费组、ACK后置、pending回收和独立PG补偿。新增世界事件也应进入展示观察者；不把“数据库里有记忆”作为Redis确实消费的证据。
7. 提供DecisionReadService的角色/运行只读摘要；统一完成依赖装配和六服务验收，补跑上一阶段未实际执行的PG回归。

## 2. 架构与文件归属

使用**Observer + Strategy**：观察者消费事实、保存任务，策略提出意图，A的World最终校验执行。你只写记忆、任务、调用/规则结果及输入命令；不追加权威events、不分配seq、不改角色状态或运行时钟。DecisionRecorded由A在提案应用时生成。

你负责`cognition/`、`application/decision_service.py`、`domain/decisions.py`、`domain/strategies.py`、规则任务/观察仓储、Redis传输、OutboxDispatcher及其仓储、Cognition/Outbox/Consumer Worker。你拥有`bootstrap.py`、`workers/base.py`、API lifespan装配、Compose新增环境配置；A拥有runtime.py，C拥有HTTP路由。

三人服务分别从自己的工厂模块导出，你在bootstrap统一接线，不要求其他人再改同一装配文件。保持frontend/api/runtime/cognition/postgres/redis六服务，不增加决策或Outbox容器。

## 3. 固定协作输入与输出

- 使用A的RuleContextReader取得完整纯领域上下文，不把全世界日志塞进visible_facts。新角色ID、日程、路线来自运行快照，不按姓名或旧chen-yu字符串写规则。
- 用A的事务内命令端口保存提案；所有字段、schedule_id、版本、有效期、correlation/causation按契约，不另设ActionProposal格式。
- 给C提供`agent_status`与`run_status`只读摘要，含规则来源、任务阶段、简短原因和失败码。提案未应用时只称“建议/处理中”，不能显示成已经移动。
- 对停止任务做取消，但仍依靠A的epoch校验防止迟到结果生效；暂停期间已算完结果可以持久化，由A暂存提案。

## 4. 必须避免的错误

WAIT不能只写任务结果后跳过World，也不能伪造到达事件。必须先送统一提案链，由World记录规则事实和下次评估时间；未来日程只用仿真时间唤醒，不用墙钟sleep。无后续日程不反复自建任务。

running任务的原始输入版本不被新刺激覆盖；needs_reevaluation必须对应保留的真实事件。租约重试不更换提案request_id。来源事件必须同run且存在，不能虚构启动通知或时钟事件。

不清空原cognition收据，不回填旧演示的历史决策；只在正式W2新建运行验收规则行为。普通日程与移动不得调用模型。

## 5. 交付与验收

第1日按固定上下文制作测试替身并补跑原PG测试；第2—3日完成规则、任务与唤醒；第4日组装真实服务；第5日汇总运行证据。

验证：启动后8名角色分别评估；陈宇日程第5秒到时后只产生一次MOVE，按契约测量调度延迟；无日程角色不空转；重复事件、租约失效与Worker重启不重复行动；暂停冻结、继续后按仿真时间唤醒；终态迟到事件不复活任务，永久拒绝不循环；Redis中断恢复后Outbox及两组pending可恢复。模型调用数为0。

交付任务/消息测试、真实PG/Redis结果、结构化关联日志、六服务及故障恢复证据和`docs/stage4-w2/acceptance-B.md`。单独登记原W1模型连通性预研缺项，不把它混入本轮业务验收。
