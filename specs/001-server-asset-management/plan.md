# Implementation Plan: 轻量服务器资产管理系统

**Branch**: '001-server-asset-management' | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: 已记录产品决定的需求规格与项目宪法；Q12确认首版业务配置空白名单，需求清单及一致性复核见docs/design-review.md，不将设计层PASS当作解除实现暂停。

## Summary

为小规模团队建设中文桌面管理后台，提供本地账号、三角色服务端授权、四类基础设施资产、宿主机关联、导入导出、审计、概览和一致性备份恢复。采用 Django 单体、服务端渲染界面、SQLite 和 Docker Compose。

SQLite 使用单主机本地 SSD 上的 WAL、synchronous=FULL、foreign_keys=ON、BEGIN IMMEDIATE 和 5 秒忙等待。备份使用 SQLite Online Backup API；恢复使用独立控制库和不可变业务 generation，先验证候选库、保护当前数据，再原子切换，以满足审计合并、资产编号永久保留和会话失效。

## Technical Context

**Language/Version**: Python 3.12；SQLite 3.51.3 或更高的受维护版本

**Primary Dependencies**: Django 5.2 LTS、Django REST Framework 3.16、Gunicorn、HTMX 2、Bootstrap 5.3、argon2-cffi、openpyxl、xlrd、age、pytest、pytest-django、Playwright、Ruff、mypy

**Storage**: SQLite 业务库、独立 SQLite 控制库、本地 Linux 持久卷；age 加密备份；生产数据卷使用 LUKS 或等效磁盘加密，备份保管到独立故障域

**Testing**: pytest/pytest-django、契约测试、Playwright、SQLite 并发与故障注入、Ruff、mypy、迁移检查、Docker Compose 冒烟测试

**Target Platform**: Linux 服务器、Docker Compose v2；单主机 ext4/xfs；禁止 NFS/SMB 和多应用副本

**Project Type**: 中文服务端渲染 Web 管理后台与 JSON/HTMX 应用

**Performance Goals**: 在 2 vCPU/4 GiB SSD、10 万资产/100 万审计、20 个并发活跃用户和不超过 5 个写事务/s 的验证规模内，列表 p95 <1s、普通写 p95 <2s、5000 行导入 <120s

**Constraints**: SQLite 只有一个写者；WAL、FULL、外键、5 秒忙等待、有界重试；锁超时返回 503；导入逐行短事务；恢复和备份使用维护互斥；秘密不进日志或审计

**Scale/Scope**: 50 个账号、20 个并发活跃用户、10 万资产、100 万审计或 5 GiB 业务库作为首轮支持边界；超过边界或出现多机多写/HA 时评估 PostgreSQL

## Constitution Check

| 宪法门槛 | 设计响应 | 结果 |
| --- | --- | --- |
| 需求与验收先行 | 组件和接口映射 FR/SC；Q12确认配置空范围，两份清单和一致性分析通过；实现仍暂停 | PASS（需求设计） |
| 安全与最小权限 | Argon2id、服务端授权、CSRF、同源 Cookie、维护门禁、秘密禁止记录 | PASS |
| 数据完整性与可追溯 | 唯一键、外键、触发器、短事务、审计同事务、编号保留账本 | PASS |
| 分层与可维护性 | UI/API、应用服务、领域规则、数据访问、作业和迁移分层 | PASS |
| 自动化验证与可重复运维 | Compose、备份恢复验证、故障注入和收敛检查 | PASS |
| 中文与可访问性 | 中文文案、键盘焦点、标签、非颜色状态表达 | PASS |

SQLite 单写者是已知容量边界，不构成宪法违规；超出边界必须启动 PostgreSQL 迁移评估，不得默默换库。

## Phase 0: Research

研究结论见 [research.md](research.md)。

- WAL 允许读写重叠但仍只有一个写者；仅使用同一主机本地文件系统。
- 每连接开启外键、FULL 同步和 5 秒 busy timeout；应用层处理 SQLITE_BUSY 与 SQLITE_BUSY_SNAPSHOT。
- 变更使用 BEGIN IMMEDIATE，保持事务短小；导入按依赖顺序逐行提交。
- 备份使用 Online Backup API，完成 integrity_check、foreign_key_check 和业务关系检查。
- 恢复不能是文件覆盖，需控制库、generation、维护门禁、session epoch 和原子指针切换。
- Django 单体满足 MVP；未来 Agent/SSH 只预留来源和服务边界，不在首版启用。

## Phase 1: Design Artifacts

- [data-model.md](data-model.md)：账号、资产、资产关系、永久编号、审计、导入导出、备份控制状态和索引。
- [contracts/api.md](contracts/api.md)：JSON/HTMX 路由、权限、错误、导入提交、导出快照和 UI 约定。
- [contracts/file-schema.md](contracts/file-schema.md)：21列中文模板/导出、版本行、CSV无损公式防护及下载反馈。
- [contracts/audit-events.md](contracts/audit-events.md)：完整事件/动作/结果组合、可见范围及白名单。
- [contracts/acceptance.md](contracts/acceptance.md)：高风险验收及删除/迁移/状态并发的确定性结果。
- [recovery.md](recovery.md)：一致备份、候选 generation、历史合并、恢复状态机、回滚和故障注入。
- [quickstart.md](quickstart.md)：Compose 部署、迁移、管理员初始化、测试、备份恢复和 SQLite 容量验证。

## Project Structure

### Documentation (this feature)

```text
specs/001-server-asset-management/
  plan.md
  research.md
  data-model.md
  recovery.md
  contracts/api.md
  contracts/file-schema.md
  contracts/audit-events.md
  contracts/acceptance.md
  tasks.md
  quickstart.md
```

tasks.md已生成44项，本轮只同步契约和验证内容，不开始实施、不勾选实现任务。

### Source Code (repository root)

```text
app/
├── manage.py
├── config/
├── accounts/
├── assets/
├── audit/
├── operations/
├── common/
├── templates/
└── static/
tests/
├── contract/
├── integration/
├── recovery/
└── e2e/
compose.yaml
Dockerfile
Caddyfile
.env.example
```

Structure decision: 单一 Django 应用进程承载账号、资产、审计和操作模块；应用服务统一授权和业务规则；独立 worker 处理导入、导出、备份和恢复，但遵守同一维护门禁。Caddy 负责 TLS，app 和 worker 不发布宿主端口。

模块内部统一 views/serializers -> services/validators -> models/selectors；ORM 参数化查询，
排序只用白名单，模板自动转义。事务边界在services；UI、API、CLI及worker共用规则。
所有写入口先验证维护gate及当前授权，非法输入422、权限403、冲突409、忙/故障503；
用户反馈中文，日志使用稳定错误码，不暴露堆栈和原始输入。各Django app自带migrations。

### Compose 与版本升级

服务为 proxy(Caddy)、app(Gunicorn 1进程4线程)、worker(单作业执行进程)，
一次性migrate/init命令使用同一app镜像。无Redis，无独立数据库容器；SQLite卷仅app/worker可见。
worker用数据库持久job及OS文件锁领任务，恢复互斥拒绝并行恢复，重启按receipt和phase续做。
app初始mem_limit=1GiB，worker=1GiB，proxy=128MiB，parser子进程512MiB包含在worker预算；
额外并发哈希信号量限制内存峰值。生产镜像非root UID10001、cap_drop ALL、
no-new-privileges、read_only、tmpfs /tmp、pids_limit、日志轮转；仅443/必要的80发布。
目录预先按UID授权0700，secret0400，数据和备份不在静态目录；禁止特权、宿主网络及socket挂载。
镜像锁digest，Python/静态依赖锁版本；构建扫描漏洞。启动检查SQLite运行时版本及PRAGMA，
不满足则拒绝ready。TZ数据包包含Asia/Shanghai；应用事件UTC，日期提醒用指定时区。

升级流程：备份并验证 -> gate关闭且排空app/worker -> 锁定迁移 -> 新版schema/登录冒烟 -> 开放。
重大迁移先在候选generation演练并报告；迁移失败保留原generation及旧镜像一起回退，
不把新schema交给旧程序，不在多个容器启动时同时自动migrate。密钥轮换保留旧key_id解密能力。

### 测试与阶段出口

FR-001..027及SC-001..011逐项映射在quickstart.md；包括角色负例、SQLite真实文件并发
（不能只用内存数据库）、导入中断幂等、关系竞态、所有恢复phase故障注入及容量压测。
安全、数据完整性等设计响应已声明；Q12确认配置空白名单，合法SystemSetting零行及manifest空范围须
有备份恢复正例，任意未知键拒绝须有保护备份/维护/epoch前失败且原库会话可用的反例。设计层PASS与
需求文档复核均不代表代码验收或解除实现暂停；尚无程序，因此未执行功能测试或性能验证。
有实现后才可执行迁移、测试、Compose验收和speckit-converge；任何必需检查失败不得宣称完成。

## Key Decisions and Tradeoffs

### SQLite concurrency

每工作单元独立连接，CONN_MAX_AGE=0；WAL、synchronous=FULL、foreign_keys=ON、busy_timeout=5000。业务写入在短 atomic 中使用 BEGIN IMMEDIATE，唯一性、宿主关系、最后管理员保护、审计和幂等回执同一事务。版本号条件更新返回 409，锁等待耗尽返回 503 与 Retry-After。导出先物化快照再序列化，避免客户端下载持有读事务。SQLite 无 SELECT FOR UPDATE，关系和权限规则由写事务、唯一键、触发器共同保证。

### Security

账号User.version从1开始，每次实际资料/密码/首次改密标志变更递增，与只负责会话撤销的auth_version分离；
普通显示名更新只递增version，不撤销会话。账号API读取/编辑/重置均携带version，旧版本409，目标变化使确认失效。
ChangeConfirmation持久化非秘密绑定信息及高熵随机令牌摘要，消费/业务/审计/回执同业务库事务；
控制库ControlConfirmation负责备份删除/恢复，消费/领作业同控制库事务，审计跨库通过operation_uuid对账。
重启不复活已用确认，备份候选清除运行态确认；恢复与回滚epoch使旧确认无效。
通用幂等摘要只覆盖逐路由非秘密白名单；不包含密码、额外密码指纹、原确认令牌、完整引用或恢复输入候选用户名。
已完成重试只返回先前结果，不比较或应用重复提交的秘密；新秘密变更必须新键/新确认（如适用），不默默二次写入。
21列资产文件、类型适用表、审计枚举及并发验收分别以spec和三个新contracts为统一依据，测试同步引用。

FR-006/Q9区分首次登记与后续状态变更：管理员和运维编辑者新增/导入新资产可选六种初态，
只读用户禁止；后续编辑按spec完整状态矩阵授权。业务层共用状态与关系校验，不以导入覆盖既有资产，
也不因初态允许而放宽宿主机资格；测试分别覆盖首次登记、全部状态方向及关系拒绝。

FR-002/Q8将登录用户名限定为创建时设置、之后不可编辑；管理员可编辑显示名、角色和active。
账号服务及API输入白名单共同拒绝用户名/规范键变更，不能仅禁用UI输入；显示名不成为登录凭据。
恢复账号仍遵守目标备份的恢复范围，不通过改名或新增账号绕过恢复登录验证。

FR-002/Q11明确管理员新增账号的username/display_name/role/初始密码四项必填，active可选且默认true；
role不得隐式默认，客户端不能取消must_change_password，首登前改密限制在服务端执行。保留登录名及既有
规范化唯一键，只持久化安全密码哈希；输入或审计失败不产生部分账号，不将新增默认值强加给备份恢复。

FR-002/024/Q10对停用、已有角色变更和重置他人密码要求服务端验证二次确认；普通新增、显示名修改、
重新启用不额外确认。确认绑定操作者、目标状态和拟执行动作，沿用短时单次确认设计；提交重验权限及
最后管理员保护，混合请求不部分保存。新密码只在最终提交请求内存中处理，不能落入确认记录或摘要；
确认消费、账号变更与审计同事务，取消或无效确认不主动撤销目标会话，正常账号只保存安全密码哈希。

Argon2id；至少 12 字符，长口令不截断。Secure/HttpOnly/SameSite Cookie、CSRF、Origin 检查、无 JWT/localStorage bearer。每请求检查身份、active、当前角色、auth_version 和全局 session epoch。改密、重置、停用和恢复撤销旧会话。日志只含 request_id、路由、状态、耗时和非敏感错误码；审计使用字段白名单。容器非 root、只读根文件系统、无特权和无 Docker socket，密钥通过 Compose secrets。

FR-003/Q7要求已登录用户的所有授权拒绝（含查询、预览、下载）追加独立安全审计；不执行被禁止
的业务操作，不复制请求原文或秘密。该类别仅管理员可查，不能因目标是资产或操作者是编辑者而
进入编辑者的资产变更审计。审计访问拒绝也留痕，审计追加不递归触发审计；持久化失败安全失败。

### Backup and restore

Online Backup API 产生一致快照；备份完成 integrity、外键、schema、业务关系和加密认证检查后才可用。恢复采用FR-020确认的方案A：当前管理员密码在当前库验证，目标备份中的候选管理员用户名/密码在隔离候选 generation 按正常认证规则验证，允许两者不同。请求入队前完成验证，原始凭据只在请求内存中使用，不持久化；worker和重启只消费绑定目标备份、候选身份及当前操作者的服务端验证回执。凭据验证失败不创建保护备份、不暂停写入、不使现有会话失效。通过后才维护排空、保护备份、合并和替换；候选账号或回执无法复核时按阶段终止或回滚。控制库保存备份目录、维护状态、恢复阶段、generation、session epoch；恢复在候选 generation 中合并审计、永久编号和恢复事件，再原子切换。实际恢复开始即使旧会话失效；失败回滚成功后必须重新登录，回滚失败保持维护态。

### Versioning and migration

Django migrations 是唯一 schema 变更入口；生产使用锁定的迁移命令。恢复候选库先迁移到当前 schema，未知高版本拒绝。达到 SQLite 边界时冻结写入、导出一致快照、校验数量/摘要/关系/审计/编号账本后迁移 PostgreSQL；失败保留原 SQLite。

### Future extension

MVP 不实现 Agent、SSH、扫描或自动采集。资产来源保留人工/导入/未来采集枚举和 source metadata；未来受限 worker 通过应用服务和版本化契约写入，不保存 SSH 密码或私钥，不绕过授权、审计和关系规则。

## Complexity Tracking

无宪法违规，无需豁免。
