# HTTP 与 UI 契约

版本 /api/v1；同源JSON/HTMX共用application services，HTMX路由不复制授权/业务逻辑。
认证Cookie + CSRF，所有操作检查维护gate、session_epoch、auth_version、active和当前role。
权限：A管理员、E编辑、V只读。强制改密会话只可me/password/logout。
响应错误：{code,message,field_errors:[{field,code,message}],request_id}，
不回显密码、引用或原始异常；审计白名单不直接记录响应对象。
用户名和显示名长度为1–128个Unicode字符；资产搜索词最多256个字符，环境/区域/负责人筛选值最多128个字符；
page>=1、page_size为1–100，sort只能使用白名单字段，超限或格式错误统一返回422。

| 方法及路径 | 权限 | 输入/输出与语义 |
| --- | --- | --- |
| POST /auth/login | 匿名+CSRF | username/password；200 user+must_change；401通用失败，429登录暂停；密码不进URL |
| POST /auth/logout | A/E/V | 撤销session，204 |
| GET /auth/me | A/E/V | id/role/must_change，无hash/token |
| POST /auth/password | A/E/V | current_password/new_password；成功全会话失效 |
| GET /users | A | 分页账号，返回id/username/display_name/role/active/must_change_password/version，不返回密码哈希或秘密 |
| POST /users | A | UserCreate+Idempotency-Key；201创建账号及version；省略active默认true、显式false保持停用；must_change_password由服务端置true；不额外二次确认 |
| PATCH /users/{id} | A | 业务字段仅display_name/role/active；控制输入version+Idempotency-Key；停用或已有角色变更另需confirmation_id；username创建后不可修改；最后管理员保护 |
| POST /users/{id}/change-preview | A | actions[]为disable/change_role/reset_password及拟变更role/active（如适用）；reset_password单独使用；返回目标version、影响、单次confirmation_id；不接收密码 |
| POST /users/{id}/reset-password | A | new_password+confirmation_id+version+Idempotency-Key；只记录结果及新version，全会话撤销 |
| GET /assets | A/E/V | q,type,status,environment,region,owner,sort,page,page_size；items,total |
| GET /assets/identities | A | 分页曾用编号、原asset_uuid、首次使用/删除时间及是否当前存在；固定路径优先于uuid路由，不展示已删除资产敏感字段 |
| POST /assets | A/E | AssetWrite+Idempotency-Key；201 id/version；无客户端uuid |
| GET /assets/{uuid} | A/E/V | AssetRead含业务字段和version |
| PATCH /assets/{uuid} | A/E | If-Match版本+Idempotency-Key；200新版本，409冲突 |
| POST /assets/{uuid}/delete-preview | A | 目标、依赖、5分钟单次confirmation_id |
| DELETE /assets/{uuid} | A | confirmation_id+If-Match+Idempotency-Key；重验依赖与角色，204 |
| GET /imports/template?format= | A/E | xlsx/xls/csv，中文列名和模板版本 |
| POST /imports | A/E | multipart文件；202 job_id，格式/资源校验 |
| GET /imports/{id} | A或创建者且当前E | 状态、逐行预览、错误、依赖、preview_version；降为V不可沿用创建者权限 |
| POST /imports/{id}/confirm | 创建者且A/E | selected_rows[],preview_version,Idempotency-Key；202 |
| GET /imports/{id}/errors | A或创建者且当前E | UTF-8 CSV，行号/字段/错误码/原因，无敏感原值；该错误文件不采用21列资产协议 |
| POST /exports/preview | A/E | format=xlsx/csv,scope=filtered/all,filters；数量、snapshot_id |
| POST /exports | A/E | snapshot_id+Idempotency-Key；202，绑定冻结结果与权限 |
| GET /exports/{id}/download | 创建者且A/E或A | 加密暂存解密传输，链接不得仅凭UUID访问 |
| GET /audit | A/E | 时间、操作者、类型、结果、编号组合筛选；E强制asset类别 |
| GET /audit/{event_uuid} | A/E | 同列表类别控制，禁止通过详情绕过 |
| GET /overview | A/E/V | 四维统计、提醒去重总数及原因、宿主关系汇总 |
| GET,POST /backups | A | 列表/手动创建；POST带Idempotency-Key，202返回operation_id |
| GET /backups/{id}/download | A | 加密包，审计下载尝试与流结果 |
| POST /backups/{id}/delete-preview | A | 单次确认token，pin状态 |
| DELETE /backups/{id} | A | confirmation_id+Idempotency-Key；使用中409，204 |
| POST /restores/validate | A | backup_id；202检查作业及范围，终态报告包含business_setting_keys: []；非空配置拒绝，无保护备份/维护/epoch变更 |
| POST /restores/confirm | A | validation_id,current_password,candidate_admin_username,candidate_admin_password,confirmation_id+Idempotency-Key；当前密码在当前库验证，候选管理员凭据在隔离候选库验证；失败不创建保护备份、不暂停写入、不使现有会话失效，通过并确认后202 |
| GET /operations/{id} | A（导入/导出例外依当前角色及拥有者） | phase/result/error/rollback状态；仅实际恢复开始后旧会话失效，恢复前拒绝/取消不要求重新登录 |
| GET /health/live,/health/ready | 代理/监测 | liveness进程存活；ready维护时503，仅通用状态 |

UserCreate（FR-002/Q11）：username、display_name、role、initial_password必填，active为可选布尔值且默认true；
role只能显式选择admin/editor/viewer，缺失不补默认值；用户名/显示名长度及规范化唯一性沿用既有规则。
initial_password按既有12–256字符规则验证，仅在请求内存中使用并保存安全哈希，不进入回执、日志、审计或错误。
must_change_password由服务端置true，客户端不得取消首次强制改密；停用账号不能登录，启用后仍按正常认证及强制改密规则处理。
缺失必填或字段不合法返回422，规范用户名冲突返回409；新增及成功审计原子提交，失败不产生部分账号。
账号修改业务字段、确认控制元数据及重置输入分别按下述Q8/Q10校验，返回值均不含密码或哈希。

AssetWrite: name,asset_no,type,purpose,environment,owner,status,room,region,
hardware_text,serial,hostname,supplier,purchase_date,rack_date,warranty_end,expires_on,
credential_ref,host_asset_no,internal_ips[],external_ips[]。日期ISO，空可选NULL；具有资产查看/导出权限时可返回credential_ref并标注为外部引用，
审计、日志、错误响应和操作摘要不得返回完整credential_ref；
输入类型枚举与中文界面映射在同一schema。所有关键ID服务端验证，禁止任意数据库路径。
FR-006/Q9：POST /assets及导入新资产时，A/E可直接指定六种合法初态；V不得新增或导入。
PATCH已登记资产时按FR-006完整状态矩阵校验当前状态到目标状态，不能用首次登记规则绕过变更限制；
状态不变不限制A/E合法编辑其他字段。新增、编辑和导入均执行宿主机关联校验，导入重复项不得更新既有资产。
列表sort仅白名单；分页上限100；错误422字段错误、401会话无效、403越权、
404不存在、409版本/唯一性/依赖冲突、413资源限额、429限流、503维护/锁超时/磁盘故障。
已认证且当前有权的已有操作返回同幂等结果，同键不同非秘密规范操作409；秘密字段不参与摘要比较，细则见下。
业务状态改变不使用GET；授权拒绝追加安全审计不执行原业务操作。

Q8：登录用户名仅在创建账号时设置；账号PATCH不接受username或内部username_key字段，提交即返回
422 `USERNAME_IMMUTABLE`，整次账号编辑不落部分变更。管理员可按既有权限修改display_name、role、
active，display_name不改变登录用户名/规范键/UUID，也不作为登录凭据；E/V仍只能修改本人密码。
普通账号编辑的不变性规则不改变FR-019/020按目标备份恢复账号的行为。

FR-002/024/Q10：停用、已有账号角色变更（升权或降权）和重置他人密码必须先预览并二次确认；
账号新增、单独display_name修改或重新启用不额外确认，首次创建时选择角色不算已有账号角色变更。
confirmation_id作为控制元数据校验，不属于可编辑账号字段；混合请求含需确认操作时整次校验，失败不部分保存。
服务端签发的确认凭据按既有5分钟技术默认短时单次使用，绑定操作者、目标、目标当前状态及拟执行动作/role/active；
不得保存新密码或密码哈希，不得在日志/审计/错误中回显确认凭据。重置的新密码只随最终HTTPS提交请求处理并安全哈希。
缺少或格式无效确认返回422；过期、已使用、绑定不符或目标状态变化返回409并要求重新确认；
当前操作者无管理权限返回403并按Q7记录安全审计。已执行的同一幂等请求仍按既有回执返回，不再次变更。
提交时重验权限、最后管理员保护及输入规则；确认消费、账号变更与审计保持原子性，取消或拒绝不主动撤销目标会话。

账号PATCH必带version及Idempotency-Key，成功返回新version。version独立于auth_version；所有实际账号资料/密码/强制改密标志
变更递增version，显示名单独编辑不撤销会话；旧version返回409 STALE_VERSION。预览的actions[]必须精确覆盖本次敏感动作，
混合停用+角色变更以同一确认绑定整个集合及拟role/active；重置密码使用单独预览，不和PATCH混用。
actions缺失、未知动作、reset_password混用返回422；目标任一编辑使预览失效，最终仍重验权限和最后管理员保护。
确认采用data-model的ChangeConfirmation持久化消费状态，令牌原文不存库；重启不清除已消费标记，不因重启延长5分钟有效期。

通用写入回执只摘要路由白名单非秘密字段，排除initial_password/current_password/new_password/password、
密码哈希、令牌、私钥、完整credential_ref、恢复输入候选用户名和原confirmation_id；禁止先dump请求再脱敏。
同键且非秘密操作匹配的已完成重试返回原结果及replayed=true，不重验或应用新提交的秘密；界面提示“返回先前结果，未再次执行”。
202已接受作业同键重试返回同operation_id/作业状态，不创建第二个作业；204及异步响应以Idempotency-Replayed响应头表示重试，
有JSON正文的同步结果可带replayed=true。各列出的Idempotency-Key缺失/非法返回422，不把密钥用作URL参数或日志字段。
改变非秘密目标/动作/拟值返回409 IDEMPOTENCY_CONFLICT；新的密码/引用变更必须换新键，需确认的还必须重新预览。
当前身份/权限校验先于回执读取；回执查找先于已消费确认和旧version拒绝，避免把已成功请求误报为重放失败。
本人改密及登录/退出不用通用回执；任何回执均不得存储秘密内容或秘密的额外低成本指纹。
账号/资产变更用业务OperationReceipt；备份创建/删除及恢复入队使用ControlReceipt（同字段及摘要规则），
确认消费/作业入队/ControlReceipt同控制库事务。后台终态与业务审计按operation_uuid对账，不声称跨库原子。

已认证用户的授权拒绝统一返回403并追加 `category=security`、`action=authorization_denied`、
`result=denied` 安全审计，覆盖上述资产、账号、导入导出、审计和备份恢复入口，包括查询、预览、下载。
只记录服务端身份、操作类别、经校验的非秘密目标标识和拒绝结果；不得复制请求体、URL查询、
文件名/内容或原始错误对象。拒绝不执行原业务操作。`security` 类别仅A可读取，E的列表/详情
即使涉及本人或资产也拒绝；该拒绝本身须留安全审计，但追加事件不递归触发新的审计。
未认证/会话失效仍返回401；登录失败/暂停依FR-025处理，不混同为已登录用户的越权拒绝。
审计持久化失败按503安全失败处理并记录非敏感故障码，不宣称已成功留痕，原业务仍不执行。

## 恢复确认（方案 A，FR-020）

首版业务配置按FR-019/Q12为空：合法快照SystemSetting零行、新manifest的business_setting_keys为[]。
验证及确认均重验空范围，旧schema迁移不能删除配置来通过；非空配置在PREBACKUP、维护门禁和
会话失效之前拒绝，原库及有效会话保持可用，不部分恢复。同步确认返回422 BUSINESS_SETTING_NOT_ALLOWED，
异步验证作业终态failed并带同error_code；更早的包认证/完整性失败仍使用相应错误码。
反馈为“备份包含首版不支持的业务配置，无法恢复”，不回显配置键或值，审计仅安全失败码和目标备份。
备份发布也验证空范围；无设置管理路由、页面或默认配置项。

current_password验证当前会话所属管理员；candidate_admin_username/candidate_admin_password验证
目标备份中的有效管理员，允许与当前管理员不同，遵守正常登录暂停规则。验证失败返回通用
RESTORE_CREDENTIALS_INVALID（422），不透露候选账号是否存在；当前角色/session不合规则仍按401/403拒绝。
两个密码和输入的候选用户名仅由确认请求内存处理，不写入作业载荷、业务/控制库、请求日志、
审计、错误响应、备份，不通过URL/命令参数传递。校验过程不为候选账号创建会话或修改账号/密码。
请求在入队前完成两组验证；worker接收服务端验证回执和非敏感操作标识，回执绑定目标备份摘要、
候选管理员UUID/账号验证版本、当前操作者UUID/auth_version/session_epoch及本次操作，客户端不能自行构造。
候选发生变化、回执失效或替换前无法复核时，保持原库并要求重新确认；不通过保存密码来支持重启。
只有验证和二次确认通过，才进入维护排空、保护备份和后续替换；失败审计只记录当前操作者、目标备份和结果。

## 导入提交与结果

预览文件hash+schema_version+normalized_payload绑定不可变job，客户端只能选行不能篡改值。
同文件规范化唯一值冲突的所有行都报错，不采用“第一行赢”；和已有记录重复拒绝不更新。
解析全文件构建host编号映射，不依赖行序；提交先已选合法物理机，再虚拟机，
最后其他无依赖资产。主机未选择且未存在则虚拟机不提交。
每行BEGIN IMMEDIATE：重新授权/验证/版本 -> identity+asset+IPs+审计+行结果一起提交。
一行异常仅该事务回滚并另写失败结果；磁盘/审计不可用则停止剩余行，状态INTERRUPTED，
已提交行可查询，不能宣称全部失败或自动撤回成功行。重启按行receipt续做，不重复插入。
依赖宿主提交失败则虚拟机DEPENDENCY_FAILED，其他行继续。
确认前后角色变化重新授权；恢复门禁使作业暂停，在重新认证并授权后显式继续。
结果各行只取一个终态：success/error/skipped；duplicate是error的原因，不重复计数。
输出成功/错误/跳过及重复子计数、未处理计数，总和与选择行数可核对。

## 文件与导出

列协议版本1以[file-schema.md](file-schema.md)为唯一依据，完整21列与AssetWrite一一对应；
第一行模板版本/文本转义元数据、第二行精确中文表头、第三行起数据。宿主机填资产编号，IP列表用分号，
日期YYYY-MM-DD；CSV标准引号/换行规则，UTF-8 BOM可选，错误行号为实际文件记录/Excel行号。
Excel仅一个非空数据sheet，公式单元格拒绝而非读取缓存值；数值型编号要求用户改为文本，
避免前导零损坏。模板无宏。export xlsx单元格强制字符串，CSV危险公式前缀采用
显式文本转义（apostrophe-v1）并在元数据及导出说明列出；此类CSV再导入须按版本规则无损还原，做往返测试。
敏感引用可存在资产文件，不能进入审计；导出条件只允许已知非秘密搜索字段。
导出预览物化完整快照，返回并回显scope、规范化q/type/status/environment/region/owner、格式、冻结时刻/数量及中文列清单；
sort在有指定时回显但不改变命中集合，忽略page/page_size。确认过期返回409要求重做，不静默换数据集。
无结果422 NO_EXPORT_DATA不生成文件；生成、传输中断和客户端未知结果区分。
确认前关闭预览不创建导出作业或成功审计；不新增后台取消作业功能。服务端收到下载请求后记录传输开始/完成/中断，
开始响应前失败返回结构错误；响应已开始后的中断不得补写伪成功。HTTP发送完成仅表示服务器传输完成，客户端是否保存标记unknown。
浏览器取消保存框若服务器无法观测，不伪造cancelled审计，中文提示可重新下载；已生成产物保留到既有24小时期限。
导出/audit组合枚举及各结果的精确中文含义见[audit-events.md](audit-events.md)，失败与取消验收见[acceptance.md](acceptance.md)。
临时产物权限0600、加密暂存24h；工人删除临时产物不删除备份或审计。

## UI

首屏登录或资产概览，无营销页。导航：概览、资产、导入导出、审计（按角色）、
账号及备份恢复（仅A）。中文表格密集可扫描；键盘可操作、标签/焦点明确，
反馈不只依赖颜色。详情含身份、类型字段、地址、宿主/虚拟机列表、审计入口。
破坏性弹窗显示目标与影响，确认凭据绑定对象版本，一旦变化重新确认。
系统维护页仅通用状态，重新登录后管理员查看详细报告。UI隐藏按钮不是授权。
