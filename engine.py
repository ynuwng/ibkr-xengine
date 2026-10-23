import asyncio
import logging
import os
import signal
from datetime import datetime
from pathlib import Path

import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ib_async import IB, LimitOrder, MarketOrder, Stock, StopOrder, util

from strategy import StrategyParams, apply_strategy, exit_prices, has_entry_signal

BASE_DIR = Path(__file__).resolve().parent


# === 配置加载（config.env 或环境变量）===
def load_config(path=BASE_DIR / 'config.env'):
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


load_config()

IB_HOST = os.getenv('IB_HOST', '127.0.0.1')
IB_PORT = int(os.getenv('IB_PORT', '4002'))  # IB Gateway: 4002 模拟盘 / 4001 实盘
IB_CLIENT_ID = int(os.getenv('IB_CLIENT_ID', '1'))
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() != 'false'  # 默认只记录信号，不下单

SYMBOL = os.getenv('SYMBOL', 'BMNR')
EXCHANGE = os.getenv('EXCHANGE', 'SMART')
CURRENCY = os.getenv('CURRENCY', 'USD')

# === 策略参数与执行仓位配置 ===
STRATEGY_PARAMS = StrategyParams.from_config(os.environ)
RISK_PCT = float(os.getenv('RISK_PCT', '0.5'))

LOG_DIR = Path(os.getenv('LOG_DIR', BASE_DIR / 'logs'))
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_LOG = LOG_DIR / 'live_trade_log.csv'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR / 'engine.log')],
)
log = logging.getLogger('engine')

ib = IB()
contract = Stock(SYMBOL, EXCHANGE, CURRENCY)


# === 连接管理（IB Gateway 每日重启，断线后自动重连）===
async def ensure_connected():
    if ib.isConnected():
        return True
    try:
        await ib.connectAsync(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
        await ib.qualifyContractsAsync(contract)
        log.info(f"已连接 IB {IB_HOST}:{IB_PORT} (clientId={IB_CLIENT_ID})")
        return True
    except Exception as e:
        log.warning(f"连接 IB 失败：{e}")
        return False


# === 获取数据并构建 DataFrame ===
async def fetch_data():
    bars = await ib.reqHistoricalDataAsync(
        contract,
        endDateTime='',
        durationStr='2 D',
        barSizeSetting='1 min',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1,
        keepUpToDate=False
    )
    df = util.df(bars)
    if df is None or df.empty:
        return None
    df.set_index('date', inplace=True)
    return df


# === 持仓 / 挂单检查，避免重复开仓 ===
def has_exposure():
    if any(p.contract.symbol == SYMBOL and p.position != 0 for p in ib.positions()):
        return True
    return any(t.contract.symbol == SYMBOL and not t.isDone() for t in ib.openTrades())


def net_liquidation():
    for v in ib.accountValues():
        if v.tag == 'NetLiquidation' and v.currency == CURRENCY:
            return float(v.value)
    return None


# === 市价买入 + 止盈/止损子单（同一 bracket，任一成交另一自动撤销）===
def place_bracket(quantity, tp_price, sl_price):
    parent = MarketOrder('BUY', quantity, orderId=ib.client.getReqId(), transmit=False)
    take_profit = LimitOrder('SELL', quantity, tp_price, orderId=ib.client.getReqId(),
                             parentId=parent.orderId, tif='GTC', transmit=False)
    stop_loss = StopOrder('SELL', quantity, sl_price, orderId=ib.client.getReqId(),
                          parentId=parent.orderId, tif='GTC', transmit=True)
    for o in (parent, take_profit, stop_loss):
        ib.placeOrder(contract, o)


# === 执行交易逻辑 ===
async def run_strategy():
    if not await ensure_connected():
        return
    try:
        df = await fetch_data()
        if df is None or len(df) < 2:
            log.warning("没有收到历史数据")
            return
        df = apply_strategy(df, STRATEGY_PARAMS)

        # 最后一根 K 线仍在形成中，使用上一根已完成的 K 线判断信号
        last_row = df.iloc[-2]
        price = last_row['close']
        atr = last_row['atr']

        if not has_entry_signal(last_row):
            log.info(f"当前无信号。最后价格：{price:.2f}")
            return
        if has_exposure():
            log.info(f"触发信号，但已有 {SYMBOL} 持仓或挂单，跳过")
            return

        cash = net_liquidation()
        if cash is None:
            log.warning("无法获取 NetLiquidation，跳过")
            return
        quantity = int(cash * RISK_PCT / price)
        if quantity <= 0:
            log.warning(f"计算股数为 0（资金 {cash:.2f}，价格 {price:.2f}），跳过")
            return

        tp_price, sl_price = exit_prices(price, atr, STRATEGY_PARAMS)

        if DRY_RUN:
            log.info(f"[DRY_RUN] 触发信号，拟买入 {quantity} 股 @ ~{price:.2f}，TP {tp_price}，SL {sl_price}")
        else:
            place_bracket(quantity, tp_price, sl_price)
            log.info(f"✅ 触发信号，买入 {quantity} 股 @ ~{price:.2f}，TP {tp_price}，SL {sl_price}")

        log_trade({
            'Datetime': datetime.now(),
            'DryRun': DRY_RUN,
            'Symbol': SYMBOL,
            'Price': price,
            'Size': quantity,
            'TP': tp_price,
            'SL': sl_price
        })
    except Exception:
        log.exception("策略运行出错")


# === 日志保存 ===
def log_trade(info):
    df_log = pd.DataFrame([info])
    df_log.to_csv(TRADE_LOG, mode='a', index=False, header=not TRADE_LOG.exists())


# === 定时执行（每分钟第 5 秒，等待上一根 K 线收盘）===
async def main():
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await ensure_connected()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_strategy, 'cron', second=5, max_instances=1, coalesce=True)
    scheduler.start()
    log.info(f"自动交易已启动（{SYMBOL}，DRY_RUN={DRY_RUN}），每分钟运行一次策略。")

    await stop.wait()
    scheduler.shutdown(wait=False)
    ib.disconnect()
    log.info("自动交易已终止。")


if __name__ == '__main__':
    asyncio.run(main())
