# 隔离验证

Python3.12，`uv sync --frozen`及`npm ci --ignore-scripts`安装锁定依赖。
测试settings强制使用/tmp的独立文件SQLite，严禁指向生产卷；pytest会建立并销毁测试库。
roles工厂在T014实现后创建真实Argon2账号；clock冻结UTC时钟；fault注入持久化失败。

```bash
.venv/bin/python app/manage.py check --settings=config.settings_test
.venv/bin/ruff check app tests
.venv/bin/mypy app
.venv/bin/pytest --collect-only
.venv/bin/pytest tests/contract tests/integration tests/recovery
PLAYWRIGHT_BROWSERS_PATH=/tmp/server-manages-browsers .venv/bin/playwright install chromium
PLAYWRIGHT_BROWSERS_PATH=/tmp/server-manages-browsers .venv/bin/pytest tests/e2e
```

Python Playwright为本轮浏览器入口；playwright.config.ts保留同版本Node工具配置。
数据库测试采用真实文件及独立连接，不能以纯内存锁证明并发保护。
生产命令需secret文件、本地加密卷及受信任TLS；本轮仅账号阶段，不执行后续资产/恢复验收。
