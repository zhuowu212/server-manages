# 实施记录

本轮已完成到 T023（资产模型、资产CRUD、角色权限、虚拟机宿主机关联和最小资产UI）。
需求清单是只读质量门槛，不表示代码已经通过测试。

## T001：恢复实施前核对

2026-10-12用户明确恢复上述范围的实施。已复核现行规格、宪法v1.0.0、设计文档及
docs/design-review.md的最新一致性结论：Critical/High/Medium均0，保留D1 Low。
38条FR/SC、44任务、17AC及直接依赖保持原样；Q12为空业务配置范围。
两份需求清单分别18/18及26/26通过，未修改其标记；原README删除状态保留。
本文件记录后续真实验证，旧设计文件的“暂停/0项完成”为历史记录。

## 验证证据

2026-10-13恢复后新增验证：

- `pytest -q`：78 passed。
- `ruff check app tests`：通过。
- `mypy app --no-incremental`：通过，65个源文件。
- `python app/manage.py check --settings=config.settings_test`：无问题。
- `python app/manage.py makemigrations --check --dry-run --settings=config.settings_test`：无迁移漂移。

## 本轮完成情况

- T001：复核设计、宪法、任务依赖及18/18、26/26需求清单，未改清单标记。
- T002：Django 5.2/DRF 3.16/Python 3.12.14项目骨架、自定义User、锁定依赖、静态检查配置。
- T003：Compose、Dockerfile、Caddy、digest锁定、SQLite 3.51.3构建、安全边界检查。
- T004：真实文件SQLite测试夹具、冻结时钟、故障注入、角色工厂、Playwright配置。
- T005：基础数据库、日志秘密过滤、控制库隔离及运行时版本测试。
- T006：已完成并勾选。覆盖SQLite运行时/PRAGMA、Django连接参数、独立工作单元连接关闭、
  结构化安全错误响应、Django包装busy错误识别、日志正向白名单、UTC/Asia-Shanghai配置、
  ready失败和事务外密码验证/哈希。
- T007：已完成并勾选。覆盖独立控制库模型、空部署受控初始化、控制状态缺失fail-closed、
  共享/独占OS门禁、维护排空、失败保持维护、app/worker/CLI共同服从门禁、SystemSetting零行结构及数据库拒写。
- T008：已完成并勾选。覆盖完整审计事件矩阵与数据库触发器一致性、login/rejected非法组合、
  稳定instance_id、普通before/after值保留、秘密字段及完整credential_ref禁止、审计UPDATE/DELETE禁止、
  event_uuid幂等重放、同ID异内容冲突、授权拒绝安全审计、审计失败时业务回滚。
- T009：已完成并勾选。覆盖OperationReceipt/ControlReceipt、ChangeConfirmation/ControlConfirmation、
  非秘密幂等摘要、同键不同秘密不重做、同键不同非秘密409、确认只存令牌摘要、过期/已用/绑定不符拒绝、
  确认消费/账号变更/审计/回执同事务、回执保存内部confirmation_uuid、worker单进程互斥、维护门禁、
  stale running作业标记interrupted而不自动重放。
- T010：已完成并勾选。覆盖migrate_locked受控初始化、重复初始化不改变epoch、数据库路由隔离业务/控制模型、
  迁移漂移检查、recovery_status仅输出非秘密控制状态。
- T011：已完成并勾选。覆盖正确/错误/未知登录、账号创建输入边界、12位/短密码、15分钟登录暂停及期满、
  CSRF、Secure Cookie、首次强制改密服务端限制、旧会话撤销和安全错误响应。
- T012：已完成并勾选。覆盖用户名不可变、显示名可改、非管理员账号路由服务端拒绝及安全审计、
  停用/角色变更/重置密码确认、最后管理员保护、审计失败回滚、幂等重试及确认绑定。
- T013：已完成并勾选。User/LoginAttemptState模型、规范用户名唯一、角色CHECK、version/auth_version分离、
  自定义用户作为会话与审计身份来源。
- T014：已完成并勾选。Argon2id参数、12–256字符密码、未知账号等成本验证、会话epoch/auth_version/active检查、
  CSRF/Cookie安全设置、改密/重置后旧会话失效。
- T015：已完成并勾选。账号API、bootstrap_admin、管理员新增/编辑/停用/角色变更/重置密码、二次确认、
  最后管理员保护、审计和回执事务边界。
- T016：已完成并勾选。根路径登录/改密/账号页面、中文标签、管理员导航、账号创建表单、破坏性操作确认钩子、
  直接请求负例测试；UI隐藏不替代服务端授权。
- T017：已完成并勾选。新增 `tests/integration/test_asset_rules.py`，覆盖必填字段、类型适用性、
  六种初态、编辑者状态矩阵、编号永久保留、标识释放复用、IP规范化和凭据引用审计边界。
- T018：已完成并勾选。新增 `tests/integration/test_asset_relations_queries.py`，覆盖虚拟机宿主状态、
  无效/缺失宿主、宿主带子机删除/退役阻塞、虚拟机迁移版本冲突、搜索筛选排序分页和删除确认幂等。
- T019：已完成并勾选。新增 AssetIdentity/Asset/AssetAddress 模型和迁移；编号规范化永久保留，
  当前主机名、序列号、IP唯一；删除资产保留 identity 并释放其他标识。
- T020：已完成并勾选。实现资产校验、生命周期和关系规则；数据库触发器阻止无效宿主、
  带子机宿主变无效和直接删除；IP zone_id拒绝，IPv4-mapped归一。
- T021：已完成并勾选。实现资产创建/更新/删除预览/确认删除、版本条件更新、审计同事务、
  删除确认绑定版本和管理员权限；credential_ref 不进入审计。
- T022：已完成并勾选。实现资产列表/详情/写入 API、If-Match版本、幂等回执、参数化搜索筛选排序分页和错误契约。
- T023：已完成并勾选。实现资产列表/新增/详情模板、类型字段脚本、角色导航和 e2e 页面验收；
  验收摘要见 `docs/validation/assets.md`。

验证结果：最新本机验证为 `pytest -q` **78 passed**；`ruff check app tests` 通过；
`mypy app --no-incremental` 通过；Django check与迁移漂移检查通过。此前Compose config、镜像
`server-manages:0.1.0` 构建和容器SQLite 3.51.3运行时验证曾通过；本次代码改动后尚未重新构建镜像。

剩余问题：T024起导入导出、审计查询、概览、备份恢复、跨功能矩阵、性能/Compose/恢复演练和收敛尚未实现。
Docker Hub 直连不稳定，此前构建验证使用了已核验
digest 的镜像代理并通过 `BUILD_REGISTRY` 参数；生产应使用组织批准的镜像仓库。
