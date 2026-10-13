# 数据模型

对应 FR-001..027；所有表由 Django migrations 版本化。UUID 为稳定身份，
UTC aware 时间戳，提醒日期为 ISO DATE + Asia/Shanghai；不用编号或用户名作为审计外键身份。
技术上限：名称/编号/序列号255，主机名253，环境/区域/机房/负责人128，用途4096，
硬件描述16384，凭据引用2048；空可选值转NULL。保留显示值及规范化键，输入拒未知字段。

## 业务实体

| 实体 | 核心字段与约束 |
| --- | --- |
| User | uuid、username、username_key UNIQUE、display_name、password_hash、role(admin/editor/viewer)、active、must_change_password、version、auth_version、created_at；version从1开始，独立于会话撤销版本auth_version；用户名trim+casefold，用户名1–128字符，显示名1–128字符，角色枚举CHECK |
| LoginAttemptState | normalized_login_key、window_start、consecutive_failures、locked_until；未知账号同规则，限制来源洪泛；永不存输入密码 |
| AssetIdentity | normalized_asset_no PK、asset_uuid UNIQUE、first_seen、last_deleted_at；永久不删除，编号trim+casefold，规范化算法版本固定 |
| Asset | uuid PK、identity FK/UNIQUE、name、type、purpose、environment、owner_text、status、room、region、hardware_text、serial/display+key、hostname/display+key、supplier、purchase_date、rack_date、warranty_end、expires_on、credential_ref、host_uuid、version、created/updated |
| AssetAddress | uuid、asset_uuid FK CASCADE、scope(internal/external)、ip_display、ip_key UNIQUE；IPv4/IPv6由ipaddress验证，IPv4-mapped IPv6归一到对应IPv4，拒zone_id；单资产也不得重复 |
| AuditEvent | event_uuid PK、instance_id、time_utc、actor_uuid可空、actor_name_snapshot、asset_uuid可空、asset_no_snapshot、asset_name_snapshot、category、action、result、request_id、operation_uuid、before/after白名单JSON、summary白名单JSON |
| SystemSetting | key UNIQUE、typed_value、version；首版键白名单为空，表必须零行，数据库CHECK(0)阻止写入；不存TLS/age密钥、密码或令牌 |
| ImportJob/Row | uuid、owner、file_digest、preview_version、state、created/expires_at；行号、payload、dependencies、error_codes、result、committed_asset_uuid、idempotency_key UNIQUE(job,row) |
| ExportJob | uuid、owner、canonical_filter、format、expected_count、snapshot_digest、state、artifact_id、expiry；筛选与文件内容不直接入日志 |
| Session | 随机session标识、user_uuid、auth_version、global_epoch、expires_at；备份中不恢复运行态session，候选库清空 |
| OperationReceipt | actor_uuid+idempotency_key UNIQUE、operation_uuid UNIQUE、request_digest、confirmation_uuid可空、result_ref；request_digest只摘要显式非秘密白名单，同键不同非秘密操作409，业务和receipt同事务；confirmation_uuid只是服务端绑定引用，不是原令牌 |
| ChangeConfirmation | confirmation_uuid PK、token_digest UNIQUE、actor_uuid、actor_auth_version、session_epoch、target_kind、target_uuid、target_version、actions、proposed_changes、expires_at、consumed_at、operation_uuid；只有非秘密绑定元数据，账号/资产确认存业务库 |

User的登录用户名及username_key在创建后不允许普通账号编辑改变，管理员也不例外；业务层和
输入白名单共同拒绝该变更。管理员修改display_name不改变登录名、规范键或uuid，也不会使显示名
成为新的登录凭据。此规则针对正常账号编辑，备份恢复仍按FR-019/020保留目标中的账号及密码哈希。

User.version是编辑并发版本，任何实际保存的显示名、role、active、密码或must_change_password变更
都在事务内递增；普通编辑必须提交读取时的version，不匹配返回409 STALE_VERSION且整次不保存。
auth_version只承担既有会话撤销规则，显示名单独变更不撤销会话；两者不得相互替代。
登录失败计数单独保存在LoginAttemptState，不把每次登录变成账号资料编辑。恢复候选回执明确绑定User.version。

FR-002/Q11：管理员新增账号必须提供username、display_name、role和初始密码，active未提供时为true，
显式false保持停用；role无隐式默认值，must_change_password由服务端置true。username保存登录名，
username_key保存既有trim+casefold规范键，初始密码只经安全哈希后保存到password_hash，不增加原始密码字段。
缺失或无效输入、用户名冲突及审计失败不产生部分账号；上述创建规则不重写恢复目标中的role/active/must_change_password。

FR-002/024/Q10：停用、已有账号角色变更和重置他人密码需绑定目标及操作的二次确认；
新增、单独显示名修改和重新启用正常提交。确认只绑定非秘密操作元数据及目标当前状态，
不保存新密码或密码哈希；原始新密码仅最终提交时在内存中处理，正常账号仅保存安全密码哈希。
提交重验当前权限及最后管理员保护，确认消费、账号变更和审计同事务；拒绝或取消不部分修改账号或主动撤销其会话。

确认令牌由服务端生成至少256位随机值，仅响应及最终HTTPS请求使用；持久化只存该高熵令牌的SHA-256摘要，
不保存原令牌、密码或密码哈希。actions为排序后的明确操作集合，proposed_changes只含role/active等允许字段。
提交按actor/授权版本/epoch、目标version、动作及拟值重验，未使用且未过期才可消费；
消费、业务变更、版本递增、成功审计与OperationReceipt同一BEGIN IMMEDIATE事务，异常全部回滚。
重启保留消费状态和过期时间，不重新签发或复活确认；过期后可清理确认记录，但不得清理审计或操作回执。
已认证且当前有权的同一幂等重试先读取回执，返回原结果而不是因确认已消费重复执行；新键复用已消费确认返回409。

request_digest使用版本化JSON规范序列化+SHA-256，仅覆盖路由/动作、目标ID/版本和逐路由非秘密业务字段。
密码、密码哈希、令牌、私钥、完整credential_ref、恢复输入的候选用户名及confirmation_id均不得进入摘要输入、回执或摘要副本。
确认操作使用独立confirmation_uuid字段而非原令牌绑定回执，不把该字段加入客户端请求摘要，
从而已提交重试无需再次解析已消费/已清理确认。资产引用改动仅以目标版本和非秘密操作标识绑定。
含密码或完整引用的请求不比较秘密内容：同键、相同非秘密操作在已提交后只返回原回执，即使重试携带不同秘密也不再写入；
如确需另一次秘密变更，必须使用新幂等键及新确认（如适用），反馈明确“返回先前结果，未再次执行”。
本人改密及登录/退出不走通用写入回执，继续遵循当前密码验证和会话失效规则。
没有回执时才执行输入及密码校验；不得通过加入低成本密码摘要来检测重试差异。

SystemSetting按spec Q12采用空白名单：保留key/typed_value/version结构，首版没有允许键或默认配置行，
业务层拒绝全部键写入，迁移建立CHECK(0)保证数据层零行，不新增设置界面或API。
新备份manifest必须包含business_setting_keys: []，同时验证快照表零行；任一表行或非空键清单
均以BUSINESS_SETTING_NOT_ALLOWED失败，不回显未知键及值。候选验证在保护备份、维护和epoch变更前拒绝，
不能靠清空表或旧schema迁移丢弃配置来通过；升级迁移发现已有配置也应失败而非删行。
未来新增键须先另行确认类型/默认值/允许范围，再版本化修改约束、manifest和恢复验收。

编号、主机名、序列号使用trim+Unicode casefold持久key，SQLite默认NOCASE只支持ASCII，
不能代替应用规范化；migrations建key的UNIQUE，NULL可重复。编号从AssetIdentity保留表
取得不可复用身份；创建只能INSERT新identity，不允许客户端指定历史uuid。恢复路径可重建原uuid。
序列号/主机名唯一性只约束当前Asset，彻底删除释放它们和AssetAddress，不删除identity/audit。
identity同编号不同uuid或同uuid不同编号在恢复合并时属于不可消解冲突，拒绝恢复。

## 类型和生命周期

四类型 physical、virtual（含云主机）、network、storage；统一必填name/no/type/purpose/
environment/owner/status/room/region。physical额外serial+hostname；virtual额外hostname+host；
network/storage额外serial。其他字段可选，虚拟资源描述也存hardware_text，不创建未要求的硬件必填项。
完整21个字段的四类型适用表以spec FR-008为准：virtual的serial可选，network/storage的hostname可选；
只有host_asset_no在非virtual中不适用。类型切换保留仍适用的可选值，不隐式丢弃信息；不适用值未清空则拒绝整次保存。
host只能指向physical且status in(racked,active,repair)，非virtual host必须NULL。
host FK ON DELETE RESTRICT；删除虚拟机不删宿主。数据库触发器校验目标类型/状态及
有子节点的宿主类型/状态变更；应用服务提供中文错误。即使管理员也不能绕过触发器。
数据库CHECK约束日期rack>=purchase（两者非空时）、状态枚举、类型必填。
editor迁移边：planned->purchased->racked->active，active->repair、active->retired、
repair->active；未列边拒绝。admin可任意边但仍受宿主限制。未改状态的编辑允许。
FR-006/Q9已确认：admin/editor手工新增或导入新资产时可显式提供六种合法初态，viewer禁止。
首次登记不同于既有资产状态变更，不能覆盖既有资产；后续角色矩阵以spec FR-006为准，仍须关系有效。
状态更新与关系核验在BEGIN IMMEDIATE事务内；version必须匹配，否则409 STALE_VERSION。
关系并发的产品结果及验收以contracts/acceptance.md中的AC-CON-001..005为准，不以锁机制代替验收。

## 审计

审计不使用会随账号/资产删除级联的强制FK，靠UUID及名称/编号快照追溯。
新增before=null，删除after=null；标量和IP集合对比固定排序。普通字段包括负责人、
IP/主机名/序列号保留原值；password/hash/token/private_key/credential_ref不进入任何JSON，
只记录敏感字段名和changed布尔。摘要仅枚举/计数，不拼接原始异常或上传行。
授权拒绝统一使用category=security、action=authorization_denied、result=denied；覆盖已登录用户的
资产、账号、导入导出、审计及备份恢复越权，包括查询、预览和下载。before/after为空，仅保存
操作者、操作类别、安全目标标识及拒绝结果，不复制输入或原始查询条件。只有管理员可查询此类别；
编辑者的asset类别过滤不得混入安全事件，详情授权也独立检查，审计访问的拒绝本身同样留痕。
变更+审计同一业务事务，审计失败则回滚；拒绝操作另一个短事务写结果，
审计存储不可用则请求失败并结构日志记录非敏感故障码。
event_uuid确定去重，重复UUID内容不同视为损坏，禁止静默覆盖。
数据库触发器拒绝AuditEvent UPDATE/DELETE；受控升级只在维护态迁移并验证保持原值。
不是对宿主root的防篡改保证；首版不引入远程合规审计服务。
category/action/result完整允许组合及各类字段白名单以contracts/audit-events.md为唯一枚举依据；
迁移建立枚举和组合CHECK，服务层复验。下载生成、服务器传输完成与客户端保存未知不得合并成一个success。

## 控制状态（不随业务恢复）

control.sqlite：BackupCatalog(id,source,state,size,path,digest,key_id,pin_count)、
RestoreOperation(uuid,phase,old_generation,new_generation,epoch,receipt_digest,error_code)、
SessionEpoch 单行单调增加、maintenance flag、发布/文件清理状态。控制库同样FULL及5s超时，
单恢复worker更新；不与业务库宣称跨库原子事务。
ControlReceipt采用OperationReceipt的actor+幂等键/operation_uuid/非秘密request_digest/确认引用/结果引用字段，
只服务控制作业入队和查询，后台终态通过operation_uuid读取，不将原凭据或请求体放入控制回执。
备份删除/恢复的ControlConfirmation使用上述确认绑定字段，另加backup_digest/validation_id/pin状态绑定，存control.sqlite。
消费与控制作业领用同一控制库事务，业务审计通过稳定operation_uuid及恢复协议对账，不声称与业务库跨库原子。
恢复原始凭据验证成功后才消费/入队；失败不进入维护。运行态ChangeConfirmation/ControlConfirmation不从备份恢复；
替换后全局epoch使原库未消费确认也失效，回滚不得复活旧确认。备份发布前清空快照中的确认记录并重新校验摘要。
恢复确认输入的当前管理员密码、候选管理员用户名和候选管理员密码只在确认请求内存中使用，
不得写入业务库、控制库、作业载荷、日志、审计、错误响应或备份；候选凭据验证失败不得进入PREBACKUP。
RestoreOperation只保存非敏感验证回执/元数据，绑定目标备份摘要、候选管理员UUID/账号验证版本、
操作者UUID/auth_version/session_epoch及本次操作；worker和重启恢复均不依赖保存原始密码。
上述限制针对确认请求的原始输入，不删除或重写目标备份中已有的正常账号及密码哈希。
运行时CURRENT指针指向完整generation目录；状态机详见 recovery.md。
文件目录manifest与审计有稳定operation_uuid，启动对账补写操作而不重复。
临时导入/导出产物默认24h删除，不涉及审计/备份保留；运行态作业不从历史备份自动重放。

## 索引与查询

Asset(status/type/environment/region/owner,uuid)、Asset(host_uuid)、日期索引；
hostname_key、serial_key、identity_key唯一；IP key唯一。
Audit(time_utc,event_uuid)、(category,time)、(actor_uuid,time)、(asset_no_snapshot,time)。
资产用参数化icontains搜索name/no/hostname和IP EXISTS，过滤类型/状态/环境/区域/负责人。
排序白名单所有列表可见标量列，IP列按最小规范地址排序；末尾uuid稳定排序。
分页默认25最大100，page>=1；搜索词最多256字符，环境/区域/负责人筛选值各最多128字符，sort只接受白名单值；深分页在容量范围压测，未来keyset是兼容扩展。
首页同一短读快照GROUP BY四维，宿主汇总按host_uuid；提醒按中国自然日，
warranty/expiry独立原因、总数COUNT DISTINCT uuid、排除retired，NULL不当作过期。
