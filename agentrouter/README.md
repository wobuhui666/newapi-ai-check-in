# AgentRouter 每日签到

AgentRouter 的每日额度在**重新登录**时自动到账（页面提示“签到成功，新增额度已到账”）。
这里用 GitHub Actions（`.github/workflows/agentrouter-checkin.yml`） 每天北京时间 09:10 开一个全新的无头浏览器登录一次，完成签到并打印余额。

## 使用

1. 仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加：
   - `AGENTROUTER_EMAIL`：邮箱或用户名
   - `AGENTROUTER_PASSWORD`：密码
2. **Actions → AgentRouter 每日签到 → Run workflow** 手动跑一次，看日志确认成功。

## 说明

- 每次都是新的浏览器上下文，相当于“退出后重新登录”。
- 失败会重试 3 次，仍失败时上传页面截图（Artifacts 里的 `agentrouter-failure-screenshot`）。
- 站点挂了阿里云 WAF。如果日志提示“被阿里云 WAF 滑块验证拦截”，说明 GitHub 的机房 IP 被拦，需要换成自托管 runner 或在自己的机器上用 cron 跑：

```bash
pip install playwright && python -m playwright install --with-deps chromium
AGENTROUTER_EMAIL=... AGENTROUTER_PASSWORD=... python agentrouter/checkin.py
```

- 公开仓库的定时任务在 60 天无提交后会被 GitHub 自动停用，到时在 Actions 页面重新启用即可。
