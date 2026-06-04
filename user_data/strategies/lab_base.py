"""
Shared helpers for the three Binance Futures dry-run strategies.

This module intentionally does not define an IStrategy subclass.  Freqtrade
should list and run only the three concrete strategies in this folder.
"""

from datetime import datetime
from typing import Optional


class LabBaseStrategy:
    """Mixin with shared risk, leverage, stake and metadata helpers."""

    INTERFACE_VERSION = 3
    can_short = True
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    position_adjustment_enable = False
    ignore_roi_if_entry_signal = False

    timeframe = "5m"
    lev: float = 3.0
    margin_per_position: float = 10.0
    max_hold_minutes: int = 120
    cooldown_candles: int = 3
    startup_candle_count: int = 300

    stoploss = -0.99
    minimal_roi = {"0": 10.0}
    trailing_stop = False
    trailing_stop_positive = 0.0
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False
    use_custom_stake_amount = True

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": int(self.cooldown_candles),
            }
        ]

    @classmethod
    def parameter_snapshot(cls) -> dict:
        """Small immutable snapshot stored in the dashboard trade journal."""
        return {
            "strategy": cls.__name__,
            "timeframe": cls.timeframe,
            "can_short": cls.can_short,
            "leverage": cls.lev,
            "margin_per_position": cls.margin_per_position,
            "max_hold_minutes": cls.max_hold_minutes,
            "cooldown_candles": cls.cooldown_candles,
            "startup_candle_count": cls.startup_candle_count,
            "stoploss": cls.stoploss,
            "minimal_roi": cls.minimal_roi,
            "trailing_stop": cls.trailing_stop,
            "trailing_stop_positive": cls.trailing_stop_positive,
            "trailing_stop_positive_offset": cls.trailing_stop_positive_offset,
            "trailing_only_offset_is_reached": cls.trailing_only_offset_is_reached,
        }

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
        return min(float(self.lev), float(max_leverage))

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
        target = float(self.margin_per_position)
        if min_stake is not None and target < float(min_stake):
            return 0.0
        return min(target, float(max_stake))

    def _max_hold_exit(self, trade, current_time: datetime) -> Optional[str]:
        open_dt = trade.open_date_utc
        held_min = (current_time - open_dt).total_seconds() / 60.0
        if held_min >= float(self.max_hold_minutes):
            return "max_hold"
        return None

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        return self._max_hold_exit(trade, current_time)
