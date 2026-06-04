"""
DonchianVolumeBurst5m

Aggressive breakout of a local Donchian range on a sharp volume increase.
"""

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy

from lab_base import LabBaseStrategy


class DonchianVolumeBurst5m(LabBaseStrategy, IStrategy):
    timeframe = "5m"
    lev = 3.0
    margin_per_position = 10.0
    max_hold_minutes = 120
    cooldown_candles = 4
    startup_candle_count = 160

    stoploss = -0.0240
    minimal_roi = {"0": 0.0480}

    trailing_stop = True
    trailing_stop_positive = 0.0120
    trailing_stop_positive_offset = 0.0285
    trailing_only_offset_is_reached = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        dataframe["dc_upper"] = dataframe["high"].rolling(36).max().shift(1)
        dataframe["dc_lower"] = dataframe["low"].rolling(36).min().shift(1)
        dataframe["vol_mean40"] = dataframe["volume"].rolling(40).mean().shift(1)
        dataframe["body"] = (dataframe["close"] - dataframe["open"]).abs()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        vol_ok = dataframe["volume"] > dataframe["vol_mean40"] * 1.50
        adx_ok = dataframe["adx"] > 20
        body_ok = dataframe["body"] <= dataframe["atr"] * 2.20
        has_vol = dataframe["volume"] > 0

        long_sig = (
            (dataframe["close"] > dataframe["dc_upper"])
            & (dataframe["close"].shift(1) <= dataframe["dc_upper"].shift(1))
            & vol_ok
            & adx_ok
            & (dataframe["close"] > dataframe["ema100"])
            & body_ok
            & has_vol
        )
        short_sig = (
            (dataframe["close"] < dataframe["dc_lower"])
            & (dataframe["close"].shift(1) >= dataframe["dc_lower"].shift(1))
            & vol_ok
            & adx_ok
            & (dataframe["close"] < dataframe["ema100"])
            & body_ok
            & has_vol
        )

        dataframe.loc[long_sig, ["enter_long", "enter_tag"]] = (1, "donchian_break_long")
        dataframe.loc[short_sig, ["enter_short", "enter_tag"]] = (1, "donchian_break_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] < dataframe["dc_upper"], ["exit_long", "exit_tag"]] = (
            1,
            "back_in_range_long",
        )
        dataframe.loc[dataframe["close"] > dataframe["dc_lower"], ["exit_short", "exit_tag"]] = (
            1,
            "back_in_range_short",
        )
        return dataframe
