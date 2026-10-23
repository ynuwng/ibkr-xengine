# ibkr-xengine

基于 [ib_async](https://github.com/ib-api-reloaded/ib_async) 的 Interactive Brokers 自动交易执行引擎，适合部署在 Linux VPS 上，配合 IB Gateway 运行。

策略：1 分钟 K 线量价动量（成交量放大 + 短均线在中均线之上），触发后市价买入，并挂基于 ATR 的止盈 / 止损 bracket 子单。已有持仓或挂单时不会重复开仓。

> 回测脚本和样例数据保存在 `research` 分支。

## 文件

- `engine.py`：交易引擎，每分钟第 5 秒运行一次策略，自动重连 IB。
- `healthcheck.py`：检查能否连接 IB Gateway（失败时退出码为 1）。
- `config.env.example`：配置模板。
- `logs/`：运行日志 `engine.log` 和信号 / 交易记录 `live_trade_log.csv`（自动创建）。

## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.env.example config.env   # 按需修改
```

## 运行

1. 启动 IB Gateway 并开启 API（模拟盘端口 `4002`，实盘 `4001`）。
2. 检查连接：`.venv/bin/python healthcheck.py`
3. 启动引擎：`.venv/bin/python engine.py`

`DRY_RUN=true`（默认）时只记录信号、不下单。确认在模拟盘上运行正常后，再在 `config.env` 中设为 `false`。

> 本项目仅用于学习，实际交易风险自负。

## 许可证

[MIT License](LICENSE)
