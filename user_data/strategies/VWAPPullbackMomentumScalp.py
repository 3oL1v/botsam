"""
VWAPPullbackMomentumScalp

Trend-following entry after a pullback to the anchored daily VWAP or EMA20.
"""

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, informative

from lab_base import LabBaseStrategy


class VWAPPullbackMomentumScalp(LabBaseStrategy, IStrategy):
    timeframe = "5m"
    lev = 3.0
    margin_per_position = 12.0
    max_hold_minutes = 120
    cooldown_candles = 3
    startup_candle_count = 120

    stoploss = -0.0210
    minimal_roi = {"0": 0.0420}

    trailing_stop = True
    trailing_stop_positive = 0.0105
    trailing_stop_positive_offset = 0.024
    trailing_only_offset_is_reached = True

    @informative("15m")
    def populate_indicators_15m(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["vol_mean30"] = dataframe["volume"].rolling(30).mean().shift(1)

        typical_price = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3.0
        tpv = typical_price * dataframe["volume"]
        day = dataframe["date"].dt.normalize()
        cum_tpv = tpv.groupby(day).cumsum()
        cum_volume = dataframe["volume"].groupby(day).cumsum().replace(0, float("nan"))
        dataframe["vwap"] = cum_tpv / cum_volume

        dataframe["dist_above"] = dataframe["close"] - dataframe["vwap"]
        dataframe["dist_below"] = dataframe["vwap"] - dataframe["close"]
        dataframe["max_above_12"] = dataframe["dist_above"].rolling(12).max()
        dataframe["max_below_12"] = dataframe["dist_below"].rolling(12).max()

        touch_vwap = (dataframe["low"] <= dataframe["vwap"]) & (dataframe["high"] >= dataframe["vwap"])
        touch_ema = (dataframe["low"] <= dataframe["ema20"]) & (dataframe["high"] >= dataframe["ema20"])
        touch = touch_vwap | touch_ema
        dataframe["touched_recent"] = touch | touch.shift(1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        vol_ok = dataframe["volume"] > dataframe["vol_mean30"] * 1.10
        has_vol = dataframe["volume"] > 0

        long_sig = (
            (dataframe["close"] > dataframe["ema50_15m"])
            & (dataframe["adx_15m"] > 18)
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["max_above_12"] >= dataframe["atr"] * 0.70)
            & dataframe["touched_recent"]
            & (dataframe["close"] > dataframe["vwap"])
            & (dataframe["close"] > dataframe["ema20"])
            & (dataframe["rsi"] >= 48)
            & (dataframe["rsi"] <= 66)
            & vol_ok
            & has_vol
        )
        short_sig = (
            (dataframe["close"] < dataframe["ema50_15m"])
            & (dataframe["adx_15m"] > 18)
            & (dataframe["ema20"] < dataframe["ema50"])
            & (dataframe["max_below_12"] >= dataframe["atr"] * 0.70)
            & dataframe["touched_recent"]
            & (dataframe["close"] < dataframe["vwap"])
            & (dataframe["close"] < dataframe["ema20"])
            & (dataframe["rsi"] >= 34)
            & (dataframe["rsi"] <= 52)
            & vol_ok
            & has_vol
        )

        dataframe.loc[long_sig, ["enter_long", "enter_tag"]] = (1, "vwap_pull_long")
        dataframe.loc[short_sig, ["enter_short", "enter_tag"]] = (1, "vwap_pull_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] < dataframe["vwap"], ["exit_long", "exit_tag"]] = (
            1,
            "below_vwap",
        )
        dataframe.loc[dataframe["close"] > dataframe["vwap"], ["exit_short", "exit_tag"]] = (
            1,
            "above_vwap",
        )
        return dataframe
