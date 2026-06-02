from datetime import datetime
from typing import Optional

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.persistence import Order, Trade
from freqtrade.strategy import IStrategy, stoploss_from_absolute


class BinanceFuturesAtrStrategy(IStrategy):
    """
    Осторожная futures-стратегия для dry-run.

    Важно:
    - работает с long и short;
    - плечо принудительно 1.0, то есть без усиления риска;
    - стоп и тейк считаются от ATR;
    - это техническая стратегия для проверки инфраструктуры, а не готовая торговая система.
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True
    startup_candle_count: int = 400

    minimal_roi = {"0": 10}
    stoploss = -0.15
    use_custom_stoploss = True
    trailing_stop = False

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    ema_fast = 50
    ema_slow = 200
    rsi_period = 14
    rsi_long_entry = 35
    rsi_long_exit = 70
    rsi_short_entry = 65
    rsi_short_exit = 30
    atr_period = 14
    atr_multiplier = 2.0
    risk_reward = 1.5
    risk_per_trade = 0.01

    # --- НАСТРОЙКИ РАЗМЕРА СДЕЛКИ И ПЛЕЧА ---
    # Целевое плечо: берём 50x, но не выше лимита биржи для конкретной пары.
    target_leverage = 50.0
    # МАКС. ширина стопа в долях ЦЕНЫ (не считая плечо).
    # При 50x ликвидация наступает примерно при -2% по цене, поэтому стоп
    # ставим ЗАМЕТНО ближе (1%), чтобы выйти ДО ликвидации.
    # Итоговый стоп = min(2*ATR, max_stop_pct). 0.01 = 1% движения цены.
    max_stop_pct = 0.01
    # Целевая СТОИМОСТЬ ПОЗИЦИИ (нотионал) в USDT — держим постоянной.
    # Маржа (собственные средства) = target_notional / фактическое плечо.
    # Пример: плечо 50 -> маржа 2 USDT; плечо 25 -> маржа 4 USDT. Нотионал всегда 100.
    target_notional = 100.0

    @property
    def protections(self) -> list[dict]:
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 2,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 48,
                "trade_limit": 10,
                "stop_duration_candles": 12,
                "max_allowed_drawdown": 0.2,
            },
        ]

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
        Плечо = 50x, но не выше максимума, который биржа даёт по этой паре.
        Если по паре доступно меньше 50 (напр. 25), берём максимум доступного.
        """
        return min(self.target_leverage, max_leverage)

    # ---- Русские уведомления в Telegram при заполнении ордера ----
    # Вызывается после ИСПОЛНЕНИЯ любого ордера (вход/выход/стоп).
    # Свои сообщения шлём через self.dp.send_msg() — они приходят в Telegram,
    # если в конфиге включены allow_custom_messages и notification_settings.strategy_msg.
    def order_filled(
        self, pair: str, trade: Trade, order: Order, current_time: datetime, **kwargs
    ) -> None:
        напр = "ШОРТ" if trade.is_short else "ЛОНГ"   # направление сделки
        плечо = f"{trade.leverage:.0f}x" if trade.leverage else "1x"

        if order.ft_is_entry:
            # ВХОД в сделку
            цена = order.safe_filled and order.average or trade.open_rate
            текст = (
                f"🟢 ВХОД в сделку\n"
                f"Пара: {pair}\n"
                f"Направление: {напр}\n"
                f"Цена входа: {trade.open_rate:.4f}\n"
                f"Плечо: {плечо}\n"
                f"Размер (маржа): {trade.stake_amount:.2f} USDT"
            )
        else:
            # ВЫХОД из сделки (или частичный/стоп) — показываем результат
            profit_abs = trade.close_profit_abs if trade.close_profit_abs is not None else (trade.realized_profit or 0.0)
            profit_pct = (trade.close_profit or 0.0) * 100
            знак = "✅ ПРИБЫЛЬ" if profit_abs >= 0 else "🔴 УБЫТОК"
            причина = trade.exit_reason or "—"
            # перевод частых причин выхода на русский
            причины = {
                "atr_take_profit": "тейк-профит (ATR)",
                "stop_loss": "стоп-лосс",
                "stoploss_on_exchange": "стоп-лосс (на бирже)",
                "trailing_stop_loss": "трейлинг-стоп",
                "exit_signal": "сигнал выхода (RSI)",
                "liquidation": "ЛИКВИДАЦИЯ",
                "roi": "достигнут ROI",
                "force_exit": "ручной выход",
            }
            причина_ру = причины.get(причина, причина)
            текст = (
                f"{знак} — выход из сделки\n"
                f"Пара: {pair}\n"
                f"Направление: {напр}\n"
                f"Причина: {причина_ру}\n"
                f"Результат: {profit_abs:+.2f} USDT ({profit_pct:+.2f}%)"
            )

        # always_send=True — чтобы сообщение пришло гарантированно, а не раз в свечу
        self.dp.send_msg(текст, always_send=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] > dataframe["ema_slow"])
                & qtpylib.crossed_above(dataframe["rsi"], self.rsi_long_entry)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        dataframe.loc[
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & qtpylib.crossed_below(dataframe["rsi"], self.rsi_short_entry)
                & (dataframe["volume"] > 0)
            ),
            "enter_short",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            qtpylib.crossed_above(dataframe["rsi"], self.rsi_long_exit)
            & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1

        dataframe.loc[
            qtpylib.crossed_below(dataframe["rsi"], self.rsi_short_exit)
            & (dataframe["volume"] > 0),
            "exit_short",
        ] = 1

        return dataframe

    def _atr_at_entry(self, pair: str, trade: Trade) -> Optional[float]:
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
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> Optional[float]:
        atr_at_entry = self._atr_at_entry(pair, trade)
        if atr_at_entry is None or trade.open_rate <= 0:
            return None

        # Дистанция стопа = меньшее из (2*ATR) и (1% цены входа).
        # Так при высоком плече стоп не уходит дальше зоны ликвидации.
        atr_distance = self.atr_multiplier * atr_at_entry
        cap_distance = self.max_stop_pct * trade.open_rate
        distance = min(atr_distance, cap_distance)

        if trade.is_short:
            stop_price = trade.open_rate + distance
        else:
            stop_price = trade.open_rate - distance

        return stoploss_from_absolute(
            stop_price,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        atr_at_entry = self._atr_at_entry(pair, trade)
        if atr_at_entry is None or trade.open_rate <= 0:
            return None

        # risk_ratio — движение цены до стопа (в долях, БЕЗ плеча).
        # Используем ту же дистанцию, что и в стопе: min(2*ATR, 1% цены).
        # current_profit уже учитывает плечо, поэтому цель умножаем на плечо.
        distance = min(self.atr_multiplier * atr_at_entry, self.max_stop_pct * trade.open_rate)
        risk_ratio = distance / trade.open_rate
        take_profit_ratio = self.risk_reward * risk_ratio * trade.leverage

        if current_profit >= take_profit_ratio:
            return "atr_take_profit"

        return None

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
        # РАЗМЕР СДЕЛКИ ПО ПРАВИЛУ "ПОСТОЯННЫЙ НОТИОНАЛ".
        # stake здесь = МАРЖА (собственные средства, без плеча).
        # Нотионал (стоимость позиции) = stake * leverage. Мы хотим нотионал = target_notional (100).
        #   => stake (маржа) = target_notional / leverage
        # Плечо 50 -> маржа 2 USDT (нотионал 100).
        # Плечо 25 -> маржа 4 USDT (нотионал 100).
        lev = leverage if leverage and leverage > 0 else 1.0
        stake = self.target_notional / lev   # требуемая маржа

        # Уважаем лимиты биржи/конфига, чтобы Freqtrade не отверг ордер.
        if min_stake is not None:
            stake = max(stake, min_stake)
        return min(stake, max_stake)
