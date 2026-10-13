# 服务器资产管理系统需求整改变更说明

开始整改：2026-10-10；本次交付：2026-10-12。

用户授权：按照speckit-analyze的推荐修改相关内容，并交付一份说明全部变更的文档。
本报告涵盖11份已修改文档和4份新增文档。已按推荐完成文档整改，并将用户最新选择A记录为Q12：
首版可恢复业务配置键白名单为空，保留结构和备份校验，不新增设置功能，未知配置键拒绝恢复。
两份需求清单全部通过，接受A后的最终一致性复核无未解决Critical/High；实现继续保持暂停，0/44。

## 具体更改

| 项目 | 更改前 | 更改后及原因 | 主要文件 |
| --- | --- | --- | --- |
| 账号编辑版本 | 用户接口要求version，但模型/建表任务未定义 | 增加独立User.version，从1起；实际资料/密码/强制改密标志改变才递增；auth_version继续负责会话撤销，显示名单独变更不撤销会话；旧编辑版本409整次拒绝 | spec、data-model、api、plan、T012/T013/T015 |
| 单次确认 | 有短时、单次、目标绑定要求，缺存储及事务细节 | 定义ChangeConfirmation/ControlConfirmation、256位随机令牌摘要、操作者/授权/epoch/目标版本/完整动作集合/拟值/到期/消费状态；业务确认与变更、审计和回执同事务，控制确认与控制作业同事务 | data-model、api、recovery、T005/T009/T012/T032 |
| 幂等与秘密 | 通用request_digest没有明确秘密排除范围 | 逐路由非秘密白名单；密码/额外密码指纹/原确认令牌/完整引用/恢复输入候选用户名不得进入摘要或回执；已完成同键重试只返回原结果，新秘密变更必须新键及新确认（如需）；补充204重试头及控制库ControlReceipt | spec、data-model、api、research、plan、T009及AC-SECRET-001 |
| 类型适用字段 | 已有必填/清空原则，缺完整适用表 | 列出全部21字段的四类型适用性；virtual序列号、network/storage主机名可选；非虚拟宿主不适用必须为空；保留仍适用值，不隐式丢弃；失败原字段/类型/关系不变 | spec FR-008、data-model、T017/T020 |
| 文件完整列清单 | 仅“中文列版本1/全部业务字段” | 精确21列、中文名称、字段映射、固定生成顺序；第1行版本/转义元数据，第2行表头，第3行起数据；拒未知/缺失/重复列和版本，不猜测别名/编码；元数据/表头不计5000数据行 | 新增contracts/file-schema.md；spec、api、research、T024/T026 |
| CSV公式防护 | 要求防公式和往返，但未规定转义 | apostrophe-v1对每个非空数据格前置单引号，按明确元数据解码恰好一层；Excel强制字符串；规定前导零/引号/逗号/多行/危险前缀测试，重复资产仍不覆盖 | file-schema、api、T024/T025/T026/T028 |
| 导出预览与结果 | 条件回显、取消及下载失败含义未完整定义 | 回显范围/格式/规范化筛选/冻结时刻/数量/21列；确认前取消不建作业；生成失败、下载前失败、传输中断、服务器发送完成分别报告；客户端是否保存为unknown，不伪造不可观测取消；文件过期410，不新增后台取消功能 | spec FR-016、file-schema、api、T025/T028/T029 |
| 审计完整枚举 | category/action/result为自由抽象字段 | 24种类别/动作组合和11种结果，明确允许组合、字段白名单和角色可见范围；阶段事件追加、不修改审计；逻辑幂等重试不重复成功事件，下载新尝试独立审计 | 新增contracts/audit-events.md；data-model、T008/T025/T030 |
| 删除/迁移/状态并发 | 有事务/触发器方向，缺确定性业务验收 | AC-CON-001..005明确两种提交顺序、409 STALE_VERSION/RELATION_CONFLICT/DEPENDENCY_CONFLICT、503忙错误及失败数据/确认保持；成功方不被失败请求回滚、不得产生孤儿或丢失更新 | 新增contracts/acceptance.md；spec FR-009、T018/T020/T021 |
| 高风险追溯 | 部分风险仅笼统描述测试 | 17个唯一AC覆盖认证/权限/账号/确认/秘密/资产/删除/导入导出/审计/备份恢复/并发，并映射FR/SC/T；注明不适用路径理由；补齐零行配置正例及未知键/非空manifest反例 | acceptance、spec、quickstart、tasks |
| 首版业务配置范围 | 已要求备份业务配置，但实际键未确认 | 用户选择A，首版键白名单为空；SystemSetting保留零行结构，业务层和数据库约束拒绝任意键；新manifest business_setting_keys: []；未知配置在保护备份、维护、会话失效前拒绝，不静默删除，也不能由旧schema迁移丢弃；未来新增键另行确认 | spec Q12/FR-019/SC-006、data-model、api、recovery、plan、T007/T032/T034/T036 |
| 恢复与确认 | 新增确认模型尚未同步备份恢复 | 快照及candidate清除运行态确认，清理后重做完整性/摘要；候选回执绑定User.version；跨库使用operation_uuid对账；恢复/回滚不复活旧确认或旧会话 | recovery、data-model、T032/T034 |
| 权限与计数一致性 | 降权创建者读导入接口表述不清；预览提及实际成功数 | 创建者须当前有编辑权限，管理员例外；补齐既有管理员专属永久编号查询路由；预览只报可导入/错误，执行才报实际终态；恢复前拒绝/取消不要求重新登录 | api、spec用户故事3、quickstart |
| 清单和阶段措辞 | 清单仍指Q1–Q3/固定3组，指南仍说尚未生成任务，类型评审记录落后 | 更新当前需求复核和逐项证据，18/18及26/26；规格标明评审通过、实现暂停；44项任务标记均保留未完成；仅将实际回答A记为本轮1条Q/A，不把技术选择记为用户答复 | 两份checklists、docs/design-review.md、spec、plan、quickstart、tasks |

## 对前次分析结论的校正

- A4是秘密处理设计缺口，没有应用代码，不能当作已发生秘密泄露。
- A10原规格已有类型切换原则，但完整适用字段表仍需补充；本轮已补表并同步当前评审。
- A11按原推荐保留FR-019/FR-020的职责划分：范围/历史与恢复过程/失败保护分别追溯，不盲目合并。
- 技术默认仍须实现后的安全/性能验证。上述明确编码和数据结构不是新增已确认业务功能。

## 清单与实施状态

| 项目 | 更改前 | 当前 | 剩余事项 |
| --- | --- | --- | --- |
| 内建requirements.md | 16/18 | 18/18 | 无未通过项；新增通过CHK010/CHK018 |
| 自定义requirements-review.md | 1/26 | 26/26 | 无未通过项；新增通过25项，含本次关闭CHK019/CHK024/CHK026 |
| 实施tasks.md | 0/44 | 0/44 | 没有勾选T001，未开始T002或恢复编码 |

接受A前的历史中间状态为内建17/18、自定义23/26；本次接受A后分别新增通过CHK018和CHK019/024/026，
无退回项或剩余未通过项。每项证据和最终分析覆盖表见[设计复核记录](design-review.md)。
更新清单依据本轮用户要求全量修订的授权，发生在需求澄清阶段；实施代理仍不得自行改清单或越过门槛。
本轮正式提问1项，明确收到答复1项，未超过5题；既有Q1–Q11不重复计数，没有伪造接受记录。

## 已确认的业务决定

Q12（原P1）：首版“应用内业务配置”允许恢复哪些实际键？用户明确选择A，已同步：

- 首版白名单为空，SystemSetting保留结构但没有默认配置行；不新增设置页面或API。
- 合法备份/恢复的配置表为零行，新manifest的business_setting_keys为[]，可完成备份恢复正例。
- 未知配置行或非空manifest键范围拒绝恢复；反馈不回显键/值，不创建保护备份、不进入维护、不撤销原有效会话，原库保持可用。
- 不通过清空配置或旧schema迁移来绕过拒绝；备份发布、升级迁移及最终候选校验重复验证范围。

已删除规格中的未决标记。技术设计细化与产品回答分别记录，不以工程默认代替业务确认。
当前没有产品未决项；未来新增配置键须另行明确类型、默认值、允许范围并更新备份恢复验收。
spec更新区域：状态、Clarifications当日会话、User Scenarios & Testing的Edge Cases、Functional Requirements、
Measurable Outcomes、Assumptions及其决策索引/补充验收场景。既有产品决定保持原义。

## 修改文件清单

| 文件 | 操作 |
| --- | --- |
| [spec.md](../specs/001-server-asset-management/spec.md) | 修改需求、字段适用表、失败/计数规则，记录Q12并关闭原P1缺口 |
| [plan.md](../specs/001-server-asset-management/plan.md) | 同步设计、契约清单、版本/确认/幂等和评审状态 |
| [tasks.md](../specs/001-server-asset-management/tasks.md) | 同步原任务的模型/实施/测试验收与Q12空配置范围，ID及直接依赖保持不变 |
| [research.md](../specs/001-server-asset-management/research.md) | 同步版本/确认/秘密摘要及文件协议 |
| [data-model.md](../specs/001-server-asset-management/data-model.md) | 同步User.version、确认、回执、运行态恢复边界和SystemSetting空白名单约束 |
| [api.md](../specs/001-server-asset-management/contracts/api.md) | 同步输入/输出、版本/幂等、权限和结果语义 |
| [recovery.md](../specs/001-server-asset-management/recovery.md) | 同步确认清理、控制事务/对账、旧确认失效及未知配置前置拒绝 |
| [quickstart.md](../specs/001-server-asset-management/quickstart.md) | 同步验收矩阵及当前阶段状态 |
| [requirements.md](../specs/001-server-asset-management/checklists/requirements.md) | 复核内建质量清单及过时措辞 |
| [requirements-review.md](../specs/001-server-asset-management/checklists/requirements-review.md) | 同步有依据的复核结果及剩余项 |
| [design-review.md](design-review.md) | 更新11项分析处置、26项依据、Q12答复及接受A后的最终只读分析 |
| [file-schema.md](../specs/001-server-asset-management/contracts/file-schema.md) | 新增精确文件协议 |
| [audit-events.md](../specs/001-server-asset-management/contracts/audit-events.md) | 新增审计枚举及白名单协议 |
| [acceptance.md](../specs/001-server-asset-management/contracts/acceptance.md) | 新增高风险验收追溯 |
| 本文档 | 新增变更说明及验证边界 |

## 验证范围

本次只校验文档结构、相对链接、需求/任务/依赖/验收标识、文件列映射、审计枚举及清单计数。
不声称已执行Django、pytest、Compose、迁移、构建、性能或备份恢复运行测试；仓库没有应用代码。
项目宪法及Git远端未改动，原README删除状态保留，没有提交或推送。

2026-10-12执行的Node只读文档校验结果：

| 检查 | 结果 |
| --- | --- |
| 15份文档代码围栏、Markdown表格列数、尾部空格、末尾换行、相对文件链接 | 通过，0格式/引用错误 |
| 27条FR+11条SC标识及任务追溯 | 38/38，100%有任务映射；这不是实现通过率 |
| 44个任务标识、直接依赖及有向依赖图 | 唯一且完整，直接依赖保持原样，无缺失依赖或环；0/44完成 |
| 17个AC标识与FR/SC/T引用 | 唯一且引用有效 |
| 21列与AssetWrite字段映射 | 集合、顺序及字段一一对应 |
| 24种审计类别/动作组合与11种结果 | 组合唯一，所有结果均已登记 |
| 内建/自定义清单标识与计数 | 18/18、26/26，无未通过项；本次新增状态及总体变化分别记录 |
| 既有Q6–Q11与本轮Q12问答 | 保留原6条问答，当日新增1条实际接受记录，无未决标记 |
| 接受A后的speckit-analyze | Critical/High/Medium均0；保留1项LOW邻近重复，无宪法冲突或未映射任务；只读分析期间核心文件未改变 |

本轮覆盖分类：

| 类别 | 状态 | 说明 |
| --- | --- | --- |
| 功能范围与行为 | Clear | 四故事、三角色和首版排除范围沿用已确认规则 |
| 领域与数据模型 | Resolved | 版本、确认及类型字段已补齐；Q12确认配置空范围、零行约束及未知键拒绝 |
| 交互与流程 | Resolved | 导出回显、取消、传输/本地保存反馈及预览/执行计数已明确 |
| 非功能质量 | Resolved | 秘密摘要、审计边界及故障语义已定义，性能和安全效果待实现验证 |
| 集成与外部依赖 | Resolved | 三格式版本化中文21列及CSV往返协议已精确定义 |
| 边界与失败处理 | Resolved | 并发、确认/回执故障、重启及恢复边界已列入唯一AC |
| 约束与取舍 | Clear | 宪法和技术默认保持，不新增设置页面或后台取消能力 |
| 术语与一致性 | Resolved | 编辑version与auth_version分离、用户角色及事件结果用词已统一 |
| 完成与验收信号 | Resolved | 配置具体fixture、两份清单和最终文档复核门槛已闭合；实际功能测试留给实施验证 |
| 占位与未决记录 | Resolved | 原P1已按实际答复关闭，当前无产品未决项或过时待确认状态 |

clarify的前后扩展检查及analyze的前后扩展检查均已完成，.specify/extensions.yml不存在，无需执行钩子。
本轮文档整改已完成，无需再次clarify或重生成计划/任务。此前实现暂停继续有效；
用户明确恢复后，下一条实施命令为speckit-implement，先复核T001的现行版本及评审证据，再按依赖顺序实现。
