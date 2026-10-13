# 审计事件与结果协议

依据：FR-003、FR-017、FR-019/020/026/027及Q7。枚举字符串是技术编码，界面使用下列中文含义。
数据库迁移与业务校验须拒绝未登记category/action/result组合，不能让自由文本扩张审计可见范围。

## 完整事件矩阵

| category | action | 触发范围 | 允许result | 可见角色 |
| --- | --- | --- | --- | --- |
| asset | created | 手工或成功导入新增资产 | success/rejected/failed | 管理员、编辑者 |
| asset | updated | 普通字段、类型或宿主迁移；状态不变 | success/rejected/failed | 管理员、编辑者 |
| asset | status_changed | 后续状态变更，可含其他字段变更 | success/rejected/failed | 管理员、编辑者 |
| asset | deleted | 彻底删除尝试 | success/rejected/failed | 管理员、编辑者 |
| authentication | login | 登录验证 | success/failed | 仅管理员 |
| authentication | login_throttled | 第5次连续失败及暂停期请求 | rejected | 仅管理员 |
| authentication | logout | 已认证退出 | success/failed | 仅管理员 |
| authentication | password_changed | 本人改密，含首次强制改密 | success/rejected/failed | 仅管理员 |
| account | user_created | 管理员新增或部署初始化 | success/rejected/failed | 仅管理员 |
| account | user_updated | 显示名修改或重新启用 | success/rejected/failed | 仅管理员 |
| account | user_disabled | 停用账号 | success/rejected/failed | 仅管理员 |
| account | role_changed | 已有账号角色升降 | success/rejected/failed | 仅管理员 |
| account | password_reset | 管理员重置他人密码 | success/rejected/failed | 仅管理员 |
| import | previewed | 上传、解析及预览校验 | success/rejected/failed | 仅管理员 |
| import | executed | 确认入队及最终行结果 | started/success/partial/failed/interrupted | 仅管理员 |
| export | previewed | 范围和冻结快照预览 | success/rejected/failed | 仅管理员 |
| export | generated | 生成导出文件 | started/success/failed | 仅管理员 |
| export | downloaded | 一次下载请求及传输 | started/transferred/failed/interrupted | 仅管理员 |
| backup | created | 手动或恢复前保护备份 | started/success/failed | 仅管理员 |
| backup | downloaded | 一次加密备份下载及传输 | started/transferred/failed/interrupted | 仅管理员 |
| backup | deleted | 备份文件删除尝试 | success/rejected/failed | 仅管理员 |
| restore | validated | 目标包、兼容性及凭据验证 | success/rejected/failed | 仅管理员 |
| restore | restored | 准备恢复、切换及最终结果 | started/success/aborted/rolled_back/recovery_required | 仅管理员 |
| security | authorization_denied | 所有已登录用户的授权拒绝，含读/预览/下载及受限审计访问 | denied | 仅管理员 |

只读用户不能读取任何审计。非管理员的业务类别越权仅写security事件，不再写编辑者可见的asset失败事件。
编辑者违反其状态方向属于授权拒绝；非法枚举、无效关系、版本冲突属于业务校验拒绝，写对应asset事件。
授权拒绝仅保存安全身份/类别/目标/结果，不复制请求或查询。未登录401不伪装成已登录403。

## 结果及阶段语义

| result | 中文含义及判定 |
| --- | --- |
| started | 服务端已接受并开始相应阶段，不代表最终成功 |
| success | 该阶段完成并持久化必需审计；导出仅表示文件生成，恢复表示全部验证通过 |
| rejected | 已授权请求被输入、版本、关系、最后管理员或确认规则拒绝，业务未变更 |
| denied | 服务端授权拒绝，仅security使用，原业务不得执行 |
| failed | 认证不通过，或技术故障导致阶段失败；失败摘要说明安全错误码及无部分变更/已提交行 |
| partial | 导入已完成，但选择行同时存在成功与错误/跳过；计数可核对 |
| interrupted | 导入仍有未处理行，或服务器观察到下载流中断；不得报全部失败或全部完成 |
| transferred | 服务器发送完成，不证明客户端落盘；client_saved固定unknown |
| aborted | 实际替换开始前取消或检查/自动备份失败，原数据和有效会话不主动失效 |
| rolled_back | 实际替换开始后失败且已验证回滚到完整原库；旧会话仍无效 |
| recovery_required | 回滚/验证无法完成，保持维护，须人工恢复 |

客户端不可观测的本地取消不产生cancelled事件；服务器收到但拒绝的确认按rejected处理。
导入duplicate仅为error原因/子计数；预览错误不伪装为执行失败。
第5次错误登录同时追加login/failed和login_throttled/rejected；暂停期正确或错误密码均仅报告暂停。
开始与终态分别追加不可变事件，event_uuid不同但operation_uuid相同，不UPDATE“进行中”审计。
同一已提交幂等重试不再追加逻辑成功事件；真正新的下载尝试仍产生新传输事件。

## 字段白名单与原子性

- 基础字段：event_uuid、instance_id、time_utc、服务端actor_uuid及名称快照、asset_uuid及编号/名称快照、
  category/action/result、request_id、operation_uuid。账号操作的目标UUID/用户名快照在允许summary中保存。
  对不存在/未知登录名的失败不复制输入用户名，以内部限流键或非秘密未知目标标记处理。
- 资产before/after白名单：name、asset_no、type、purpose、environment、owner、status、room、region、
  hardware_text、serial、hostname、supplier、purchase_date、rack_date、warranty_end、expires_on、
  host_asset_no、internal_ips、external_ips。普通值原样留痕；IP集合规范化后稳定排序。
  新增before=null，删除after=null；迁移是updated。混合状态及其他字段变更用status_changed，并包含全部允许变化。
- account前后值只允许display_name/role/active/must_change_password；密码只记录动作及changed=true。
  同一次混合显示名/角色/停用按实际动作分别追加user_updated/role_changed/user_disabled事件，
  共用operation_uuid、同一事务提交，以支持按动作筛选；禁止把密码/哈希塞入前后值。
- summary按类别选取目标ID、字段名、changed布尔、安全错误码、计数、格式、范围、冻结时间、
  备份来源/标识、恢复前后范围及回滚状态。成功导出的条件仅允许规范化q/type/status/environment/region/owner，
  不记录原URL、未知参数、文件内容或引用。失败行只记录行号/字段/安全原因码，不记录上传原值。
- password/hash/token/private_key、原confirmation_id及完整credential_ref禁止进入任意字段；
  引用变化只保存字段名和changed，不以“脱敏摘要”为由保存其内容或额外指纹。
- 成功变更、确认消费、回执和审计同业务库事务；拒绝/失败在变更回滚后用独立短事务写事件。
  审计不可用返回503并保留非秘密故障码，不宣称业务成功，也不谎称已成功留痕。
- 备份文件发布/删除、恢复控制库与业务库无跨库事务；以稳定operation_uuid和恢复协议对账。
  不得向用户宣布成功直到必需审计持久化。审计不可修改/删除；恢复按event_uuid合并，ID同内容不同拒绝。

扩展枚举需要同时更新本文件、迁移、规格引用、API筛选白名单、任务和测试；不能用无约束字符串规避评审。
