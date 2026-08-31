"""
双色球模型实现
"""
from typing import List, Optional, Tuple

from config import LOTTERY_RULES
from .base import BaseLottery


class SSQLottery(BaseLottery):
    """双色球"""

    def __init__(self):
        self._rules = LOTTERY_RULES["ssq"]

    @property
    def lottery_type(self) -> str:
        return "ssq"

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
        双色球中奖规则：
        一等奖: 6红 + 1蓝
        二等奖: 6红 + 0蓝
        三等奖: 5红 + 1蓝
        四等奖: 5红 + 0蓝 或 4红 + 1蓝
        五等奖: 4红 + 0蓝 或 3红 + 1蓝
        六等奖: 2红 + 1蓝 或 1红 + 1蓝 或 0红 + 1蓝
        """
        red_match, blue_match = self.count_matches(ticket_red, ticket_blue, draw_red, draw_blue)

        if red_match == 6 and blue_match == 1:
            return 1
        elif red_match == 6 and blue_match == 0:
            return 2
        elif red_match == 5 and blue_match == 1:
            return 3
        elif red_match == 5 and blue_match == 0:
            return 4
        elif red_match == 4 and blue_match == 1:
            return 4
        elif red_match == 4 and blue_match == 0:
            return 5
        elif red_match == 3 and blue_match == 1:
            return 5
        elif red_match == 2 and blue_match == 1:
            return 6
        elif red_match == 1 and blue_match == 1:
            return 6
        elif red_match == 0 and blue_match == 1:
            return 6
        return None

    def get_prize_amount(self, tier: int) -> float:
        """获取奖金（一、二等奖为浮动奖金，取典型值）"""
        return self._rules["prize_amounts"].get(tier, 0)

    def get_prize_desc(self, tier: int) -> str:
        """获取奖级描述"""
        return self._rules["prize_tiers"].get(tier, {}).get("desc", "未知")
