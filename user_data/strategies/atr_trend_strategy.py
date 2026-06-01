# =============================================================================
#  Стратегия: AtrTrendStrategy  (Freqtrade, Binance FUTURES, ЛОНГ + ШОРТ)
# -----------------------------------------------------------------------------
#  Идея простыми словами:
#    Торгуем USDT-фьючерсы с плечом, в обе стороны.
#
#    ЛОНГ (ставка на рост):
#       - тренд вверх: EMA(50) > EMA(200);
#       - вход: RSI(14) пересекает СНИЗУ ВВЕРХ уровень 35 (выход из перепроданности);
#       - выход по сигналу: RSI пересекает вниз 70 (перекупленность ушла).
#
#    ШОРТ (ставка на падение) — зеркально:
#       - тренд вниз: EMA(50) < EMA(200);
#       - вход: RSI(14) пересекает СВЕРХУ ВНИЗ уровень 65;
#       - выход по сигналу: RSI пересекает вверх 30 (перепроданность ушла).
#
#    ОБЩЕЕ управление сделкой (и для лонга, и для шорта):
#       - СТОП-ЛОСС: 2*ATR(14) от цены входа (custom_stoploss, по цене);
#       - ТЕЙК-ПРОФИТ: риск/прибыль = 1 : 1.5 (custom_exit);
#       - РАЗМЕР ПОЗИЦИИ: риск ~1% депозита на сделку (custom_stake_amount);
#       - ПЛЕЧО: фиксированное (leverage callback), по умолчанию 3x.
#
#  Параметры (EMA/RSI/ATR/риск/плечо) собраны в блоке "ПАРАМЕТРЫ".
#  Пары и таймфрейм меняются в config.json.
# =============================================================================

from datetime import datetime
from typing import Optional

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_absolute


class AtrTrendStrategy(IStrategy):
    """Трендовая стратегия для фьючерсов: ATR-стоп, R:R=1.5, риск ~1%, плечо."""

    # ----------------------- БАЗОВЫЕ НАСТРОЙКИ -------------------------------
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True        # ФЬЮЧЕРСЫ: разрешаем шорт

    # EMA(200) — самый длинный период; берём запас (x2) для стабилизации.
    startup_candle_count: int = 400

    # ROI почти отключён: тейк-профит считаем сами в custom_exit (R:R = 1.5).
    minimal_roi = {"0": 10}

    # Аварийный стоп -15% (страховка, если ATR недоступен). Реальный стоп — ATR.
    stoploss = -0.15
    use_custom_stoploss = True
    trailing_stop = False

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # --------------------------- ПАРАМЕТРЫ ----------------------------------
    ema_fast = 50          # быстрая EMA (тренд)
    ema_slow = 200         # медленная EMA (тренд)
    rsi_period = 14        # период RSI
    rsi_long_entry = 35    # лонг-вход: RSI пробивает вверх
    rsi_long_exit = 70     # лонг-выход: RSI пробивает вниз
    rsi_short_entry = 65   # шорт-вход: RSI пробивает вниз
    rsi_short_exit = 30    # шорт-выход: RSI пробивает вверх
    atr_period = 14        # период ATR (волатильность)
    atr_multiplier = 2.0   # стоп = atr_multiplier * ATR от цены входа
    risk_reward = 1.5      # тейк = risk_reward * риск (1 : 1.5)
    risk_per_trade = 0.01  # рискуем 1% депозита на сделку
    fixed_leverage = 3.0   # фиксированное плечо

    @property
    def protections(self) -> list[dict]:
        """Защиты от серии плохих сделок и повторного входа сразу после выхода."""
        return [
            {
                "method": "CooldownPeriod",      # пауза 2 свечи после выхода
                "stop_duration_candles": 2,
            },
            {
                "method": "StoplossGuard",       # 4 стопа за 24 свечи -> пауза 12
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",         # просадка >20% за 48 свечей -> пауза
                "lookback_period_candles": 48,
                "trade_limit": 10,
                "stop_duration_candles": 12,
                "max_allowed_drawdown": 0.2,
            },
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Считаем индикаторы один раз для всей истории свечей."""
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Условия ВХОДА: лонг в восходящем тренде, шорт в нисходящем."""
        # --- ЛОНГ: тренд вверх + RSI пробил 35 снизу вверх ---
        dataframe.loc[
            (
                (dataframe["ema_fast"] > dataframe["ema_slow"])
                & (qtpylib.crossed_above(dataframe["rsi"], self.rsi_long_entry))
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "long_rsi_oversold")

        # --- ШОРТ: тренд вниз + RSI пробил 65 сверху вниз ---
        dataframe.loc[
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & (qtpylib.crossed_below(dataframe["rsi"], self.rsi_short_entry))
                & (dataframe["volume"] > 0)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "short_rsi_overbought")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Сигнальный ВЫХОД (помимо стопа/тейка из колбэков)."""
        # Лонг закрываем, когда RSI уходит вниз из зоны перекупленности (70)
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe["rsi"], self.rsi_long_exit)
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1

        # Шорт закрываем, когда RSI уходит вверх из зоны перепроданности (30)
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe["rsi"], self.rsi_short_exit)
                & (dataframe["volume"] > 0)
            ),
            "exit_short",
        ] = 1
        return dataframe

    def _atr_at_entry(self, pair: str, trade: Trade) -> Optional[float]:
        """Вспомогательное: вернуть ATR на свече, где открылась сделка."""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None

        entry_candles = dataframe.loc[dataframe["date"] <= trade.open_date_utc]
        if entry_candles.empty:
            return None

        atr_value = entry_candles.iloc[-1]["atr"]
        if atr_value is None or np.isnan(atr_value):
            return None

        return float(atr_value)

    def custom_stoploss(
        self, pair: str, trade: Trade, current_time: datetime,
        current_rate: float, current_profit: float, after_fill: bool,
        **kwargs,
    ) -> Optional[float]:
        """
        СТОП-ЛОСС = 2*ATR от цены входа.
        Для ЛОНГА стоп НИЖЕ входа, для ШОРТА — ВЫШЕ входа (учитываем trade.is_short).
        stoploss_from_absolute() переводит абсолютную цену стопа в относительный
        формат, который ждёт Freqtrade. Возврат None -> аварийный stoploss (-15%).
        """
        atr_at_entry = self._atr_at_entry(pair, trade)
        if atr_at_entry is None or trade.open_rate <= 0:
            return None

        distance = self.atr_multiplier * atr_at_entry
        if trade.is_short:
            stop_price = trade.open_rate + distance   # шорт: стоп выше входа
        else:
            stop_price = trade.open_rate - distance   # лонг: стоп ниже входа

        return stoploss_from_absolute(
            stop_price, current_rate,
            is_short=trade.is_short, leverage=trade.leverage,
        )

    def custom_exit(
        self, pair: str, trade: Trade, current_time: datetime,
        current_rate: float, current_profit: float, **kwargs,
    ) -> Optional[str]:
        """
        ТЕЙК-ПРОФИТ по R:R = 1 : 1.5.
        Риск (в долях, БЕЗ учёта плеча) = 2*ATR(вход) / цена входа.
        current_profit уже учитывает плечо, поэтому цель тоже умножаем на плечо.
        """
        atr_at_entry = self._atr_at_entry(pair, trade)
        if atr_at_entry is None or trade.open_rate <= 0:
            return None

        risk_ratio = (self.atr_multiplier * atr_at_entry) / trade.open_rate
        take_profit_ratio = self.risk_reward * risk_ratio * trade.leverage

        if current_profit >= take_profit_ratio:
            return "atr_take_profit"
        return None

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: Optional[float], max_stake: float,
        leverage: float, entry_tag: Optional[str], side: str,
        **kwargs,
    ) -> float:
        """
        РАЗМЕР ПОЗИЦИИ (маржа) под риск ~1% депозита.
        stake здесь = собственная МАРЖА (без плеча). Чтобы при срабатывании стопа
        потерять ~risk_per_trade капитала:
            margin = (капитал * risk_per_trade) / stop_distance / leverage
        Плечо НЕ увеличивает риск: оно лишь уменьшает требуемую маржу.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return proposed_stake

        atr_now = dataframe.iloc[-1]["atr"]
        if atr_now is None or np.isnan(atr_now) or current_rate <= 0:
            return proposed_stake

        stop_distance = (self.atr_multiplier * float(atr_now)) / current_rate
        if stop_distance <= 0:
            return proposed_stake

        try:
            total_capital = self.wallets.get_total_stake_amount()
        except Exception:
            return proposed_stake

        risk_amount = total_capital * self.risk_per_trade
        lev = leverage if leverage and leverage > 0 else 1.0
        stake = risk_amount / stop_distance / lev   # требуемая маржа

        if min_stake is not None:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

    def leverage(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
        side: str, **kwargs,
    ) -> float:
        """Фиксированное плечо, но не выше лимита биржи для пары."""
        return min(self.fixed_leverage, max_leverage)
