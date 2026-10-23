"""量价动量策略；不连接 IBKR，也不读取文件或提交订单。"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyParams:
    vol_period: int = 20
    vol_ratio_th: float = 1.45
    short_ma: int = 5
    mid_ma: int = 10
    atr_period: int = 14
    tp_atr: float = 2.5
    sl_atr: float = 1.5

    @classmethod
    def from_config(cls, config):
        """从引擎已加载的配置映射读取参数，保留原配置名称及默认值。"""
        return cls(
            vol_period=int(config.get('VOL_PERIOD', cls.vol_period)),
            vol_ratio_th=float(config.get('VOL_RATIO_TH', cls.vol_ratio_th)),
            short_ma=int(config.get('SHORT_MA', cls.short_ma)),
            mid_ma=int(config.get('MID_MA', cls.mid_ma)),
            atr_period=int(config.get('ATR_PERIOD', cls.atr_period)),
            tp_atr=float(config.get('TP_ATR', cls.tp_atr)),
            sl_atr=float(config.get('SL_ATR', cls.sl_atr)),
        )


def apply_strategy(df, params=StrategyParams()):
    """沿用原算法，在传入的 DataFrame 上添加指标和 signal 列。"""
    df['vol_avg'] = df['volume'].rolling(params.vol_period).mean()
    df['vol_ratio'] = df['volume'] / df['vol_avg']
    df['shortMA'] = df['close'].rolling(params.short_ma).mean()
    df['midMA'] = df['close'].rolling(params.mid_ma).mean()
    df['atr'] = (df['high'] - df['low']).rolling(params.atr_period).mean()

    df['signal'] = (df['vol_ratio'] > params.vol_ratio_th) & (df['shortMA'] > df['midMA'])
    return df


def has_entry_signal(row):
    return bool(row['signal']) and not math.isnan(row['atr'])


def exit_prices(price, atr, params=StrategyParams()):
    return round(price + params.tp_atr * atr, 2), round(price - params.sl_atr * atr, 2)
