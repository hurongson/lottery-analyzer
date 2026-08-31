"""
大乐透模型实现
"""
from typing import List, Optional, Tuple

from config import LOTTERY_RULES
from .base import BaseLottery


class DLTLottery(BaseLottery):
    """大乐透"""

    def __init__(self):
        self._rules = LOTTERY_RULES["dlt"]

    @property
    def lottery_type(self) -> str:
        return "dlt"

    @property
    def name(self) -> str:
        return self._rules["name"]

    @property
    def red_count(self) -> int:
        return self._rules["red_count"]

    @property
    def red_range(self) -> Tuple[int, int]:
        return (self._rules["red_min"], self._rules["red_max"])

    @property
    def blue_count(self) -> int:
        return self._rules["blue_count"]

    @property
    def blue_range(self) -> Tuple[int, int]:
        return (self._rules["blue_min"], self._rules["blue_max"])

    @property
    def ticket_price(self) -> float:
        return self._rules["ticket_price"]

    def check_prize(self, ticket_red: List[int], ticket_blue: List[int],
                    draw_red: List[int], draw_blue: List[int]) -> Optional[int]:
        """
        大乐透中奖规则：
        一等奖: 5前区 + 2后区
        二等奖: 5前区 + 1后区
        三等奖: 5前区 + 0后区
        四等奖: 4前区 + 2后区
        五等奖: 4前区 + 1后区
        六等奖: 3前区 + 2后区
        七等奖: 4前区 + 0后区
        八等奖: 3前区 + 1后区
        九等奖: 2前区 + 2后区
        """
        red_match, blue_match = self.count_matches(ticket_red, ticket_blue, draw_red, draw_blue)

        prize_map = [
            (5, 2, 1), (5, 1, 2), (5, 0, 3),
            (4, 2, 4), (4, 1, 5), (3, 2, 6),
            (4, 0, 7), (3, 1, 8), (2, 2, 9),
        ]
        for r, b, tier in prize_map:
            if red_match == r and blue_match == b:
                return tier
        return None

    def get_prize_amount(self, tier: int) -> float:
        return self._rules["prize_amounts"].get(tier, 0)

    def get_prize_desc(self, tier: int) -> str:
        return self._rules["prize_tiers"].get(tier, {}).get("desc", "未知")
