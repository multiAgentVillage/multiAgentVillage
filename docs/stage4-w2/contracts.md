# W2统一施工契约（负责人定稿）

这是A/B/C及其agent的共同输入，不是待讨论议题。本文件只指定主计划未细化的施工口径；主计划的单一世界写入、三种时间、至少一次投递、暂停/停止/恢复和信息边界全部保留。

## 1. 当前基线与阶段边界

沿用现有命令/事件信封、字符串ID、FrozenJsonObject、回执、14张表及`0002_core_schema`。现有通知链保留。旧演示配置含操场；禁止修改旧运行快照来迁就新地图。

新建W2实验使用`config.schema_version=2`，事件与命令信封仍为`schema_version=1`。新模板固定5地点、8角色、1活动；地图不可自由编辑。本轮MOVE进入世界执行，WAIT作为“此刻保持空闲”的提案也进入同一执行链，World记录DecisionRecorded，不创建独立计时动作。未来日程由B按仿真时间唤醒。

## 2. 配置、地图与默认数据

统一配置对象包含：`schema_version,name,seed,locations,routes,agents,activities`。默认`seed=7`。

| 对象 | 固定字段 |
| --- | --- |
| location | `location_id,name,position:{x,y},capacity`；capacity可为null |
| route | `route_id,from_location_id,to_location_id,path:[{x,y}],duration_ms,bidirectional` |
| agent | `agent_id,name,biography,interests:[string],goals:[string],initial_location_id,schedule:[schedule_item]` |
| schedule_item | `schedule_id,at_sim_time_ms,target_location_id`；时间非负，按时间及schedule_id排序 |
| activity | `activity_id,name,location_id,starts_at_ms,ends_at_ms`；结束不早于开始 |

默认地点：`dormitory/宿舍(100,300)`、`teaching-building/教学楼(100,100)`、`library/图书馆(350,100)`、`cafeteria/食堂(350,300)`、`activity-room/活动室(600,100)`。坐标用于800×500视图中的显示，不是物理速度单位。

固定双向边，path默认直线端点；教学楼至活动室使用折线`[(100,100),(350,60),(600,100)]`：

| route_id | 两端 | duration_ms |
| --- | --- | --- |
| dorm-teaching | dormitory—teaching-building | 8000 |
| teaching-library | teaching-building—library | 8000 |
| library-cafeteria | library—cafeteria | 8000 |
| cafeteria-dorm | cafeteria—dormitory | 8000 |
| teaching-activity | teaching-building—activity-room | 10000 |
| activity-cafeteria | activity-room—cafeteria | 12000 |

World按边耗时求最短路，等耗时路径按route_id序列的字典序选择；禁止随机选路。多边移动使用累计边耗时决定当前段，段内沿path长度比例插值；A返回每段耗时，C采用同一算法显示。

默认角色沿用当前姓名、简介/兴趣可补简短文本；创建新实验时A生成新的全局角色ID，模板中的`chen-yu`等仅为临时标识，不能跨实验复用写入AgentProfile主键。A返回规范化配置，B/C只使用返回ID。一个实验创建多个运行可以复用其角色ID。

| 角色 | 起点 | 日程（仿真毫秒→地点） |
| --- | --- | --- |
| 陈宇 | teaching-building | 5000→activity-room |
| 林夏 | library | 空 |
| 周宁 | activity-room | 空 |
| 李沐 | cafeteria | 10000→library |
| 王悦 | dormitory | 0→cafeteria |
| 赵航 | teaching-building | 20000→library |
| 孙可 | library | 空 |
| 许安 | activity-room | 15000→dormitory |

schedule_id由A按角色和序号生成，保存后保持稳定。默认活动为`reading-club/社团读书会`，地点activity-room，开始60000、结束120000；本轮仅保存/展示，不自动加入活动或强迫全员参与。

C允许编辑实验名称、角色简介/兴趣/目标/起点及日程时间与目标；不增减角色/地点，不提供路线编辑器。新实验保存时角色ID由A规范化；编辑已有实验必须保留角色ID。外层name是名称输入的唯一准值，A同时将config.name归一为它。A校验全部引用、8角色、5地点、图连通性、正边耗时和时间合法性；错误返回字段路径，不能部分保存。

## 3. 公开HTTP接口

C负责传输DTO和路由，调用A的应用服务；A负责写服务及初始化事务。浏览器仍使用`/api`与`/ws`代理前缀，后端不加前缀。

| 方法与路径 | 固定输入与输出 |
| --- | --- |
| GET /templates/campus-w2 | 返回`{template_id:"campus-w2",name,config}`，config为上述默认配置 |
| GET /experiments | `{items:[{experiment_id,name,updated_at}]}`，最近100条 |
| GET /experiments/{id} | `{experiment_id,name,config,updated_at}` |
| POST /experiments | 输入`{experiment_id,name,config}`，首次201，返回规范化实验；同ID和同意图重试200复用，同ID不同创建意图409 |
| PUT /experiments/{id} | 输入`{name,config}`整体保存，200返回完整实验；只影响未来新运行 |
| POST /runs | 输入`{run_id,experiment_id}`，首次201创建DRAFT，响应RunSummary；同ID和同实验重试200返回原RunSummary，不同实验409；created只用于选择状态码，不放入HTTP响应 |
| 既有/runs及状态/事件/角色/命令/WS接口 | 地址和已有字段保持；按下文扩充只读字段 |

experiment_id/run_id由C为一次创建操作生成并在重试时复用；仍允许合法字符串ID，不把UUID变成全局契约要求。A在0003新增`experiments.creation_intent_hash:String(64),nullable=True`：旧记录保留null，新建由应用必填，编辑不覆盖。摘要取角色ID规范化之前的`{experiment_id,name,config}`（先归一config.name），按UTF-8、键排序、紧凑JSON计算SHA-256；角色ID规范化不影响创建重试比较。旧schema=1实验在本轮只读，不用W2表单编辑或创建新运行，相关写入422并说明应从campus-w2新建。

创建Run时A在一次事务中锁定并复制已保存配置，初始化角色、地点与活动状态，`status=DRAFT,sim_time_ms=0,last_seq=0,run_epoch=0`。快照创建后不可修改，StartRun不重新读取模板。ValidateConfig仅校验该快照。

命令提交仍为：`{request_id,type,schema_version:1,payload}`，command_id服务端生成。ValidateConfig/StartRun/PauseRun/ResumeRun/StopRun的payload固定`{}`，通知保持原payload。未知命令/字段拒绝；合法业务意图可先202保存，再由Runtime拒绝。

保留CommandReceipt：`command_id,status,result_event_ids,reason`。pending对应accepted回执；DEFER不写入数据库status。错误：404资源不存在，409幂等冲突，422格式/配置错误，503暂时无法持久化。404/409/503沿用`{detail:string}`；422采用`{detail:[{loc:["body","config",...字段路径],msg:string,type:string}]}`，C据此定位表单。业务拒绝通过rejected回执和稳定reason表达。

## 4. 生命周期、控制反馈与恢复

| 状态 | 固定允许操作 |
| --- | --- |
| DRAFT | ValidateConfig成功→READY；其余控制/行动拒绝 |
| READY | StartRun→RUNNING；ValidateConfig可幂等校验；行动拒绝 |
| RUNNING | PauseRun→PAUSED；StopRun→FINISHED；通知与合法行动执行；时钟推进 |
| PAUSED | ResumeRun→RUNNING；StopRun→FINISHED；新通知拒绝，行动提案DEFER，到期完成保留，时钟冻结 |
| FINISHED/FAILED | 只读；旧行动/到期完成拒绝，时钟停止 |

同request_id永远复用原结果。不同request_id重复StartRun/ResumeRun且已RUNNING、重复PauseRun且已PAUSED、重复StopRun且已FINISHED，固定返回`applied,result_event_ids:[],reason:"already_running"/"already_paused"/"already_finished"`。READY重复ValidateConfig同样无变化，reason固定already_ready。均不生成重复事件；C显示“已是目标状态/配置已校验”，不等待事件。其他非法迁移rejected。

控制命令优先于普通提案；暂存命令不得堵住继续/停止。正常迁移事件为RunStarted、RunPaused、RunResumed、RunStopped。ValidateConfig使DRAFT变READY时新增ConfigValidated事件；这是为主计划既定“校验到READY”补齐事件名，不新增业务流程。停止后递增epoch，中断当前动作并固定位置；真正结束/失败同样使旧提案失效。

**重启严格按主计划3.6：DRAFT/READY/RUNNING/PAUSED均恢复或保持PAUSED；FINISHED/FAILED不变。** A通过运行锁、World和UoW完成一次恢复；实际迁移生成RunPaused并记录`reason=restart_recovery`及原状态，原PAUSED不重复发事件。保存recovery_reason供C说明。

恢复后用户点击继续，A先校验快照；无效则拒绝并保持PAUSED。若历史尚无RunStarted，首次继续生成RunStarted，随后启动规则任务；已有启动记录则生成RunResumed。C对ResumeRun接受这两种已冻结的生效事件。此为恢复例外，正常新建仍走DRAFT→READY→RUNNING。

## 5. 仿真时间与移动

Scheduler约250ms检查，默认1×。冻结内部入口`CommandProcessor.advance_time(run_id,elapsed_ms)`：与普通命令共享运行锁、World和UoW，只在RUNNING推进时间；不暴露HTTP，不新增公开Tick命令，不由定时器直接改ORM，也不为每个tick写事件。失败不推进进程时钟锚点。

暂停、继续、恢复后重建单调墙钟锚点，停机及暂停墙钟时间不计入仿真。权威位置由仿真时间和动作段计算。移动中location_id保留起点，完成后才设为终点；停止时保存停止瞬间的插值坐标并清除动作。若中途停在路线上，将location_id设为null并显示“途中停止”，不把人物误报为仍在教学楼；原本静止者保留地点。

开始MOVE时World校验：RUNNING、同run角色、角色无其他动作、目标与路线合法、epoch/计划版本/相关资源版本匹配、提案未过期、schedule_id属于该角色且到时。接受后增加plan_version，保存动作起终点、分段路径、仿真起止时间，生成DecisionRecorded和ActionStarted。

日程时间是最早执行时刻，不是要求回填的开始时刻。started_at_ms取World实际应用时的sim_time_ms，ends_at_ms=started_at_ms+路线总耗时。无故障时日程到应用、到期到完成各允许0—1000ms仿真延迟；超限应记录并修复，不通过伪造时间达标。

到期由Scheduler提交已有CompleteAction，request_id固定为`complete:`加`SHA256([run_id,run_epoch,action_id])`。完成同一action只产生一次AgentArrived，并标记相应日程项完成；重复输入复用或无变化，不能再次到达。到达事件的sim_time_ms取实际提交时刻，不回填到截止时间。

空闲WAIT也由ProposeAction进入World验证：没有其他动作时可保持当前位置，记录DecisionRecorded并增加plan_version；不生成ActionStarted、CompleteAction或AgentArrived。World从日程计算下次评估时间，写入AgentState.plan；无后续日程则为null。目标本来就在当前位置的到期日程项，在WAIT通过时标记完成，不能无限重评同一项。

AgentState.plan固定存`completed_schedule_ids:[string]`、`next_evaluation_at_sim_time_ms:int|null`、`last_proposal_command_id:string|null`、`last_decision:{source,action,target,summary,memory_refs}|null`。这是权威计划状态，由A写，B/C只读。

## 6. 行动提案、规则上下文与任务

沿用ActionProposal所有现有字段：`agent_id,action,target,source,summary,memory_refs`。MOVE.target为地点ID，WAIT.target为null，source固定rule；不添加模型字段。

ProposeAction.payload沿用现有`run_epoch,agent_plan_version,resource_revisions,proposal,expires_at_sim_time_ms`，本轮补充可空`schedule_id`（旧记录默认null，新日程提案必须提供对应ID）。resource_revisions保持现有二元组数组格式，MOVE携带目标地点版本；有效期固定为生成上下文时的sim_time_ms+60000。暂停不消耗仿真有效期，继续后仍须重新验证。

B扩充DecisionContext，但不改变现有字段含义：增加`sim_time_ms,context_event_seq,location_id,current_action,schedule,completed_schedule_ids,known_locations,resource_revisions`；旧调用兼容默认值，W2 Worker必须填完整。context_event_seq取一致读取的run.last_seq；current_action与第8节action同形，schedule与第2节同形，known_locations为`[{location_id,name,position}]`，resource_revisions为二元组数组。只包含自身状态、公开地图、自己的日程与可见事实，model_allowed=false，不传完整世界日志。

规则固定：从未完成日程中取最早一项；尚未到时→WAIT；到时且目标不同→MOVE；到时但已在目标→WAIT并由World确认完成该项；无剩余日程→WAIT且不再定时自触发。World决定路线与耗时，Strategy不计算或写坐标。

规则观察者稳定名`rule-decisions-v1`，复用cognition消费组；原`cognition`通知记忆收据不改、不清空。触发白名单：RunStarted创建8角色首次任务；RunResumed为无动作角色重新评估；AgentArrived仅评估该角色；ActionRejected按下文受限重评；RunStopped取消未完成任务。NoticePublished继续按原范围写记忆，本轮不理解自由文本。

观察事务先锁定并检查当前Run，再处理任务。除RunStopped的取消动作外，终态、来源epoch失效或旧schema=1运行都只记收据，不创建/合并任务；不能因迟到RunStarted把停止后的任务复活。任务事务统一按Run共享锁→Job锁→命令写入的顺序，世界事务按Run排他锁进入，计算期间不持锁。

行动拒绝码固定：stale_plan、stale_resource、proposal_expired可刷新上下文重评；actor_busy等待该角色真实到达事件，不立即重评；stale_epoch、run_terminal取消；invalid_schedule、invalid_target、no_route、invalid_action、invalid_run_state不自动重评。根任务`input_context.rejection_count=0`，由ActionRejected派生任务时递增，同日程同epoch第3次连续拒绝后停止自动重评并保留失败码。原任务仍保留已完成计算事实，decision_status可依据其提案被拒绝显示failed；不能无限换job绕过上限。新的用户继续操作产生RunResumed后允许作为新根评估。

收据与任务创建/合并同事务；PG补偿覆盖这些事件和对应观察者名。每角色最多一个pending/running任务。新刺激存`input_context.pending_stimulus={event_id,event_seq,correlation_id}`及needs_reevaluation，不覆盖`input_context.context`中的运行中输入；任务结束后仅为未处理刺激创建下一任务。

B每250ms查询RUNNING的到期计划唤醒点，只处理无当前动作的角色。来源事件固定取`last_proposal_command_id`对应的DecisionRecorded；任务键为`wake:`加`SHA256([run_id,epoch,agent_id,plan_version,due_ms])`，来源必须是真实事件。无唤醒时间不自建任务；时间到但已有同键历史任务也不重建。前一提案尚未最终处理时不领取后续任务，避免两个未应用提案竞争。

事件任务键为`event:`加`SHA256([source_event_id,agent_id])`；所有键的SHA-256均使用UTF-8紧凑JSON数组及小写十六进制，不能直接拼长ID突破列长度。job_id固定`job-`加32位随机十六进制标识，proposal请求键不超过128字符。租约15秒，最多3次领取；失败后的两次自动重试分别等1、2秒，第3次失败进入failed，不再安排第4次。领取更换claim token并记录attempt，提交时检查running状态、token和attempt，失效领取者整个结果提交取消。失败状态更新也必须匹配仍在running的领取者，不能把已提交completed改回failed。停止取消任务，世界epoch校验仍是最后防线。

B提供维护命令`python -m app.retry_job --job-id JOB_ID`，仅在原任务failed、epoch仍有效、运行非终态、没有同角色未完成任务且没有已提交提案时重置为pending并清零尝试次数；领取时重取上下文。已完成/过期/已有提案的任务拒绝人工重试，不清空收据或旧事件。该命令只重试技术执行失败，领域拒绝按上一段的受限重评处理，不属于前端产品页面。

任务result固定`{proposal,proposal_command_id,next_evaluation_at_sim_time_ms,error_code}`。结果、completed状态与唯一ProposeAction命令同事务保存；提案request_id为`proposal:{job_id}`，不能按重试换ID。WAIT一样要经过该命令链；唤醒时间最终以World保存的计划为准。

## 7. 已确定的内部交付入口

以下是后续施工要实现的接口，当前代码未必已具备；本次不创建实现。

| 提供方 | 固定入口及返回 |
| --- | --- |
| A | `ExperimentService.default_template()/list()/get(id)/replace(id,name,config)`：返回第3节对应数据；`create(id,name,config)`固定返回`{created:boolean,experiment:ExperimentView}`，C只将experiment作为HTTP响应，created决定201/200 |
| A | `RunCreationService.create(run_id,experiment_id)`：返回`{created:boolean,run:RunSummary}`，复制快照及初始化同事务 |
| A | `PostgresTransactionalCommandWriter(session).append(envelope,correlation_id,causation_id)`：复用调用者事务，返回回执，不自行commit |
| A | `SimulationFacade.submit(envelope,*,correlation_id=None)`：兼容现有调用；C转交可选追踪Header，未提供时A采用request_id |
| A | `RuleContextReader.load(run_id,agent_id)`：一致读取第6节上下文；实现位于PostgreSQL层，输出纯领域数据 |
| A | `CommandProcessor.advance_time(run_id,elapsed_ms)`及统一恢复入口：保持权威事务边界 |
| B | `RuleDecisionStrategy.decide(context)`、任务/提案服务和Worker；`build_cognition_loops(resources)`统一装配 |
| B | `DecisionReadService.agent_status(run_id,agent_id)`与`run_status(run_id)`：返回下文只读摘要 |
| C | HTTP路由、WorkbenchQueries及前端，调用上述服务；不在路由新写业务事务 |

A提供应用服务及写/上下文工厂，C提供路由与读取工厂，各自用自己的新模块导出；B统一在bootstrap、API lifespan和Worker入口接线。A拥有Runtime调度文件；B提供可被调用的恢复/依赖装配部分但不同时编辑该文件。

根用户命令correlation_id默认request_id，可接收X-Correlation-ID；派生命令继承来源事件的根correlation_id，causation_id指直接来源事件。World使用显式执行上下文接收追踪信息。每条命令直接产生的事件统一causation_id=command_id，seq仅A分配。

commands.result_event_id保存首个直接结果事件指针；回执result_event_ids按run和causation_id查询直接结果并按seq排序，不能只返回单字段冒充全部结果。无变化控制回执是第4节已规定的例外。

## 8. 事件与读取DTO

A负责命令解码及世界事件。新增ConfigValidated需同步事件枚举、CHECK和新增`0003_w2_runtime`迁移；已发布0002不得改写。其他事件复用主计划已有名称。技术故障写任务/日志，不递归生成领域事件。

| 事件 | payload最小字段 |
| --- | --- |
| ConfigValidated | `status:"READY"` |
| RunStarted/RunPaused/RunResumed/RunStopped | `status,run_epoch,reason`；恢复额外`recovered_from` |
| DecisionRecorded | `agent_id,source:"rule",action,target,summary,memory_refs,schedule_id,next_evaluation_at_sim_time_ms` |
| ActionStarted | `agent_id,action_id,type:"MOVE",from_location_id,to_location_id,segments,started_at_ms,ends_at_ms,schedule_id` |
| AgentArrived | `agent_id,action_id,location_id,schedule_id` |
| ActionRejected | `agent_id,reason,schedule_id`，只用于已解码行动意图的领域拒绝 |
| ActionInterrupted | `agent_id,action_id,reason:"run_stopped",position:{x,y}` |

非法JSON/未知版本和非法通知仍通过命令rejected回执表达，不伪造行动失败。停止时先写RunStopped，再写需中断动作的ActionInterrupted，全部同事务。DecisionRecorded由A在有效提案处理事务生成，B不能自行追加events。

RunSummary保持现有字段并新增experiment_id。RunView在其基础上新增：`run_epoch,sim_speed:1,sampled_at(UTC),recovery_reason,routes,rule_status`。LocationView新增position。AgentView及AgentDetail新增`position,current_goal,action,plan_version,last_decision,decision_status`，保留原记忆字段。

`action=null`或`{action_id,type:"MOVE",from_location_id,to_location_id,segments:[{route_id,path:[{x,y}],duration_ms}],started_at_ms,ends_at_ms}`。position为采样仿真时刻的权威插值坐标。current_goal为下一未完成日程目标地点ID或null。

`decision_status={status:"idle"|"pending"|"running"|"failed",source:"rule",summary:string|null,error_code:string|null}`，由B只读服务提供；`last_decision`来自World已应用的计划记录，不把尚未应用的建议标为已执行。

`rule_status={mode:"rule",status:"ok"|"degraded",failed_jobs:int,message:string|null}`。C的状态查询从同一一致世界读视图取得时钟/位置/动作/seq；任务摘要允许稍晚更新，不能拿它覆盖世界状态。

旧schema=1运行原快照不改，读取缺少新字段时返回routes=[]、action=null及已有位置，页面标识旧演示；不回填历史规则任务。通知观察与查看保留，W2行为验收仅使用正式新建schema=2运行。

## 9. C可直接使用的固定Mock

不要等A/B完成再开发。用第2节默认配置和以下快照制作Mock；ID仅为示例，真实使用服务端返回值：

| 场景 | 固定数据 |
| --- | --- |
| 未启动 | DRAFT，sim_time_ms=0，8人原位；校验后READY |
| 正在移动 | RUNNING，陈宇started_at_ms=5000、ends_at_ms=15000，采样sim_time_ms=9000 |
| 已暂停 | PAUSED，沿用9000；任意墙钟等待后仍为9000且坐标不变 |
| 已到达 | RUNNING，sim_time_ms=15000，陈宇location_id=activity-room，action=null |
| 已停止 | FINISHED，epoch从0变1，无当前动作，显示停止位置 |
| 控制无变化 | applied、result_event_ids=[]、reason=already_paused，显示“已是暂停状态” |
| 拒绝/冲突/断线 | rejected+reason；HTTP409；WS断线后状态重取及事件分页补拉 |

C必须保留通知的精确causation_id匹配。一般状态迁移也按本命令对应事件确认后刷新状态；控制无变化按第4节显示。暂停请求中不提前冻结权威状态，收到RunPaused再冻结；断线不外推或控制，重连先同步状态并按已处理seq补齐事件。停止需一次确认。

Mock的5000—15000是理想时刻固定示例；真实端到端使用实际started_at_ms和ends_at_ms验收，并按第5节记录调度延迟。

状态每500ms补拉，收到相关事件立即刷新；事件仍保留原2秒补偿查询。收到状态时用浏览器单调时钟记录显示锚点，RUNNING只按该锚点与sim_speed外推，定期用权威状态校正，不直接相减两台机器的墙钟时间。

## 10. 交付证据

A负责世界/状态/原子性验证；B负责真实PG/Redis、任务租约/重复消费和部署；C负责前端逻辑/构建与浏览器E2E。共同验收脚本见[总计划](README.md)。三人分别记录实际命令和结果；测试跳过、未部署和已知限制必须如实区分。只有文档可以在本轮修改，以上全部接口均是后续施工要求。
