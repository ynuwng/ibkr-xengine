# ibkr-xengine

基于 [ib_async](https://github.com/ib-api-reloaded/ib_async) 的 Interactive Brokers 自动交易执行引擎，适合部署在 Linux VPS 上，配合 IB Gateway 运行。

`engine.py` 负责 IBKR 连接、行情取数、策略调用、持仓 / 资金检查、订单提交、日志和定时调度。策略计算独立放在 `strategy.py` 中，由引擎传入数据与参数；策略模块不连接 IBKR，也不提交订单。

主分支为 `main`，包含执行引擎、独立策略模块、连接检查和配置模板。回测脚本和样例数据已移除。

当前每分钟请求最近两个交易日的常规交易时段历史 K 线，并使用返回数据的倒数第二根 K 线判断信号；尚未接入实时行情、逐笔成交或 Level 2 订单簿。

## 文件

- `engine.py`：连接 IBKR、取数、调用策略、持仓 / 资金检查、下单、日志和调度；每分钟第 5 秒运行一次，自动重连 IB。
- `strategy.py`：独立的策略参数、指标计算、入场判断与止盈 / 止损价格计算，不连接 IBKR。
- `healthcheck.py`：检查能否连接 IB Gateway（失败时退出码为 1）。
- `config.env.example`：配置模板。
- `logs/`：运行日志 `engine.log` 和信号 / 交易记录 `live_trade_log.csv`（自动创建）。

## 当前内置策略

`strategy.py` 当前实现 1 分钟 K 线量价动量策略：成交量放大且短均线高于中均线时产生入场信号，并计算基于 ATR 的止盈 / 止损价格。这里的 ATR 沿用现有算法，按每根 K 线的最高价减最低价取滚动均值。

引擎使用倒数第二根 K 线判断信号，通过持仓 / 挂单和资金检查后，提交市价买入及止盈 / 止损 bracket 子单；已有持仓或挂单时不会重复开仓。

`strategy.apply_strategy(df)` 可独立计算默认策略；自定义参数可通过 `StrategyParams` 传入。函数在传入的 DataFrame 上添加指标和 `signal` 列。

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

## 配置

配置从项目目录下的 `config.env` 加载，已有环境变量优先。引擎加载配置后将策略参数传给 `strategy.py`。

### 执行与连接配置

以下配置由执行引擎使用，`RISK_PCT` 控制买入股数的资金分配比例。

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `IB_HOST` / `IB_PORT` | `127.0.0.1` / `4002` | IB Gateway 地址与端口 |
| `IB_CLIENT_ID` | `1` | API 客户端 ID，同一 Gateway 上应避免冲突 |
| `DRY_RUN` | `true` | 仅设为 `false` 时提交订单 |
| `SYMBOL` / `EXCHANGE` / `CURRENCY` | `BMNR` / `SMART` / `USD` | 交易标的、路由和币种 |
| `RISK_PCT` | `0.5` | 仓位分配比例：按账户净值的 50% 计算买入股数，并非止损风险比例 |
| `LOG_DIR` | 项目目录下的 `logs/` | 日志保存目录 |

### 内置策略配置

以下参数由 `strategy.py` 使用，经引擎加载后传给 `StrategyParams`。

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `VOL_PERIOD` / `VOL_RATIO_TH` | `20` / `1.45` | 成交量均值周期与放量阈值 |
| `SHORT_MA` / `MID_MA` | `5` / `10` | 短期与中期均线周期 |
| `ATR_PERIOD` | `14` | 波动幅度均值周期，当前按每根 K 线的最高价减最低价计算 |
| `TP_ATR` / `SL_ATR` | `2.5` / `1.5` | 止盈与止损的波动幅度倍数 |

`healthcheck.py` 默认使用 `IB_CLIENT_ID + 100`，可通过 `HEALTHCHECK_CLIENT_ID` 单独指定。

> 本项目仅用于学习，实际交易风险自负。

## 许可证

[MIT License](LICENSE)
