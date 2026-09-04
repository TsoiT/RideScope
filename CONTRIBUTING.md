# 参与开发

感谢关注 RideScope。提交修改前请遵循以下约定。

## 本地开发

1. 使用 Python 3.12 创建虚拟环境。
2. 安装依赖：`python -m pip install -r requirements.txt`。
3. 启动程序：`python -m streamlit run app.py`。
4. 运行测试：`python -m unittest discover -s tests -v`。

## 代码结构

- 文件格式解析放在 `ridescope/parsers.py`。
- 统计口径和派生指标放在 `ridescope/analytics.py`。
- 图表函数放在 `ridescope/visuals.py`。
- 本地文件来源放在 `ridescope/file_sources.py`。
- 运动平台连接器放在 `ridescope/platforms.py`。

新增功能时请补充相应测试。不要提交真实骑行记录、账号、密码、访问令牌、Cookie、启动日志或本地设置文件。

## 提交建议

- 一个提交只解决一个明确问题。
- 提交信息使用简短的动词开头，例如 `Add GPX export` 或 `Fix FIT timestamp parsing`。
- 如果修改统计口径，请在 README 和软件说明书中同步说明。
