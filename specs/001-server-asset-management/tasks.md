---
description: "服务器资产管理 MVP 实施任务与验证门槛"
---

# Tasks: 轻量服务器资产管理系统

**Input**: 本目录 spec.md、plan.md、research.md、data-model.md、contracts/api.md、contracts/file-schema.md、contracts/audit-events.md、contracts/acceptance.md、recovery.md、quickstart.md；项目宪法 v1.0.0。
**Tests**: 用户及宪法要求自动化测试，所有测试任务必做。先编写并记录因功能未实现而失败的测试，再实现；最终必须通过。
**Organization**: Setup → Foundational → US1/US2/US3/US4 → 跨功能验收。路径均相对仓库根。
**Format**: `- [ ] Txxx [P?] [USn?]`。依赖栏列出全部直接前置任务，包含其传递依赖；`[P]` 只表示前置完成后可与同批不同文件任务并行。
**Readiness**: 自定义清单 checklists/requirements-review.md 的26项仍由评审者持有，未勾选不代表实现失败，也不能自动视作通过。实施开始前处理该门槛；本文件不修改任何清单标记。规格优先于较早的方案。
**Current Review**: 2026-10-12在用户授权的clarify中完成需求质量复核：内建18/18、自定义26/26，接受Q12后的一致性分析无未解决Critical/High；详见docs/design-review.md。实施暂停仍有效，T001保持未勾选，恢复实施后先核对文档版本及复核证据。

## Phase 1: Setup

目标：可重复构建的 Django/Compose 骨架与测试工具。

- [X] T001 校齐后续澄清与设计文档：在 specs/001-server-asset-management/data-model.md、contracts/api.md、recovery.md、quickstart.md 中落实管理员专属编号保留查询、类型切换、概览排序、备份排除范围、恢复候选管理员凭据验证、输入长度限制及导入限制；逐项记录已有技术默认与已确认业务的区别，执行 speckit-analyze 并将结果纳入设计评审，提交 checklists/requirements-review.md 给评审者，不替其勾选。依赖：无；验证：形成 docs/design-review.md 的差异表、需求引用、分析问题及未解决冲突列表；Critical/High冲突未解决不得开始对应实现。
  本轮整改补充：核对独立User.version、持久化确认、非秘密幂等摘要、三份contracts及Q12空配置结论；以docs/clarification-changes-2026-10-12.md记录变更。2026-10-12需求清单及新一致性复核已通过；T001在恢复实施后核对现行版本和评审证据才能勾选，T002仍依赖T001；文档整改不解除实现暂停。
- [X] T002 建立 app/manage.py、app/config/、app/accounts/、app/assets/、app/audit/、app/operations/、app/common/、app/templates/、app/static/ 和 tests/ 骨架，配置 pyproject.toml、依赖锁、AUTH_USER_MODEL 与开发工具；锁定 Python 3.12、Django 5.2 LTS、DRF 3.16、HTMX 2、Bootstrap 5.3、argon2-cffi、openpyxl、xlrd、xls模板写入依赖、age、pytest/Playwright/Ruff/mypy。依赖：T001；验证：依赖安装、Django check、测试收集与静态检查可运行，账号首次迁移前已选定自定义用户。
- [X] T003 [P] 建立 Dockerfile、compose.yaml、Caddyfile、.dockerignore、.env.example：proxy/app/单worker、TLS、SQLite本地持久卷、secret文件、UID10001、只读根、cap_drop ALL、no-new-privileges、tmpfs、资源限制及日志轮转；固定镜像digest与SQLite运行时版本。依赖：T002；验证：Compose配置校验、构建成功、无默认密码、仅代理发布端口、无特权或Docker socket。
- [X] T004 [P] 建立 tests/conftest.py、tests/fixtures/、playwright.config.ts 与测试依赖锁，提供隔离文件SQLite、冻结时钟、故障注入夹具及三角色工厂接口；Ruff/mypy/pytest/Playwright统一命令写入 docs/testing.md。依赖：T002；验证：测试可收集、夹具契约可用、运行不触碰生产卷；角色工厂在T014后实例化。

## Phase 2: Foundational

目标：业务开始前具备数据库、控制状态、审计、事务、错误和测试基础。

- [X] T005 编写 tests/integration/test_foundation.py 与 tests/recovery/test_control_bootstrap.py 的数据库、日志秘密排除、维护锁、控制库丢失和审计原子性测试。依赖：T003,T004；验证：真实多连接文件库用例可重复运行，未实现行为先失败。
  增补AC-CONFIRM-001/AC-SECRET-001：确认消费/变更/审计/回执的提交与故障回滚、重启消费状态和到期、秘密排除摘要输入、同键返回原结果不重做、新键复用确认拒绝；审计枚举/组合非法值必须被数据库拒绝。
- [X] T006 实现 app/config/settings.py、app/common/db.py、app/common/errors.py、app/common/logging.py：SQLite 3.51.3+、WAL、FULL、foreign_keys ON、busy_timeout=5000、wal_autocheckpoint=1000、timeout=5、IMMEDIATE、ATOMIC_REQUESTS=False、CONN_MAX_AGE=0；请求/工作单元独立连接，忙错误503/Retry-After、版本冲突409、字段错误422、权限403；UTC事件及Asia/Shanghai日期。依赖：T005；验证：每连接PRAGMA断言、运行时不达标拒绝ready、无请求体/秘密/堆栈泄露，事务内不做解析或密码哈希。
- [X] T007 建立 app/operations/control_models.py、app/operations/migrations/、app/operations/gate.py、app/common/generations.py，并建立业务库 SystemSetting 模型及迁移：独立控制库、BackupCatalog/pin_count、RestoreOperation/phase、SessionEpoch、maintenance、CURRENT；业务配置只保存可恢复的应用内配置，不保存部署路径、证书、加密密钥、密码、令牌或会话；初始化和丢失区分、OS共享/独占门禁、读写排空、控制/业务库不嵌套持锁。依赖：T006；验证：空部署成功初始化，既有部署控制库缺失保持维护，app/worker/CLI共同服从门禁，业务配置可迁移且不越界进入控制库。
  Q12已确认A：首版配置键白名单为空，SystemSetting保留结构、无默认行；业务层拒绝任意键，数据库CHECK(0)保证零行，直接DB写入及含配置的升级迁移失败，不新增设置功能/API。备份与恢复使用空范围并拒绝未知键。
- [X] T008 建立 app/audit/models.py、app/audit/services.py、app/audit/migrations/：event_uuid PK、instance_id、UTC时间、可空actor_uuid/asset_uuid、身份名称编号快照、category/action/result、request_id/operation_uuid、白名单before/after/summary；无级联历史删除，禁止审计UPDATE/DELETE。依赖：T007；验证：普通字段保留原值；password/hash/token/private_key/完整credential_ref不入任何审计字段；敏感变化仅动作/changed；业务和审计同事务，写入失败回滚。
  完整枚举及组合CHECK严格采用contracts/audit-events.md；混合账号操作同事务多事件共享operation_uuid，started和终态追加新event_uuid，不修改旧事件；下载transferred不等于客户端保存。
  补充FR-003/Q7：已登录用户所有授权拒绝写security/authorization_denied/denied安全事件，含查询/预览/下载；仅管理员可查，不执行原业务，不复制请求原文或秘密；拒绝审计访问也留痕，追加不递归，持久化失败安全失败。
- [X] T009 建立 app/common/models.py、app/common/migrations/、app/common/receipts.py、app/common/confirmations.py、app/common/normalization.py、app/operations/jobs.py、app/operations/management/commands/run_worker.py：OperationReceipt及业务ChangeConfirmation，补充control_models.py/控制库迁移的ControlConfirmation；actor+幂等键唯一、不同非秘密请求摘要409、UUID回执、version条件更新、trim+casefold规范键、IP实际地址键、单worker持久领任务、重启恢复与清理。依赖：T008；验证：T005增补通过；随机令牌只存摘要，确认消费/业务/审计/回执同事务、重启不复活；密码/哈希/原令牌/完整引用不参与摘要，相同非秘密操作的已完成重试只返回原结果；worker并发领用互斥、维护时停到事务边界，无未授权自动重放；控制确认只与控制作业原子，不声称跨库事务。
  控制库增补ControlReceipt：备份/恢复确认消费、控制作业入队及回执同控制库事务；幂等重试返同operation_id，204使用Idempotency-Replayed头；原令牌仅其摘要进入确认表，回执只存内部confirmation_uuid引用。
- [X] T010 实现 app/common/management/commands/migrate_locked.py、app/common/management/commands/recovery_status.py 和数据库路由：受控迁移、业务/控制库独立版本、初始化与维护锁、禁止多容器自动迁移。依赖：T009；验证：空库和重复初始化、makemigrations --check；生产既有数据升级的保护备份和候选验证由T034/T036/T037的升级流程负责，不把后续任务作为T010完成前置。

Checkpoint：T005-T010全部完成并通过；数据库、控制状态、业务配置零行结构与校验、审计与作业原语就绪。全体故事依赖T010。

## Phase 3: User Story 1 - 登录并按角色管理资产 (P1)

目标：本地账号、三角色授权及账号安全。
独立验收：账号夹具验证登录、登出、改密、锁定、账号管理、最后管理员保护与权限策略；真实资产/导入/恢复路由矩阵在T039补齐，不把策略测试冒充全系统验收。

### Tests

- [X] T011 [P] [US1] 编写 tests/integration/test_authentication.py：正确/错误/未知账号、用户名/显示名长度边界、初始化、首次强制改密、11/12/长口令、15分钟5次失败及锁定15分钟、暂停期正确密码、CSRF、Cookie、撤销会话。依赖：T010；验证：SC-001/008、FR-001/023/025的正反例先失败。
  补充FR-002/Q11：管理员新增账号首次登录只能进入改密流程，直接业务请求被服务端拒绝；显式停用的新账号不能登录，启用后仍须改密；使用不同的合法新密码完成本人改密后初始密码及旧会话无效。
- [X] T012 [P] [US1] 编写 tests/integration/test_account_authorization.py：三角色资料修改边界、重置/停用/降权、最后管理员并发保护、敏感日志与账号拒绝审计。依赖：T010；验证：FR-002/003/017/024、SC-007负例与事务竞态先失败。
  补充Q7：账号列表查询及写操作的授权拒绝均留安全审计；只存安全元数据、原业务不执行，安全审计持久化失败明确报告，未认证401与越权403分开验证。
  补充FR-002/Q8：管理员提交username/username_key变更返回422，混合显示名变更不部分保存；显示名可单独合法修改并审计，登录名/规范键/UUID不变，显示名修改不新增或替换登录用户名；E/V资料编辑仍拒绝。
  补充FR-002/024/Q10：停用、已有角色升降、重置他人密码须有效二次确认；取消/缺少/伪造/过期/已用/目标或动作不符/目标变化均不变更账号或主动撤销会话，混合普通字段不部分保存；确认不能绕过最后管理员保护；新增、显示名单独修改、重新启用不额外确认，确认记录及日志审计无新密码/密码哈希。
  补充Q11：新增四项必填逐项缺失、非法role/active、规范用户名冲突、密码不合格及审计失败均无部分账号；active省略为true、显式false保持停用，role省略不默认，首次改密标志不可由客户端关闭；创建动作/结果留审计但不记录密码或哈希，E/V直接创建均拒绝。
  增补AC-ACCOUNT-001/AC-CONFIRM-001/AC-SECRET-001：独立User.version覆盖显示名/role/active/密码/强制改密标志，旧编辑版本409；显示名不撤销会话；组合actions[]确认精确绑定；消费及审计故障回滚；已完成重试带不同密码仍仅返回原结果，新秘密变更要求新请求。

### Implementation

- [X] T013 [US1] 创建 app/accounts/models.py、app/accounts/migrations/：User(uuid、username、username_key UNIQUE trim+casefold、display_name、password_hash、role admin/editor/viewer CHECK、active、must_change_password、version从1开始、auth_version、created_at)、LoginAttemptState(normalized_login_key、window_start、consecutive_failures、locked_until)；绝不存输入密码。依赖：T011,T012；验证：账号规范键唯一和角色约束、编辑version与会话auth_version分离、空库迁移，自定义模型成为会话与审计的身份来源。
  补充Q8：登录用户名/username_key在创建后对普通账号编辑不可变，display_name和登录标识分离，不将普通编辑限制误用于FR-019/020的账号恢复。
- [X] T014 [US1] 实现 app/accounts/passwords.py、app/accounts/sessions.py、app/common/authorization.py：Argon2id 64MiB/t3/p2初始值及并发内存限制、12–256字符不截断、opaque session、Secure/HttpOnly/SameSite、CSRF/Origin、闲置30分钟/绝对8小时技术默认、每请求当前role/active/auth_version/外部epoch检查。依赖：T013；验证：等成本未知账号失败、限流持久化、改密/重置/停用/降权撤销，安全默认不当作新增已确认业务要求。
- [X] T015 [US1] 实现 app/accounts/services.py、app/accounts/views.py、app/accounts/serializers.py、app/accounts/urls.py、app/accounts/management/commands/bootstrap_admin.py：登录登出、本人改密、管理员新增/编辑/停用/分配角色/重置，空账号库初始化secret且首次改密；强制改密限制业务访问，最后管理员保护和审计同事务。依赖：T014；验证：T011/T012通过，重复初始化不重置密码，其他角色只能改本人密码，拒绝账号操作记录安全审计。
  补充Q8：账号可编辑业务字段白名单只含display_name/role/active及既有版本字段；包含username/username_key时422拒绝整次编辑，服务端及业务服务共用规则，确认控制元数据另行校验。
  补充Q10：实现账号change-preview与确认消费，绑定操作者/目标当前状态/动作及role/active，复用短时单次确认与幂等回执设计；密码不进入预览或确认记录，仅最终提交安全哈希；混合变更、确认消费及审计同事务，重验权限和最后管理员保护。
  技术对齐：实现actions[]组合预览（reset_password单独使用）、User.version读取/条件更新与确认失效；复用T009确认持久化/回执，先授权、再查已完成回执、再验证未用确认及版本；密码哈希在短写事务外计算、事务内重验绑定。所有实际账号字段/密码变更递增编辑版本，不用auth_version代替。
  补充Q11：新增业务输入白名单为username/display_name/role/initial_password及可选active，四项必填；active省略默认true，role无默认，must_change_password服务器置true，密码安全哈希后账号与审计原子保存；保留显式停用和既有初始化/恢复边界，不持久化初始密码或将创建默认值用于恢复。
- [X] T016 [US1] 构建 app/templates/base.html、app/templates/accounts/、app/static/accounts.js 和 tests/e2e/test_accounts.py；接通认证路由及按权限导航，中文标签/焦点/错误，停用等破坏性变更二次确认。依赖：T015；验证：浏览器登录/改密/账号管理主路径及直接请求负例通过，隐藏按钮不替代服务端授权。
  补充Q8：用户名编辑界面只读并标明创建后不可修改，显示名按管理员权限可改；浏览器篡改请求仍被拒绝，合法显示名修改不改变登录标识。
  补充Q10：仅停用、已有角色变更和重置他人密码显示目标/动作/影响二次确认；新增、显示名单独修改和重新启用正常提交。取消不变更，直接绕过弹窗的请求仍由服务端拒绝，失败不部分保存；本人改密继续验证当前密码。
  补充Q11：新增表单明确四项必填和可选启用状态、默认启用；角色必须主动选择且无预选默认，初始密码不入URL或浏览器持久存储；首登改密、显式停用和字段错误浏览器验收与直接请求一致。

Checkpoint：US1账号闭环可演示；真实跨故事授权尚需T039。

## Phase 4: User Story 2 - 维护和查找资产 (P1)

目标：四类型资产、生命周期、关系、查询和删除闭环。
独立验收：已知四类型六状态集合的CRUD、唯一性、关系阻塞、搜索排序分页、原子审计和两用户冲突全部符合SC-002/003/007/011。

### Tests

- [X] T017 [P] [US2] 编写 tests/integration/test_asset_rules.py：必填、可选空值、规范化唯一/复用、全部状态边、类型切换、日期、多IP、凭据禁止字段。依赖：T016；验证：FR-004..010及SC-002/011的参数化正反例先失败。
  类型适用性逐字段覆盖FR-008完整21字段四类型表；virtual序列号、network/storage主机名可选，切换保留仍适用值，非virtual宿主必须显式清空，失败原数据不变。
  补充FR-006/Q9：A/E可分别手工创建六种初态，V全部拒绝；三角色后续六乘六状态组合按spec完整矩阵验证，状态不变仍按编辑权限判断，首次登记不放宽宿主机资格。
- [X] T018 [P] [US2] 编写 tests/integration/test_asset_relations_queries.py：主机六状态、子机迁移、删除/修改并发、管理员关系限制、版本冲突、分页稳定性、取消删除、删除审计历史。依赖：T016；验证：FR-009/011..013、SC-003/007先失败，使用真实SQLite连接而非内存锁模拟。
  并发必须逐项执行contracts/acceptance.md的AC-CON-001..005两种提交顺序；断言409 STALE_VERSION/RELATION_CONFLICT/DEPENDENCY_CONFLICT与503忙错误的区别、没有孤儿/丢失更新、失败确认未消费及成功方结果不被回滚。

### Implementation

- [X] T019 [US2] 创建 app/assets/models.py、app/assets/migrations/：AssetIdentity(normalized_asset_no PK、asset_uuid UNIQUE、first_seen、last_deleted_at，永久保留)、Asset及AssetAddress(ip_key UNIQUE、scope internal/external、asset FK CASCADE)；采用data-model.md原文限制“名称/编号/序列号255，主机名253，环境/区域/机房/负责人128，用途4096，硬件描述16384，凭据引用2048；空可选值转NULL”；主机/序列当前资产唯一，编号永久唯一。依赖：T017,T018；验证：迁移、唯一键/索引、NULL重复、删除后编号禁止复用而其他标识可复用，历史身份不串联。
- [X] T020 [US2] 实现 app/assets/validators.py、app/assets/lifecycle.py、app/assets/relationships.py 及约束迁移：通用必填name/no/type/purpose/environment/owner/status/room/region；physical必填serial+hostname，virtual必填hostname+host，network/storage必填serial；其余可选，非virtual host必须NULL，类型切换不适用值未清空则拒绝；host FK RESTRICT且physical/status in(racked,active,repair)，有子机禁改为无效类型/状态；rack>=purchase（两者非空时）；editor仅planned→purchased→racked→active、active→repair/retired、repair→active，admin受关系约束；依FR-006/Q9区分A/E新增六种初态与后续完整角色状态矩阵，V禁止写入，不能借首次登记覆盖既有资产。依赖：T019；验证：T017规则断言通过、数据库绕过服务也拒绝孤儿/无效宿主；IPv4-mapped归一和zone_id拒绝遵循设计。
- [X] T021 [US2] 实现 app/assets/services.py、app/assets/audit.py、app/assets/delete.py：CRUD、宿主迁移、version条件更新、短IMMEDIATE事务、普通字段前后值、引用仅changed；删除预览含名称编号/依赖/影响，5分钟单次确认绑定版本，提交重验关系与权限；新增before=null/删除after=null，IP集合稳定比较。依赖：T020；验证：取消/越权/冲突/审计失败不改业务，删除无级联子机，历史仍可追溯。
- [X] T022 [US2] 实现 app/assets/selectors.py、app/assets/views.py、app/assets/serializers.py、app/assets/urls.py：参数化q搜索name/no/hostname/IP、type/status/environment/region/owner筛选、可见标量列排序白名单/IP最小规范地址排序、uuid稳定次排序、q及筛选值长度校验、page>=1、默认25最大100；API版本、If-Match与错误契约。依赖：T021；验证：T018查询和冲突测试通过，超长/非法分页和筛选返回422，全部返回字段遵守权限且无SQL拼接注入。
- [X] T023 [US2] 实现 app/templates/assets/、app/static/assets.js、tests/e2e/test_assets.py；中文字段分组/多IP/类型差异/状态/主机选择、列表筛选分页、删除阻塞和二次确认。依赖：T022；验证：三角色浏览器闭环、零数据与异常区分、并发编辑可恢复反馈；FR-004..013验收证据写入 docs/validation/assets.md。

## Phase 5: User Story 3 - 批量导入导出和审计 (P1)

目标：可解释的逐行导入、数据导出及按角色审计查询。
独立验收：SC-004/005/007，错误/合法/重复/依赖文件的结果可核对，重试不重复；导出覆盖全部筛选页，审计无秘密且历史不丢失。

### Tests

- [ ] T024 [P] [US3] 编写 tests/integration/test_imports.py：xls/xlsx/UTF-8 BOM、版本中文模板、空/错表头/重复/公式、20MiB上传/100MiB展开/100列/60秒/5000行边界、预览不写、同文件主机后置、未选/错误/失败宿主、预览后冲突、逐行中断重试。依赖：T023；验证：FR-014/015正反例及总计核对先失败。
  文件协议严格引用contracts/file-schema.md：21列集合/生成顺序、两行元数据和表头、逻辑记录行号、缺/错版本、未知/重复/缺失列、CSV两转义模式及前导零；预览不显示实际成功数量。
  补充FR-006/Q9：A/E确认导入六种合法初态的新资产均可成功，V拒绝；重复项不覆盖既有资产状态，任一虚拟机初态均受宿主资格及依赖规则约束。
- [ ] T025 [P] [US3] 编写 tests/integration/test_exports_audit.py：xlsx/csv全部筛选页、空结果、冻结数量、引用与秘密边界、CSV公式防护往返、权限变更、审计详情越权/筛选/历史查询。依赖：T023；验证：FR-016/017/027、SC-005先失败。
  增补AC-EXPORT-001/AC-AUDIT-001：21列精确协议、条件回显/分页排除、确认前取消、生成失败、下载前故障/流中断/服务器发送完成而客户端保存unknown、产物过期410；全部审计允许组合及拒绝未知组合，CSV apostrophe-v1逐单元格无损往返。

### Implementation

- [ ] T026 [US3] 创建 app/operations/import_models.py、app/operations/export_models.py、app/operations/migrations/ 并在 models.py 注册：ImportJob/Row(uuid/owner/digest/preview_version/state/created/expires、行号/payload/dependencies/errors/result/asset_uuid、UNIQUE(job,row))，ExportJob(owner/filter/format/expected_count/snapshot_digest/state/artifact/expiry)；实现 app/operations/import_parser.py 与 templates.py 的中文列版本1、IP分号/ISO日期、xls/xlsx/csv、一个非空数据sheet、拒公式/宏/外链/数值标识；无网络512MiB解析进程、20MiB/100MiB/100列/60秒/5000数据行、单元格32768字符技术上限。依赖：T024,T025；验证：资源边界可测，超限确认前拒绝且不回显敏感原值。
  parser/templates共同使用contracts/file-schema.md的21列及版本/转义元数据，拒绝猜测别名/版本；两行非数据不计5000行，报错使用实际Excel行或CSV逻辑记录号。
- [ ] T027 [US3] 实现 app/operations/import_validation.py、app/operations/import_service.py、app/operations/import_worker.py：整文件规范化冲突全部标错、依赖图不依赖行序、不可变预览+版本、选择行确认重验权限/关系/唯一性、宿主优先、逐行资产+审计+回执原子提交、错误/跳过/未处理分别计数、duplicate为error子计数；系统性故障停止剩余并持久化INTERRUPTED。依赖：T026；验证：T024通过，恢复/重启重认证后继续、不重放已提交行、宿主失败不创建占位且独立合法行可成功。
  补充Q9：调用T020共用的新资产登记校验，允许A/E合法六种初态，但不借此更新重复资产或放宽宿主资格；预览和确认使用相同规则，按FR-015提交前重验。
- [ ] T028 [US3] 实现 app/operations/export_service.py、app/operations/export_worker.py：短读物化快照后释放数据库，默认全筛选页/显式全部、冻结范围数量/过期重做、无结果不生成；全部业务字段含引用、宿主编号；xlsx文本及CSV防公式转义无损往返；临时文件加密保存24小时后清理，生成/传输/客户端未知结果分离。依赖：T027；验证：T025导出用例通过，无慢下载持有读事务，审计不记录文件或引用原值。
  实现file-schema全部列/条件回显/取消和下载结果，不新增后台取消API；按audit-events写generated与downloaded分阶段事件，client_saved=unknown，不将服务器发送完成宣称客户端保存。
- [ ] T029 [US3] 实现 app/operations/import_views.py、app/operations/export_views.py、app/operations/urls.py、app/templates/imports/、app/templates/exports/：模板、上传、行预览/选择、确认、结果、错误CSV及导出下载；所有作业资源检查当前角色和所有者，降权用户不可沿用创建者权限。依赖：T028；验证：契约主路径与猜测UUID、他人作业、只读、降权负例通过，数字与行终态可核对。
- [ ] T030 [US3] 实现 app/audit/selectors.py、app/audit/views.py、app/audit/urls.py、app/templates/audit/、tests/e2e/test_import_export_audit.py：管理员全部/编辑者仅资产新增编辑状态删除/只读禁止；时间/操作者/动作/结果/编号组合筛选、time/event_uuid倒序分页、允许前后值及空状态；无审计导出或修改入口。依赖：T029；验证：T025及端到端测试通过，删除资产/停用账号不丢历史，导入导出摘要不得被编辑者从详情绕过读取。

## Phase 6: User Story 4 - 概览、提醒和备份恢复 (P2)

目标：可核对的统计、提醒与一致性备份、安全恢复、失败回滚。
独立验收：SC-006/009/010，目标业务状态+历史叠加正确；失败结果只能是完整旧库、完整目标或封闭维护态。

### Tests

- [ ] T031 [P] [US4] 编写 tests/integration/test_overview.py：四维统计、trim文本归组、宿主及子机数量、权限集合、Asia/Shanghai午夜与D-1/D/D+30/D+31、空日期/退役排除、双原因总数去重、过期优先/日期/编号排序、零值和不可用区分。依赖：T030；验证：FR-018、SC-010先失败。
- [ ] T032 [P] [US4] 编写 tests/recovery/test_backup_restore.py、tests/recovery/test_crash_recovery.py：在线写入备份一致性、下载/删除/pin/越权、秘密排除及业务 SystemSetting 随备份恢复；方案A的当前密码/候选凭据分别在当前库/候选库验证、不同管理员成功、候选不存在/停用/非管理员/暂停登录/错密码及当前错密码拒绝、通用失败反馈；原始凭据不进入业务/控制库、作业载荷、日志、审计、错误响应或备份，候选验证不修改账号/会话；凭据失败不创建保护备份/不暂停写入/不撤销会话、绑定回执/账号变化/重启复核；恢复确认/自动保护、目标校验、SystemSetting、审计ID和编号合并、epoch、成功/回滚/维护，逐phase强制终止、ENOSPC/只读盘/损坏密文/失密钥/未知schema/控制库丢失；另定义虚拟机断电演练脚本 tests/recovery/power_failure.sh。依赖：T030；验证：FR-020、SC-006正反例和故障位置覆盖recovery.md所有持久化/切换边界，先失败且不使用生产数据。
  增补AC-CONFIRM-001：快照/恢复不保留ChangeConfirmation，ControlConfirmation的消费/作业入队原子且重启不重做；跨库审计中断对账；候选验证回执绑定User.version，恢复/回滚epoch均不复活旧确认。
  增补Q12/AC-BACKUP-001/AC-RESTORE-001：合法SystemSetting零行、manifest business_setting_keys: []的备份恢复正例；按acceptance构造未知键行及非空manifest键清单反例，均在保护备份/维护/epoch变更前拒绝、不静默清空，原库及原会话可用；原库非空配置的备份和升级迁移也失败。

### Implementation

- [ ] T033 [P] [US4] 实现 app/operations/overview.py、app/operations/overview_views.py、app/templates/overview/：同一短读快照统计用户可见未删除资产、主机子机计数，维保与到期分组/过期优先、日期升序/编号稳定排序，跨组按资产去重；局部失败显示暂不可用。依赖：T031；验证：T031全通过、数量列表详情可相互核对，无外部通知。
- [ ] T034 [P] [US4] 实现 app/operations/backup_service.py、app/operations/backup_files.py：Online Backup API限时复制并包含零行业务 SystemSetting 结构；清除session/运行态后重做integrity/FK/业务校验并计算最终摘要、manifest和快照age认证加密、fsync发布/中断对账；配置键白名单为空，排除部署路径/证书/key/会话；空间检查、不自动清理备份。依赖：T032；验证：在线并发写快照可恢复，配置零行结构随备份恢复且排除部署/密钥/会话，非空配置失败不发布可用包、临时明文受控0700加密卷与0600文件、无秘密下载路径，密钥外置保管。
  session/运行态清理明确包含业务ChangeConfirmation，控制库确认本来就不入包；清理后重验最终文件，不让旧确认随恢复复活。
  Q12：SystemSetting随包保留零行结构，manifest business_setting_keys: []；任一配置行/键以BUSINESS_SETTING_NOT_ALLOWED失败，不删除配置来发布包，验证合法空范围备份可恢复。
- [ ] T035 [US4] 实现 app/operations/backup_views.py、app/operations/backup_catalog.py、app/templates/backups/：管理员备份列表含来源时间大小结果、下载前敏感数据提示、下载审计、二次确认删除、pin占用禁止、删除文件不删审计、失败与取消无误报。依赖：T034；验证：T032备份管理路径通过，删除中断可对账，手动/自动备份均不定时过期清理。
- [ ] T036 [US4] 实现 app/operations/recovery_validation.py、app/operations/recovery_service.py：方案A的管理员授权、当前密码验证当前库、目标备份候选用户名/密码验证隔离候选库和二次确认；候选包来源schema/摘要/认证检查、旧版隔离迁移、schema对象白名单；确认请求在PREBACKUP和入队前按正常认证规则验证候选active/role/密码/登录暂停，原始凭据只存请求内存，通用失败反馈、不创建候选会话或修改候选账号；生成绑定目标备份摘要、候选UUID/账号验证版本、操作者UUID/auth_version/session_epoch及本次操作的服务端回执，worker不接收密码；凭据失败不创建自动保护备份、不关闭门禁、不撤销旧会话；通过后关闭门禁排空、验证自动保护备份并pin、候选业务及 SystemSetting、审计 event_uuid 并集、永久编号并集、ID异内容拒绝。依赖：T035；验证：T032方案A正反例通过，无效包/当前或候选凭据失败/空间不足/自动备份失败/取消不改变原业务或撤销旧会话，业务配置恢复结果与目标一致，禁止直接覆盖活动库。
  Q12：在旧schema迁移及PREBACKUP之前核对配置表零行/manifest空范围；任一配置键以BUSINESS_SETTING_NOT_ALLOWED（或更早的完整性错误）拒绝，不回显键值、不删除配置、不保护备份/维护/撤销会话；候选构建及最终验证重复核对零行，配置结果与合法目标一致。
- [ ] T037 [US4] 实现 app/operations/recovery_worker.py、app/common/management/commands/recovery_verify.py、app/common/management/commands/recovery_rollback.py：VALIDATING/PREBACKUP/PREPARED/REPLACING/VERIFYING/COMMITTED、ROLLING_BACK/ROLLED_BACK/MANUAL_RECOVERY持久化；worker/重启复核服务端验证回执及绑定身份，原始凭据不持久化、不重放；替换前回执/候选账号失效则终止并解除准备恢复门禁、保持原会话，替换后验证失败回滚；实际替换前单调epoch、关闭连接、独立WAL、fsync+原子CURRENT、验证后放行；失败切回完整旧generation、审计幂等补记、重启对账；接通T010生产升级前保护及旧镜像/旧generation回退。依赖：T036；验证：T032每个崩溃点及迁移回滚通过，回滚也不恢复旧会话，失败保持维护且结果可追溯。
- [ ] T038 [US4] 实现 app/operations/recovery_views.py、app/operations/urls.py、app/templates/recovery/、app/assets/identity_views.py、app/templates/assets/identities.html、tests/e2e/test_recovery.py：方案A确认表单明确区分当前管理员密码与备份中的候选管理员用户名/密码，支持不同管理员，输入只随HTTPS确认请求发送、不写浏览器持久存储；凭据失败显示通用反馈并保留业务访问及原会话；确认范围风险、进度/结果/重新登录、匿名维护页不泄露详情；管理员专属历史编号查询、复用统一提示、恢复事件前后范围，敏感数据不展示。依赖：T033,T037；验证：仅管理员查看编号账本和恢复结果；当前/候选凭据拒绝、不同管理员恢复成功、自动备份前失败、开始后成功/回滚/人工维护的会话路径、US4全套自动化通过。

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T039 [P] 完成 tests/contract/test_role_matrix.py、tests/integration/test_secret_surfaces.py、tests/e2e/test_accessibility.py：覆盖contracts全部HTTP/HTMX/CLI/worker入口及账号/资产/作业/审计/备份/历史编号资源越权、CSRF/XSS/CSV公式、日志错误审计禁止秘密、中文键盘标签焦点对比度；区分合法导出含凭据引用、加密备份含密码哈希与日志审计禁止这些内容。依赖：T038；验证：SC-001..011跨故事负例和桌面/窄视口截图均通过，无UI重叠或秘密泄露。
  补充SC-007/Q7：资产/账号/导入导出/审计/备份恢复全部授权拒绝（含查询/预览/下载）的安全审计覆盖率100%；仅管理员列表/详情可查，编辑者不能从本人/资产事件绕过，拒绝审计访问也留痕且不递归；请求体/查询/秘密不入事件，原业务不执行，审计失败路径可测。
- [ ] T040 [P] 完成 tests/integration/test_migrations.py、tests/performance/sqlite_workload.py、docs/validation/sqlite.md：空库/旧版升级/候选迁移/失败回退、2vCPU/4GiB下10万资产/100万审计/20活跃用户/5写事务每秒混合导入导出登录；记录p95/锁等待/DB_BUSY/WAL/RSS、5GiB边界及PostgreSQL迁移触发条件。依赖：T038；验证：列表p95<1秒、普通写<2秒、5000行导入<120秒为待实测目标，超标明确失败不编造结果，不自动换库。
- [ ] T041 [P] 完成 tests/e2e/test_compose_smoke.py、compose.test.yaml、docs/validation/recovery.md：Linux干净卷部署/重启持久化、secret权限、非root/rootfs/cap/端口/健康检查/worker互斥、备份异机取回登记恢复、虚拟机断电与回滚失败演练；检查解析子进程512MiB包含在worker1GiB预算。依赖：T038；验证：quickstart命令逐条可运行，恢复报告含完整性/关系/数量摘要/历史ID/管理员实际登录证据，不把kill进程等同断电。
- [ ] T042 [P] 编写 README.md、docs/deployment.md、docs/upgrade-recovery.md 并校准 specs/001-server-asset-management/quickstart.md：首次管理员、secret移除/轮换、Linux本地卷/NFS禁止、LUKS、备份异机保管/key丢失风险、受控升级/回退、CLI人工恢复、SQLite容量与未来采集仅服务边界。依赖：T038；验证：第二名操作者按文档完成隔离部署和恢复演练，无默认密码、无在线cp库或删卷恢复步骤。
- [ ] T043 执行Django deploy check、迁移漂移检查、pytest、Ruff、mypy、Playwright、构建、依赖漏洞扫描、Compose验收与恢复故障测试；汇总 docs/validation-report.md 的FR/SC证据、机器环境、失败和限制。依赖：T039,T040,T041,T042；验证：每项必需门槛均有结果，任何失败/未执行不得宣称完成或发布。
- [ ] T044 在实现完成后执行 speckit-converge；将遗漏追加至 specs/001-server-asset-management/tasks.md，形成 docs/convergence-report.md，修复后重跑T043。依赖：T043；验证：无未处理高风险遗漏，新增任务有验收且全通过；检查清单的评审归属不被实现代理覆盖。

## Dependencies & Execution Order

```text
T001 → T002 → (T003 || T004) → T005..T010
  → (T011 || T012) → T013..T016 [US1]
  → (T017 || T018) → T019..T023 [US2]
  → (T024 || T025) → T026..T030 [US3]
  → T031 → T033 ───────────────────────┐
  → T032 → T034..T037 ────────────────┴→ T038 [US4]
  → (T039 || T040 || T041 || T042) → T043 → T044
```

严格使用每项任务的直接依赖，编号顺序不是额外隐含依赖。共享settings、URL汇总、迁移编号和依赖锁由对应串行任务统一合并；并行任务不得同时改这些文件。
US1完整资产权限场景依赖US2/US3实际入口，T039完成全矩阵，不能将其误写为完全无跨故事依赖。US4恢复是整套系统能力，依赖前三个故事；概览与备份两支可并行。

## Parallel Examples

- Setup：T002完成后同时分派T003（容器）与T004（测试夹具）。
- US1：T010后T011认证测试与T012权限测试各占独立文件，完成后串行实现。
- US2：T016后T017规则测试与T018关系/查询测试并行。
- US3：T023后T024导入测试与T025导出/审计测试并行。
- US4：T031/T032并行；各自完成后T033概览与T034备份分支并行，T038等待两支。
- 验收：T038后T039安全、T040并发、T041容器恢复、T042文档并行，各用隔离环境；T043统一汇总。

## Requirement Traceability

| 需求/标准 | 主要任务 | 验证入口 |
| --- | --- | --- |
| FR-001..003,023..025 / SC-001,007,008 | T011..T016 | T011,T012,T039 |
| FR-004..010 / SC-002,011 | T019..T021 | T017,T018 |
| FR-011..013 / SC-003,007 | T021..T023 | T018,T023,T039 |
| FR-014..016 / SC-004 | T026..T029 | T024,T025,T030 |
| FR-017,027 / SC-005 | T008,T015,T021,T027..T030 | T005,T012,T025,T039 |
| FR-018 / SC-010 | T033 | T031 |
| FR-019,020,026 / SC-006,009 | T007,T032,T034..T038 | T032,T038,T041 |
| FR-021,022 / 宪法安全可访问性与范围 | T016,T023,T029,T038,T042 | T039,T044 |
| 宪法数据库升级、部署、测试、收敛 | T003..T010,T037,T039..T044 | T040,T041,T043,T044 |

## Implementation Strategy

1. 首先评审T001，随后Setup和Foundational；不自动把未勾选需求质量清单判为通过。
2. US1为登录授权技术增量，US1+US2为内部核心MVP演示点，不代表用户要求的首版交付完成。
3. US3提供批量操作与审计查看；US4补齐统计和强制备份恢复能力。首版必须完成全部四个故事。
4. 先写测试、记录失败、实现、验证；任务勾选须有验证证据，不允许以文件存在替代验收。
5. 本阶段只生成任务，没有编写功能代码或运行功能/性能测试。未来Agent/SSH仅保留来源元数据/服务接口设计，不实现采集、网络扫描或凭据托管。
