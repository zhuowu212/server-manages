# 实施后的部署与验证指南

本阶段只有设计文档；以下命令是下一阶段必须实现的运行契约，目前不声称可执行，
不创建Compose、程序、迁移或测试代码。使用隔离测试数据卷演练，禁止对生产直接跑恢复测试。

## 环境与交付

Linux本地SSD ext4/xfs、2vCPU/4GiB、Docker Engine+Compose v2、TLS域名或已信任内网证书。
准备LUKS数据卷、独立备份保管位置、age密钥及初始管理员密码文件；权限0600，不放仓库。
生产产物需交付 compose.yaml、Dockerfile、Caddy配置、无秘密.env.example、依赖锁文件。
以example中环境变量设置DATA_DIR、BACKUP_DIR、DOMAIN、ADMIN_USERNAME、secret文件路径，
不得把密码放命令参数、shell history或普通.env；Compose secrets本身不加密宿主文件。

实施后在项目根执行：
```bash
docker compose config --quiet
docker compose build --pull
docker compose run --rm app python manage.py migrate_locked
docker compose run --rm app python manage.py bootstrap_admin --password-file /run/secrets/admin_password
docker compose up -d
docker compose ps
docker compose logs --tail=100 app
```
首次初始化只允许空账号库，重复执行不改密；部署后移除初始化secret挂载。
TLS访问管理界面，首次管理员强制改密，验证日志未出现密码/引用/令牌。
首次无备份正常显示空状态；仅代理发布443，app和worker不发布宿主端口。

## 自动化命令契约

```bash
docker compose run --rm app python manage.py check --deploy
docker compose run --rm app python manage.py makemigrations --check --dry-run
docker compose run --rm app pytest
docker compose run --rm app ruff check .
docker compose run --rm app mypy app
docker compose --profile test run --rm e2e
```

## 验证矩阵

FR-002/Q11账号新增验收补充：username/display_name/role/initial_password四项必填，逐项缺失或非法输入均拒绝；
role无隐式默认，active省略默认true、显式false保持停用，新增不额外二次确认且账号/审计原子保存。
所有新增账号首次登录被限制为先改密，直接业务请求也拒绝；停用账号不能登录，启用后仍须改密。
日志、审计、错误、回执和浏览器持久存储不含初始密码；正常账号仅保存安全哈希，创建默认不重写恢复账号。

FR-002/Q8账号验收补充：管理员普通编辑包含username/username_key时返回422且没有部分账号变更；
单独合法修改display_name允许成功并留审计，用户名/规范键/UUID保持不变，新的显示名不成为登录凭据；
编辑者和只读用户不能修改资料。账号恢复行为仍按FR-019/020验证，不把正常编辑限制误作恢复障碍。

FR-002/024/Q10账号确认验收补充：停用、已有角色升降及重置他人密码测试成功、取消、缺少/无效/失效确认，
目标或拟操作变化需重新确认；拒绝不部分修改账号或主动撤销会话，混合显示名编辑也不部分保存。
新增、单独显示名修改及重新启用不额外确认；有效确认仍不能绕过最后管理员保护。
密码或密码哈希不进入确认记录、日志、审计或错误；同一幂等重试不再次执行，确认不能用于新请求重放。

本轮整改验收契约：

- 账号User.version与auth_version分离；显示名单独编辑不撤销会话，旧编辑版本409；组合角色/停用预览绑定完整actions。
- 高熵确认令牌只存摘要与非秘密元数据；确认消费、业务、审计及回执原子。重启不复活已用/过期确认，恢复/回滚不复活旧epoch确认。
- 幂等摘要从非秘密白名单生成；带不同秘密的同键已完成重试只返回先前结果，新秘密变更必须换新键/确认；不同非秘密目标/动作409。
- 四类型21字段适用表、文件版本行/精确中文表头、CSV apostrophe-v1无损往返和下载结果均以contracts/file-schema.md为准。
- 审计全部允许枚举/组合以contracts/audit-events.md为准；服务器传输完成不宣称客户端保存。
- contracts/acceptance.md的AC-CON-001..005两种并发顺序及其他高风险AC逐项留运行证据。
- Q12已确认A：SystemSetting保留零行结构、业务/DB约束拒绝任意键；manifest business_setting_keys: []的备份恢复正例，以及未知键行/非空manifest范围反例，按AC-BACKUP-001/AC-RESTORE-001验证保护备份/维护/epoch前拒绝、原库和会话可用，不清空配置绕过失败。需求整改不等于解除实施暂停。

| 要求 | 测试与证据 |
| --- | --- |
| FR-001..003,023..025 / SC-001,007,008 | 三角色UI及直接HTTP越权；查询/预览/下载及写操作的所有授权拒绝均产生仅管理员可查的安全审计；编辑者列表/详情不能读取本人或资产相关安全事件；审计访问拒绝也留痕、不递归、无输入/秘密泄露；审计写入失败安全失败；12位边界；15分钟/5次时钟冻结；CSRF；改密/降权/停用旧session失效；最后管理员并发竞态 |
| FR-004..012 / SC-002,011 | 四类型必填；Q9管理员/编辑者手工及导入新资产六种初态、只读拒绝；三角色后续完整六乘六状态矩阵及状态不变编辑；初态不扩大宿主资格，导入不覆盖既有资产；管理员宿主限制；多IP与IPv6等价/空值；Unicode大小写；曾用编号不可复用；删除审计留存 |
| FR-013,018 / SC-003,010 | 多分页静态集合无遗漏；排序白名单拒注入；四维总数；中国午夜D-1/D/D+30/D+31、退役、双日期去重 |
| FR-014..016 / SC-004 | xls/xlsx/csv；5000/5001行；20MiB及展开限额；公式攻击；文件内重复；主机在后；漏选主机；提交后断进程、重试无重复；导出快照、空结果 |
| FR-017,027 / SC-005 | 字段前后值白名单；引用、哈希、密码、token禁止；编辑者详情越权；删资产/停账号后历史仍可查；不提供审计导出 |
| FR-019,020,026 / SC-006,009 | Online Backup期间并发写；方案A两组凭据分别在当前/候选库验证、不同管理员成功、候选身份/密码/登录暂停负例；凭据不落库/不进作业或日志；绑定回执重启复核；目标及保护备份校验；旧审计和编号并集；同UUID异内容拒绝；会话epoch；空间不足；pin删除拒绝 |
| 宪法可维护性 | 空库迁移、旧版本升级、候选副本升级、受控回滚；全部模板中文标签与焦点；日志敏感字段负例扫描 |

## 恢复故障注入（必须，不是可选冒烟）

使用测试库、已知当前管理员密码和目标备份中的候选管理员用户名/密码，先备份A；新增资产B、删除A中的资产并改密后，
恢复A，验证旧管理员凭据、编号保留及新旧审计合并；B不作为资产复活但审计仍存在。
当前密码在当前库验证，候选凭据在隔离候选库按正常认证规则验证，允许与当前管理员不同。
分别测试候选不存在、停用、非管理员、暂停登录、密码错误及当前密码错误，均不得创建保护备份、暂停写入或撤销旧会话。
输入的原始凭据不出现在业务/控制库、作业载荷、日志、审计、错误响应或备份中；worker和重启只复核绑定的服务端验证回执。
逐一在 recovery.md 每个状态写入前后、fsync前后、CURRENT替换前后强制终止worker/
app/容器再重启。断电模拟需虚拟机测试磁盘，而不只进程kill。
每次保留控制phase、CURRENT、库integrity/foreign_key检查、审计UUID计数、
账号验证、epoch拒绝结果。允许结局只有完整目标、完整原库或封闭维护态，
不得无审计成功、双主写、半恢复放行或编号复用。
注入只读磁盘、ENOSPC、损坏密文、失密钥、未知schema、丢控制库、回滚失败。
手动运维恢复命令契约：
```bash
docker compose run --rm app python manage.py recovery_status
docker compose run --rm app python manage.py recovery_verify --generation UUID
docker compose run --rm app python manage.py recovery_rollback --operation UUID
```
必须使用状态报告返回的明确UUID，服务gate保持关闭；CLI遵守锁及审计，不能直接cp在线库。

## 并发与发布门槛

10万资产/100万审计、20并发客户端、5写事务/s，混合登录/检索/5000行导入/导出；
采集p95、busy率、锁等待、WAL、RSS及磁盘。目标见plan/research，报告实测机器和原始结果。
所有必需测试通过才可发布。SQLITE_BUSY导致可解释503，不等于丢数据。
备份移到独立主机后验证解密和恢复；记录恢复用时及空间峰值，不编造RTO。
实施后运行 speckit-converge，对spec/plan/tasks/代码收敛；tasks已有44项，本轮仅同步文档和验证契约，仍为0/44。
