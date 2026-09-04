# 安全与隐私

RideScope 在用户电脑本地解析和统计 GPX/FIT。在线地图以及 iGPSPORT、Onelap 数据下载需要访问相应外部服务。

## 敏感信息

- 账号、密码和 Access Token 不应提交到仓库。
- `.ridescope-settings.json`、`RideScope-startup.log`、`.venv/` 和 `records/` 中的用户数据已被 `.gitignore` 排除。
- 平台凭据只应在当前 Streamlit 会话中使用，不应写入文件或日志。

## 报告安全问题

请通过 GitHub 仓库所有者提供的私密联系方式报告可能泄露账号、令牌或精确位置的问题，不要在公开 Issue 中粘贴真实凭据和骑行文件。

## 外部平台说明

iGPSPORT 与 Onelap 连接器依据其当前网页端协议实现。平台接口或登录验证发生变化时，连接器可能需要更新。使用者应遵守相应平台的服务条款。
