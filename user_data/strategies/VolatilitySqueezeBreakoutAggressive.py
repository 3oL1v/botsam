"""
VolatilitySqueezeBreakoutAggressive

Momentum breakout after a volatility squeeze, confirmed by Bollinger bandwidth
expansion, a band break, EMA alignment, ADX and a volume burst.
"""

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import IStrategy, informative

from lab_base import LabBaseStrategy


class VolatilitySqueezeBreakoutAggressive(LabBaseStrategy, IStrategy):
    timeframe = "5m"
    lev = 3.0
    margin_per_position = 12.0
    max_hold_minutes = 180
    cooldown_candles = 3
    startup_candle_count = 320

    stoploss = -0.0255
    minimal_roi = {"0": 0.0510}

    trailing_stop = True
    trailing_stop_positive = 0.0135
    trailing_stop_positive_offset = 0.030
    trailing_only_offset_is_reached = True

    @informative("15m")
    def populate_indicators_15m(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_middle"] = bb["middleband"]
        dataframe["bb_lower"] = bb["lowerband"]
        safe_mid = dataframe["bb_middle"].replace(0, float("nan"))
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / safe_mid

        dataframe["bb_width_q25"] = (
            dataframe["bb_width"].rolling(100, min_periods=100).quantile(0.25).shift(1)
        )
        dataframe["vol_mean30"] = dataframe["volume"].rolling(30).mean().shift(1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        prior_squeeze = dataframe["bb_width"].shift(1) < dataframe["bb_width_q25"]
        expansion = dataframe["bb_width"] > dataframe["bb_width"].shift(1) * 1.05
        vol_ok = dataframe["volume"] > dataframe["vol_mean30"] * 1.40
        adx_ok = dataframe["adx"] > 18
        has_vol = dataframe["volume"] > 0

        long_sig = (
            prior_squeeze
            & expansion
            & qtpylib.crossed_above(dataframe["close"], dataframe["bb_upper"])
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["close"] > dataframe["ema50_15m"])
            & adx_ok
            & vol_ok
            & has_vol
        )
        short_sig = (
            prior_squeeze
            & expansion
            & qtpylib.crossed_below(dataframe["close"], dataframe["bb_lower"])
            & (dataframe["ema20"] < dataframe["ema50"])
            & (dataframe["close"] < dataframe["ema50_15m"])
            & adx_ok
            & vol_ok
            & has_vol
        )

        dataframe.loc[long_sig, ["enter_long", "enter_tag"]] = (1, "squeeze_break_long")
        dataframe.loc[short_sig, ["enter_short", "enter_tag"]] = (1, "squeeze_break_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        max_hold = self._max_hold_exit(trade, current_time)
        if max_hold:
            return max_hold
        if current_profit <= 0:
            return None
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) < 2:
            return None
        last = dataframe.iloc[-1]
        previous = dataframe.iloc[-2]
        if not trade.is_short:
            if previous["close"] >= previous["ema20"] and last["close"] < last["ema20"]:
                return "ema20_cross_profit_long"
        else:
            if previous["close"] <= previous["ema20"] and last["close"] > last["ema20"]:
                return "ema20_cross_profit_short"
        return None
