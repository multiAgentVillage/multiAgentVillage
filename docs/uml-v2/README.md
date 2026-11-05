# v2 UML与GoF设计附件

主文档：[project-plan-v2.md](../project-plan-v2.md)，新增内容集中在第三节3.11。原始[project-plan.md](../project-plan.md)保留不变。

## 内容与状态

- `design-section.md`：从主文档提取的3.11章节，便于单独审阅；以主文档为准。
- `diagrams/*.puml`：9张可编辑PlantUML图，图中模式角色与主文档类名对应。
- `rendered/*.png`：本地渲染的可查看预览。
- `reference_interfaces.py`：标准库接口与小例子，不是后端程序，不含ORM/网络实现；不可据此声称可靠性功能已完成。
- `build_plan_v2.py`：检查当前v2的链接与结构，并同步3.11章节；不再从v1重新拼接，避免覆盖后续修订。
- `revisions/project-plan-v2.0-before-terminology.txt`：用词统一前的文本基线，仅用于核对修订。

## 图源索引

| 编号 | 图类型 | 图源 | 预览 |
| --- | --- | --- | --- |
| U01 | 用例图 | [源文件](diagrams/U01-use-cases.puml) | [PNG](rendered/U01-use-cases.png) |
| U02 | 组件图 | [源文件](diagrams/U02-components.puml) | [PNG](rendered/U02-components.png) |
| U03 | 类图：命令/世界/状态 | [源文件](diagrams/U03-command-world.puml) | [PNG](rendered/U03-command-world.png) |
| U04 | 类图：认知/策略/适配 | [源文件](diagrams/U04-cognition.puml) | [PNG](rendered/U04-cognition.png) |
| U05 | 状态图 | [源文件](diagrams/U05-run-state.puml) | [PNG](rendered/U05-run-state.png) |
| U06a | 时序图：通知生效 | [源文件](diagrams/U06a-notice-sequence.puml) | [PNG](rendered/U06a-notice-sequence.png) |
| U06b | 时序图：认知和行动 | [源文件](diagrams/U06b-decision-sequence.puml) | [PNG](rendered/U06b-decision-sequence.png) |
| U07 | 类图：Memento | [源文件](diagrams/U07-memento.puml) | [PNG](rendered/U07-memento.png) |
| U08 | 部署图 | [源文件](diagrams/U08-deployment.puml) | [PNG](rendered/U08-deployment.png) |

UML图由PlantUML表达。`<<Command>>`等为项目模式标签；不声称定义了正式UML Profile。组件图和部署图分别描述逻辑职责、物理进程，不能把每个类或组件当成一个新服务。

## 本地重新生成

原始图源不依赖网络。使用已有Java和PlantUML JAR渲染；类/组件等图使用内置Smetana布局，避免额外安装Graphviz。生成时工作目录为`D:\SEProject\docs\uml-v2`，将下列`<plantuml.jar绝对路径>`替换为本机工具位置：

```powershell
java '-Djava.awt.headless=true' -jar '<plantuml.jar绝对路径>' -charset UTF-8 -checkonly 'diagrams/*.puml'
java '-Djava.awt.headless=true' -jar '<plantuml.jar绝对路径>' -charset UTF-8 -tpng -o '../rendered' 'diagrams/*.puml'
python 'build_plan_v2.py'
```

图源指定微软雅黑字体；在其他操作系统重新渲染时需选择可显示中文的字体。校验图语法与参考接口不等于已完成业务实现或运行验收。

本次预览使用PlantUML 1.2024.8与Java 8生成，JAR长度及上游校验和已验证。`tools/`保存本地绘图工具缓存及下载脚本；JAR不是后端运行依赖，交付源码时可不包含。若PATH中的Java是失效的启动器，可直接使用有效JRE的`bin/java`完整路径。

参考：[PlantUML类图](https://plantuml.com/class-diagram)、[时序图](https://plantuml.com/sequence-diagram)、[Smetana布局](https://plantuml.com/smetana02)。
