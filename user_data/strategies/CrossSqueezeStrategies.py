"""
Long/short Freqtrade strategies for Binance USDⓈ-M Futures with cross margin.
Designed for a small account (~100 USDT) and restrained exposure.

Target strategy class names:
- CrossSqueezeExpansion15m
- CrossSqueezeExpansion4HFilter15m
- CrossSqueezeSafe15m

Notes:
- These strategies require futures trading and can_short=True.
- Stake sizing returns margin, not leveraged notional value.
- No DCA / position adjustment is enabled.
"""

from datetime import datetime
from typing import Optional

import talib.abstract as ta
from pandas import DataFrame, Series
from technical import qtpylib

from freqtrade.strategy import IStrategy, informative


class _CrossSqueezeBase15m(IStrategy):
    """
    Shared squeeze-breakout logic.
    Do not select this base class directly.
    """

    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 240

    # Risk controls for a shared-collateral cross-margin wallet.
    position_adjustment_enable = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Overridden by concrete strategies where needed.
    strategy_leverage: float = 2.0

    # Margin target per trade.
    # With 100 USDT equity: 7 USDT margin per position.
    position_equity_pct: float = 0.07

    # Signal parameters.
    squeeze_quantile: float = 0.30
    bandwidth_expansion: float = 1.05
    volume_multiplier: float = 1.10
    adx_floor: float = 16.0

    # Freqtrade evaluates stoploss / ROI on leveraged trade PnL.
    # At 2x leverage:
    # -4.6% trade PnL ~= -2.3% underlying price movement.
    stoploss = -0.046

    minimal_roi = {
        "0": 0.110,      # ~= +5.5% underlying move at 2x
        "240": 0.060,
        "720": 0.000,
    }

    trailing_stop = True
    trailing_stop_positive = 0.032
    trailing_stop_positive_offset = 0.060
    trailing_only_offset_is_reached = True

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """
        Return bounded leverage for every new position.
        Same leverage is used for long and short trades.
        """
        return min(self.strategy_leverage, max_leverage)

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """
        Allocate margin equal to 7% of current wallet equity.

        Starting from 100 USDT:
        - 2x strategy: approximately 7 USDT margin / 14 USDT notional.
        - 1.5x strategy: approximately 7 USDT margin / 10.5 USDT notional.

        If exchange minimum stake forces a position above the intended
        risk allocation, skip the entry instead of increasing risk.
        """
        equity = float(self.wallets.get_total_stake_amount())
        target_margin = equity * self.position_equity_pct

        if min_stake is not None and target_margin < float(min_stake):
            return 0.0

        return min(target_margin, float(max_stake))

    def populate_indicators(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:
        """
        Indicators for volatility compression / expansion trading.
        """
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        bbands = ta.BBANDS(
            dataframe,
            timeperiod=20,
            nbdevup=2.1,
            nbdevdn=2.1,
            matype=0,
        )

        dataframe["bb_upper"] = bbands["upperband"]
        dataframe["bb_middle"] = bbands["middleband"]
        dataframe["bb_lower"] = bbands["lowerband"]

        safe_middle = dataframe["bb_middle"].replace(0, float("nan"))

        dataframe["bb_width"] = (
            (dataframe["bb_upper"] - dataframe["bb_lower"]) / safe_middle
        )

        # Quantile is shifted so current signal does not use future candles.
        dataframe["bb_width_q"] = (
            dataframe["bb_width"]
            .rolling(120, min_periods=120)
            .quantile(self.squeeze_quantile)
            .shift(1)
        )

        dataframe["volume_mean30"] = (
            dataframe["volume"]
            .rolling(30)
            .mean()
            .shift(1)
        )

        return dataframe

    def _long_regime_filter(self, dataframe: DataFrame) -> Series:
        """
        Hook for subclasses that apply a higher-timeframe trend filter.
        """
        return Series(True, index=dataframe.index)

    def _short_regime_filter(self, dataframe: DataFrame) -> Series:
        """
        Hook for subclasses that apply a higher-timeframe trend filter.
        """
        return Series(True, index=dataframe.index)

    def populate_entry_trend(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:
        """
        Entry logic:
        1. Bollinger bandwidth was compressed.
        2. Volatility starts expanding.
        3. Price breaks outside the band.
        4. EMA, ADX and volume confirm the direction.
        """
        prior_squeeze = (
            dataframe["bb_width"].shift(1) < dataframe["bb_width_q"]
        )

        expansion = (
            dataframe["bb_width"]
            > dataframe["bb_width"].shift(1) * self.bandwidth_expansion
        )

        volume_confirmed = (
            dataframe["volume"]
            > dataframe["volume_mean30"] * self.volume_multiplier
        )

        long_signal = (
            prior_squeeze
            & expansion
            & qtpylib.crossed_above(
                dataframe["close"],
                dataframe["bb_upper"],
            )
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["adx"] > self.adx_floor)
            & volume_confirmed
            & self._long_regime_filter(dataframe)
            & (dataframe["volume"] > 0)
        )

        short_signal = (
            prior_squeeze
            & expansion
            & qtpylib.crossed_below(
                dataframe["close"],
                dataframe["bb_lower"],
            )
            & (dataframe["ema20"] < dataframe["ema50"])
            & (dataframe["adx"] > self.adx_floor)
            & volume_confirmed
            & self._short_regime_filter(dataframe)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[
            long_signal,
            ["enter_long", "enter_tag"],
        ] = (
            1,
            "squeeze_breakout_long",
        )

        dataframe.loc[
            short_signal,
            ["enter_short", "enter_tag"],
        ] = (
            1,
            "squeeze_breakout_short",
        )

        return dataframe

    def populate_exit_trend(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:
        """
        Exit when the breakout impulse loses momentum.
        ROI, stoploss and trailing-stop remain additional exit mechanisms.
        """
        long_exit = (
            (
                qtpylib.crossed_below(
                    dataframe["close"],
                    dataframe["ema20"],
                )
                | qtpylib.crossed_below(
                    dataframe["rsi"],
                    48,
                )
            )
            & (dataframe["volume"] > 0)
        )

        short_exit = (
            (
                qtpylib.crossed_above(
                    dataframe["close"],
                    dataframe["ema20"],
                )
                | qtpylib.crossed_above(
                    dataframe["rsi"],
                    52,
                )
            )
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[
            long_exit,
            ["exit_long", "exit_tag"],
        ] = (
            1,
            "momentum_faded_long",
        )

        dataframe.loc[
            short_exit,
            ["exit_short", "exit_tag"],
        ] = (
            1,
            "momentum_faded_short",
        )

        return dataframe


class CrossSqueezeExpansion15m(_CrossSqueezeBase15m):
    """
    Main strategy.

    Logic:
    - trades 15m volatility expansion after Bollinger compression;
    - allows long and short;
    - uses 2x leverage;
    - targets 7% wallet equity as margin per position.
    """

    strategy_leverage = 2.0


class CrossSqueezeExpansion4HFilter15m(_CrossSqueezeBase15m):
    """
    Conservative version.

    Uses the same 15m breakout entry, but only:
    - longs when EMA50 > EMA200 on 4h;
    - shorts when EMA50 < EMA200 on 4h.

    Expected effect:
    - fewer trades;
    - fewer counter-trend entries;
    - lower cross-wallet pressure during noisy periods.
    """

    strategy_leverage = 2.0

    # EMA200 on the 4h informative timeframe needs additional warm-up data.
    startup_candle_count = 800

    @informative("4h")
    def populate_indicators_4h(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def _long_regime_filter(self, dataframe: DataFrame) -> Series:
        return dataframe["ema50_4h"] > dataframe["ema200_4h"]

    def _short_regime_filter(self, dataframe: DataFrame) -> Series:
        return dataframe["ema50_4h"] < dataframe["ema200_4h"]


class CrossSqueezeSafe15m(_CrossSqueezeBase15m):
    """
    Reduced-leverage benchmark strategy.

    Same signal family as the main strategy, but:
    - leverage reduced to 1.5x;
    - smaller leveraged stoploss;
    - smaller ROI and trailing thresholds.

    Suitable as a low-risk comparison strategy for a 100 USDT wallet.
    """

    strategy_leverage = 1.5

    # At 1.5x leverage:
    # -3.0% trade PnL ~= -2.0% underlying price movement.
    stoploss = -0.030

    minimal_roi = {
        "0": 0.063,      # ~= +4.2% underlying move at 1.5x
        "240": 0.036,
        "720": 0.000,
    }

    trailing_stop = True
    trailing_stop_positive = 0.0195
    trailing_stop_positive_offset = 0.036
    trailing_only_offset_is_reached = True
