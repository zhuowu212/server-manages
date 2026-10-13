# 架构决策与研究

日期：2026-10-08。依据 spec.md FR-001 至 FR-027 和项目宪法。
技术选型是本阶段决策，不修改业务规格。性能数值为待压测的工程目标，不宣称已验证。
主代理完成规格、宪法和模板阅读；SQLite 关键决策另行委派只读研究。

## R1 单体与成熟技术栈

Decision: Python 3.12、Django 5.2 LTS、Django REST Framework 3.16、
Django Templates + HTMX 2、Bootstrap 5.3 中文管理界面。Gunicorn 一个进程、4 个线程；
Caddy 2 负责 TLS，静态资源随镜像提供。版本补丁及镜像 digest 在实施时锁定。
Rationale: 小团队无需独立 SPA、Node 生产服务或 Redis；Django 自带账号、CSRF、
ORM、迁移、模板转义。使用自定义管理页面，不暴露 Django admin 绕过业务服务。
Alternatives: FastAPI 需要额外组装认证迁移；React SPA 增加状态与构建维护；微服务无必要。

## R2 SQLite 并发与容量

Decision: SQLite 3.51.3+，使用受维护补丁并在镜像构建和启动检查 sqlite3.sqlite_version；
Python可能链接较旧系统SQLite，必须明确构建固定版本并验证，不只检查Python版本。
单 Linux 主机本地 ext4/xfs 持久卷，
禁止 NFS/SMB、共享网络卷、多应用副本。业务库 WAL，synchronous=FULL，
foreign_keys=ON（每条连接）、busy_timeout=5000ms、wal_autocheckpoint=1000。
Django OPTIONS timeout=5、transaction_mode=IMMEDIATE，ATOMIC_REQUESTS=False，
CONN_MAX_AGE=0；每请求/工作单元独立连接，不跨线程共享。
Rationale: WAL 允许读写重叠但仍只有一个写者。写服务在短 atomic 中先读后验再写，
BEGIN IMMEDIATE 避免读事务升级写锁竞态。密码哈希、文件解析和网络 I/O 均不在写事务内。
无 SELECT FOR UPDATE 保证；版本号条件 UPDATE 防丢失更新，最后管理员保护及关系验证
在同一写事务。5s 忙超时返回 503 DB_BUSY + Retry-After，不无限重试；幂等键允许安全重试。
Alternatives: DELETE journal 读写互阻；多进程提升不了 SQLite 写吞吐；
共享一条连接产生线程与事务串扰。

Initial envelope: 2 vCPU/4 GiB SSD，50 个账号、20 个并发活跃用户、10 万资产、
100 万审计或 5 GiB 业务库以内作为首轮验证范围，持续写入目标不超过 5 个事务/s。
这是部署支持目标而非 SQLite 的理论限制。列表 p95 <1s、普通写 p95 <2s，
导入 5000 行 <120s 在约定数据集压测；后台作业与登录流量必须同测。
每个写事务目标 <100ms；审计随业务原子提交，批处理按小单元释放写锁。
监测锁等待、DB_BUSY、WAL 大小、磁盘空间、作业时间；不自动删除审计或备份。
出现持续写排队、忙错误率 >1%（15 分钟）、WAL >256MiB 无法收敛、容量超范围时
先查长读事务/索引并重测，再启动数据库迁移评估，不靠增加超时掩盖问题。
导出采用一次短读快照物化记录后关连接，再序列化，禁止慢客户端下载持有读事务。

## R3 一致备份与可恢复边界

Decision: 使用 Python sqlite3.Connection.backup（SQLite Online Backup API）生成独立快照，
绝不直接复制正在使用的 main.db 或遗漏 WAL。备份完成执行 integrity_check、
foreign_key_check、版本/业务关系检查。使用 age 加密产物（无压缩，避免解压炸弹），
manifest 与快照一起加密认证，记录 instance_id、schema_version、摘要、大小、时间。
age 公钥/私钥用 Compose secrets 文件注入；私钥不放数据库或备份。文件0600，
临时明文仅限专用0700加密宿主卷，失败与启动时清理；没有明文下载路径。
SQLite 本身不加密，生产要求宿主数据卷 LUKS 或等效磁盘加密；秘密不进日志。
Rationale: 密码哈希及凭据引用仍敏感。加密备份满足宪法的秘密保护；原始在线复制不一致。
Alternatives: VACUUM INTO 也可一致但有额外空间/阻塞取舍；cp+WAL 无可靠协调不可采用。
丢失备份私钥无法恢复，运维须独立保管密钥；整个主机/磁盘丢失不能靠同卷回滚保障，
必须下载加密备份到另一故障域并演练。MVP 不增加定时备份。
2026-10-12 Q12确认首版业务配置空白名单：保留零行SystemSetting结构，新manifest包含
business_setting_keys: []；备份/恢复校验未知键即失败，不清空配置绕过校验，具体拒绝阶段见recovery.md。

## R4 恢复不是物理文件回退

Decision: /data/control/control.sqlite 保存恢复状态、全局 session_epoch、备份目录、
作业恢复进度；业务 /data/generations/<uuid>/main.sqlite 保存业务和审计。
控制库不随业务恢复回退，也不下载给用户。单个恢复 worker 和应用共享 OS advisory gate；
控制库短事务与业务事务禁止相互嵌套锁。业务切换使用同文件系统 CURRENT 指针原子替换、
fsync 文件及目录。详见 recovery.md。
Rationale: 已确认规则要求旧审计合并、编号永不复用和旧会话失效，裸覆盖库做不到。
控制状态只协调恢复，不与业务作跨库分布式事务；缺失控制库时启动保持维护，
不自动重建 epoch 让旧会话复活。
Alternatives: 在线覆盖文件让旧连接继续读写旧 inode；只存库内作业状态会被恢复抹除。

## R5 认证和日志

Decision: Argon2id（argon2-cffi，初始 memory=64MiB、time=3、parallelism=2，
实施压测后锁定）；128 位以上随机盐由库管理。12-256 Unicode 字符密码，长口令不截断。
Django 数据库 session + 随机 opaque Cookie，Secure/HttpOnly/SameSite=Lax，HTTPS 同源；
无 JWT/localStorage bearer。CSRF 覆盖 HTMX 和 JSON，Origin 检查、CORS 关闭。
会话闲置30分钟、绝对8小时工程默认，轮换登录标识；维护 epoch + user.auth_version 每请求检查。
角色每请求读当前值，不能只信会话快照；改密/重置/停用及降权使 auth_version 增加。
失败限流按规范15分钟/5次，持久化；未知用户名也走等成本哈希及同样响应。
成功登录重置连续失败计数；额外按来源IP限流防分布式账号洪泛。
Rationale: 可立即撤销，恢复无旧会话复活。初始管理员 CLI 从 secret 文件读取，
只有空账号表允许创建；不可每次启动重置密码。
日志仅 request_id、route_name、status、duration、error_code；禁请求体、Cookie、
Authorization、完整URL查询、文件内容、密码哈希和引用。审计采用正向字段白名单，
引用变化只写 changed=true，绝不把原始对象自动 dump 入审计。
本轮技术对齐：User.version独立于auth_version；高熵确认只存令牌摘要及非秘密绑定/消费状态，
幂等request_digest只摘要逐路由非秘密白名单，不存密码等秘密的额外低成本指纹。
具体确认、幂等重试及跨库边界以data-model和contracts/api.md为准，秘密改变的重试不自动再次执行。

## R6 导入作业与未来迁移

Decision: csv 标准库、openpyxl(.xlsx)、xlrd(.xls)、xlwt 仅生成旧格式模板；
禁止执行公式/宏/外链，不依赖 Excel。格式由签名及内容验证，CSV UTF-8 BOM 可接受。
一文件一个数据表，技术限额20MiB上传、100MiB展开、100列、单元格32768字符、解析60s。
两行版本/表头结构、精确21列及CSV转义按contracts/file-schema.md；元数据与表头都不计5000数据行。
隔离无网络解析进程、内存512MiB。
部分成功以逐行事务+持久结果实现，不是整个5000行长事务。
Alternatives: Pandas 内存过重；整文件事务长期占写锁；仅内存进度会让重试重复提交。
未来迁移 PostgreSQL 仅为容量路径，不在MVP部署：冻结写入、全量一致导出、
保留UUID/规范化键/审计/编号、重建约束、数量摘要校验、切换 DSN、全量回归；
SQLite 特有触发器改写并验证，迁移失败保留原库回退。多机多写/HA要求是迁移触发点，
当前 SQLite 不提供该能力，不暗换数据库。

## 参考资料

- https://sqlite.org/wal.html
- https://sqlite.org/backup.html
- https://sqlite.org/pragma.html
- https://docs.python.org/3.12/library/sqlite3.html
- https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes
- https://docs.djangoproject.com/en/5.2/topics/auth/passwords/
- https://docs.djangoproject.com/en/5.2/topics/http/sessions/
- https://github.com/FiloSottile/age

以上为设计参考链接，未宣称本阶段完成线上文档版本验证或性能实测。

只读研究复核结论：FULL优于NORMAL用于审计持久性；多连接不增加写吞吐；旧审计及
编号保留必须是恢复叠加层；控制协调状态不得随目标快照回退。研究建议的整批事务
未采用，因为已确认合法行可单独导入；采用逐行事务与持久回执实现可解释部分成功。
