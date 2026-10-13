# 一致性备份与恢复协议

此协议落实 FR-019/020/026，必须通过故障注入后方可发布。SQLite可满足单主机、
有限停机恢复，但没有多库原子提交、无限写并发或多主机HA。文件系统须支持同卷
原子rename及fsync，磁盘损坏/丢失依赖异机保管备份，不声称本地回滚能覆盖。

## 备份

1. 管理员+CSRF校验，创建稳定operation UUID和目录占用记录，检查剩余空间。
2. 对活动库使用独立连接的Online Backup API生成临时快照；备份读完即释放连接，
   有限页复制避免长读，deadline 120s，超限明确失败。
3. integrity_check=ok、foreign_key_check为空，schema匹配、业务关系和UUID约束通过；
   清除快照中的sessions/运行态作业/ChangeConfirmation，不改变账号、资产、审计或已批准业务配置。原库不受影响。
   按spec Q12，SystemSetting保留结构但必须零行；发现任一配置行即以BUSINESS_SETTING_NOT_ALLOWED失败，
   不删除配置来使快照通过。新manifest明确business_setting_keys: []，无设置功能或默认配置行。
   清理提交后重新执行完整性、外键和业务校验，关闭快照连接后再计算最终摘要；
   manifest摘要及行数必须对应清理后的最终文件，不得沿用清理前的校验结果。
4. manifest携带instance_id/schema/app版本、摘要、行数、时间及来源；age加密整个封装，
   fsync后发布。控制目录记录成功；业务审计追加备份结果（不要求结果记录存在于此前快照）。
   启动对账处理“文件成功而审计未写”的中断，不向用户宣布成功直到审计持久化。
5. 下载需管理员授权，每次审计只记录生成/传输状态，不谎称客户端已落盘。
   删除二次确认，pin_count>0拒绝；先标删除中、移入受控隔离目录、审计后删除，
   崩溃按operation_uuid续做。空间不足不自动清理任何旧备份。
   下载/删除采用contracts/audit-events.md的阶段事件；服务器transferred不代表客户端保存。
   ControlConfirmation消费及删除控制作业入队同控制库事务，文件与业务审计以operation_uuid对账，
   不声称跨库原子。新请求重用已消费确认409；同键的已接受操作只返回原作业状态，不再次删除。

## 恢复状态机

VALIDATING -> PREBACKUP -> PREPARED -> REPLACING -> VERIFYING -> COMMITTED
失败路径：验证/保护备份失败 -> ABORTED；替换开始后失败 -> ROLLING_BACK ->
ROLLED_BACK 或 MANUAL_RECOVERY。每个phase及generation指针都持久化并fsync。

### 1. 验证与用户确认

仅选择本实例生成且目录已登记的加密备份；MVP不接受任意SQLite上传。
可通过运维CLI把从外部保管处取回的同实例包登记再验证，不执行包内程序。
先验证age认证、manifest摘要、大小、来源、允许schema；新于程序schema拒绝，
旧schema在隔离candidate副本迁移到当前版本，禁止直接开库执行未知触发器。
显式schema对象白名单/迁移签名、关闭扩展加载、trusted_schema=OFF（验证连接）、
查询超时及空间上限；再做完整性/外键/唯一性/状态检查。
业务配置空白名单同时核对manifest键范围与SystemSetting零行；任何配置键均以
BUSINESS_SETTING_NOT_ALLOWED在PREBACKUP、维护门禁和epoch变更前拒绝，不回显键或值。
旧schema迁移前也检查配置范围，不能通过隔离迁移清空配置绕过拒绝；原库及有效会话保持可用。
展示范围和时间，管理员输入当前管理员密码、目标备份中的候选管理员用户名和密码后二次确认。
current_password在当前业务库验证，候选凭据在此阶段已隔离解密并迁移的候选库验证；候选登录验证
依下文第4节规则，在进入PREBACKUP前完成。任一验证失败时，不创建保护备份、不暂停写入、不使现有会话失效。
恢复预览在控制库签发ControlConfirmation，绑定操作者auth_version/epoch、目标备份摘要及validation_id，
原令牌不存库。两组原始凭据及当前授权在请求内验证通过后，确认消费与RestoreOperation/控制回执入队同事务；
成功入队后的重试只返回同operation_uuid，不重新发起恢复，不使用秘密摘要。跨业务库的验证/审计通过回执和对账衔接，
worker在PREBACKUP前重验发起人及目标绑定；替换后的复核规则遵守下文第4节，不错误要求旧会话有效。

### 2. 保护当前数据

获取恢复互斥锁，设置“准备恢复”写入门禁，等待读写请求及后台作业到事务边界，
之后允许状态页、拒新业务操作503 MAINTENANCE；尚不撤销session。
对完全静止的当前库执行并验证自动备份，保留当前generation，pin住两份备份。
空间预算：旧库及WAL + 保护备份加密产物 + candidate + 合并审计额外空间 +
失败回滚工作空间 + 20%余量；空间不足/密码失败/取消解除门禁，旧session不主动失效。
应用所有入口、CLI写入及worker都遵守同一gate；读快照也须排空，禁止其他进程直接开业务库。

### 3. 构建候选与连续历史

从目标快照生成全新generation候选。账号/角色/资产按目标恢复，首版SystemSetting保持目标的零行结构；
构建及最终校验重复验证空白名单，发现非空配置按所处阶段终止或回滚，不部分恢复或静默清空。
冻结时刻的当前审计与目标审计按event_uuid合并；内容冲突拒绝，去重不删合法历史。
当前及目标AssetIdentity并集永久保留；同编号必须映射同一uuid。
允许目标恢复同一uuid原资产，即使它后来删除；不能新建复用旧编号。
审计中的actor/asset仅快照引用，不能把备份外账号或资产“补建”出来。
候选校验所有类型必填、宿主约束、全部标识规范化唯一性和原始摘要。
因完整历史保留，恢复后审计和身份保留表不与目标快照逐字节相等，这是规格要求。

### 4. 校验管理员可登录性

至少一个active admin、受支持的密码哈希、角色可用，拒绝无管理员的备份。
方案A（FR-020）要求在确认请求中输入目标备份中的候选管理员用户名和对应密码；按实际认证规则验证
该账号、密码、active、管理员角色及登录暂停状态，不能绕过FR-025。候选不存在、停用、非管理员、
暂停登录或密码错误均返回通用失败，验证过程不创建会话、不修改候选账号、密码或登录状态。
允许与当前管理员不同；不自动创建后门账号。当前密码及输入的候选用户名/密码只在请求内存中使用，
不写业务库、控制库、作业载荷、日志、审计、错误响应或备份。失败审计只含当前操作者、目标备份和结果。
此验证在第1节、进入PREBACKUP前完成；通过后生成服务端验证回执，绑定目标备份摘要、候选UUID/
账号编辑版本User.version、当前操作者身份/授权版本及本次操作，worker不接收原始凭据。最终激活前按回执复核
候选身份与已验证的账号认证状态一致；未改变账号的审计/编号合并不会使回执失效。
回执中的发起 session_epoch 只用于进入 PREBACKUP/PREPARED 前确认发起会话仍有权限；实际进入
REPLACING 时会按 RestoreOperation 写入新的单调 epoch，并使旧会话失效，这是预期结果，不得因旧
会话失效而错误拒绝已批准的操作。替换后及重启复核的是回执、RestoreOperation、phase 与新 epoch
的一致性，而不是要求发起人的旧 session 继续有效。
实际替换前回执失效、候选账号变化或无法复核时终止并要求重新确认，解除准备恢复门禁且保留原会话；
替换后的验证失败依第6节回滚。重启也只使用绑定的验证结果，无法验证则依阶段终止或回滚。
自动化测试使用已知fixture凭据验证实际认证通路。无法提供有效恢复后管理员凭据则不恢复。

### 5. 切换与验证

PREPARED后写控制状态REPLACING并单调增加session_epoch，fsync；此刻为实际恢复开始，
所有旧session立即无效，candidate和旧generation中的epoch也不得覆盖控制epoch。
清空candidate session/运行作业/ChangeConfirmation，关闭所有业务连接并checkpoint旧WAL；candidate目录
含独立完整库，禁止把旧库WAL/SHM配到新库。fsync候选文件与目录，原子替换CURRENT。
应用不自动重新开放服务，重连candidate，运行完整性/外键/关系/身份/审计合并检查、
内部认证探针及只读冒烟。成功把恢复事件写入candidate audit，再写控制COMMITTED，
解除门禁；用户均重新登录。状态页未认证只显示维护/可登录，不泄露备份或操作者；
详细结果重新认证管理员后查询，不保留旧会话作为例外。
全部原确认凭据也因epoch变更失效，控制库已用确认消费标记保留；回滚不复活旧会话或旧确认。

### 6. 回滚、崩溃和幂等

验证失败先写ROLLING_BACK，关闭候选连接，原子切回仍完整的old generation，
验证原库并追加恢复失败+回滚结果审计，控制状态ROLLED_BACK。epoch不减，必须
用恢复前身份重新登录。回滚失败写MANUAL_RECOVERY，保持门禁，普通业务不放行。
恢复结果UUID写控制日志（无秘密），业务不可写时待修复幂等补记，不丢恢复事件。
启动先检查控制phase与CURRENT；未COMMITTED的切换一律完成验证或回滚，
禁止仅因main.sqlite存在就放行业务。通过generation和phase检查处理：
- phase持久化前断电：旧库继续；phase=REPLACING而指针未换：回滚旧库，epoch仍有效。
- 指针换后断电：门禁不解除，重验candidate；失败回旧库。
- audit写后控制COMMITTED前断电：按event_uuid识别已写，避免重复事件。
人工恢复命令只在服务停写下操作选定generation，输出验证报告；不能删除整个data卷。
旧generation只在成功验证、加密保护备份和结果审计均存在后作为临时恢复工作文件清理；
这不删除备份目录里的任何用户备份。审计不自动清理。
