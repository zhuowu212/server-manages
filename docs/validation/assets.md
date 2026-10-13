# 资产管理验收摘要

日期：2026-10-13

覆盖任务：T017–T023。

## 已验证范围

- 资产模型：AssetIdentity 永久保留规范化编号，Asset 保存显示编号和版本，AssetAddress 保存规范化 IP。
- 字段规则：四类资产、六种初态、必填字段、类型适用字段、日期顺序、多 IP、IPv4-mapped 归一、zone_id 拒绝。
- 约束：编号永久不可复用；删除后序列号、主机名、IP 可释放复用；当前序列号、主机名、IP 唯一。
- 宿主关系：虚拟机只能关联 physical 且状态为 racked/active/repair 的宿主；有子机宿主禁止删除或改为无效类型/状态。
- 权限：管理员/编辑者可新增合法资产；只读用户服务端拒绝写入；编辑者后续状态流转按矩阵限制。
- CRUD/API：创建、详情、更新、删除预览、管理员确认删除、幂等删除重放、列表搜索/筛选/排序/分页。
- 审计：资产新增、更新、状态变更、删除与业务同事务；credential_ref 不进入审计 before/after/summary。
- UI：资产列表、新增表单、详情页、中文标签、按角色隐藏新增入口；直接 API 请求仍由服务端授权拒绝。

## 本机验证

- `pytest -q`：78 passed。
- `ruff check app tests`：通过。
- `mypy app --no-incremental`：通过。
- `python app/manage.py check --settings=config.settings_test`：通过。
- `python app/manage.py makemigrations --check --dry-run --settings=config.settings_test`：No changes detected。

## 已知后续

T024 起导入导出、审计查询、概览、备份恢复和跨功能角色矩阵尚未实现；完整跨入口授权覆盖会在 T039 补齐。
