# RideScope 骑行轨迹分析

RideScope 是一个在个人电脑上运行的骑行数据分析程序。它读取 GPX 或 FIT 轨迹文件，计算里程、用时、速度、爬升、心率、踏频、功率等指标，并在地图上汇总显示多次骑行轨迹。

> 本项目以本地处理为主：轨迹解析和统计不会上传到 RideScope 自有服务器。在线地图和运动平台下载功能需要联网。

## 最快开始（Windows）

1. 安装 Python 3.12（支持 3.10-3.13，暂不支持 3.14），并在安装界面勾选“Add Python to PATH”。
2. 直接双击 `启动程序.bat`，不要使用“用 PowerShell 运行”。
3. 首次运行会自动创建独立环境并安装依赖；完成后浏览器自动打开。
4. 在左侧上传一个或多个 `.gpx` / `.fit` 文件，或把文件放进项目内的 `records` 文件夹。

启动器会保留窗口并把详细信息写到同目录的 `RideScope-startup.log`。如果启动失败，请把这个日志发给开发者。若曾经用 Python 3.14 创建过环境，请先删除项目内的 `.venv` 文件夹再重新双击。

轨迹解析和统计在本机完成。首次安装依赖、在线 OpenStreetMap 底图以及从运动平台获取记录需要联网；无法联网时可继续使用手动上传、文件夹读取和离线坐标图。

## 功能

- GPX / FIT 多文件导入与错误提示
- iGPSPORT 与 Onelap/顽鹿 OTM 账号连接，可自动读取最近记录并下载 FIT
- 自动扫描指定文件夹，可保存路径、递归读取子文件夹，并与手动上传的文件合并去重
- 单次及总计里程、总用时、运动时间、均速、最高速度、累计爬升
- 心率、踏频和功率统计（原文件含对应字段时显示）
- OpenStreetMap 道路底图、仅显示细线的多次轨迹总览，以及不联网时可用的离线坐标图
- 速度、海拔随里程变化曲线
- 骑行汇总与轨迹点 CSV 导出
- 内置演示数据，未上传文件时也能直接体验

## 命令行启动

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## 运行测试

在项目目录中执行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub Actions 会在每次推送和拉取请求时使用 Python 3.12 自动运行同一组测试。

## 项目文档

- [软件说明书](docs/RideScope_软件说明书_程序文档.docx)：功能、安装、架构、算法、平台连接、测试和限制
- [参与开发](CONTRIBUTING.md)：本地开发、模块划分和提交约定
- [安全与隐私](SECURITY.md)：凭据、轨迹文件和外部平台注意事项

## 目录说明

- `app.py`：界面与交互入口
- `ridescope/parsers.py`：GPX / FIT 文件解析
- `ridescope/analytics.py`：距离、时间、速度、爬升统计
- `ridescope/visuals.py`：线路、轨迹总览与曲线绘制
- `sample_data/demo_loop.gpx`：演示用合成轨迹
- `records/`：默认自动读取的轨迹文件夹
- `tests/`：自动化测试
- `docs/`：课程设计报告

## 统计口径与限制

- 地球距离采用 Haversine 公式；移动速度阈值为 1 km/h。
- 相邻记录时间间隔超过 10 分钟时，不把该间隔计入移动时间。
- 超过 150 km/h 的速度按异常值处理。
- 累计爬升由相邻海拔正增量计算，单点跳变超过 50 m 时不计入，以降低 GPS 漂移影响。
- FIT 中没有 GPS record、GPX 中没有 `trkpt` 时无法生成路线。
- “轨迹总览”只绘制轨迹细线，不做密度扩散，避免大批量记录形成色块并遮挡地图内容。

## 自动读取文件夹

默认情况下，程序每次启动或刷新页面都会扫描项目内的 `records` 文件夹。也可以在左侧填写其他完整路径，例如 `D:\\骑行记录`，选择是否扫描子文件夹，然后点击“保存文件夹设置”。设置只保存在本机项目目录的 `.ridescope-settings.json` 中。

单次最多读取 500 个 GPX/FIT 文件。文件夹中的记录和页面上传的记录会一起分析；内容完全相同的文件只计算一次。文件增删或更新后，刷新网页即可重新读取。

## 自动从 iGPSPORT / Onelap 下载

展开左侧“自动从 iGPSPORT / Onelap 下载”，选择平台和最近记录数量（1-1000），然后点击“登录、获取并下载”。成功下载的 FIT 会立即加入当前统计；默认还会保存到项目的 `records/downloaded/igpsport` 或 `records/downloaded/onelap`，下次启动可继续自动读取。批量数量较大时下载、解析和绘图会需要更长时间。

- iGPSPORT：中国大陆账号可使用用户名/密码，也可使用网页端 Access Token。
- Onelap / 顽鹿 OTM：使用手机号或账号及密码登录。
- 账号、密码和 Token 只存在于当前 Streamlit 会话和发往相应平台的网络请求中，不会写入 RideScope 设置文件或日志。
- 下载过程中单个记录失败不会中断其他记录，界面会显示具体错误。

这两家平台没有面向本项目提供稳定的公开用户数据 API。连接器依据其当前网页端协议实现，平台修改登录验证、活动列表或下载接口后可能需要更新；遇到验证码、登录保护或接口变化时，可暂时继续使用手动上传和文件夹自动读取。
