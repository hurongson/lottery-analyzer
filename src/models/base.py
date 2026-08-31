"""
彩种抽象基类
定义统一的彩种接口，所有具体彩种继承此类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
import random


class BaseLottery(ABC):
    """彩种基类"""

    @property
    @abstractmethod
    def lottery_type(self) -> str:
        """彩种标识，如 'ssq'"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """彩种名称，如 '双色球'"""
        pass

    @property
    @abstractmethod
    def red_count(self) -> int:
        """红球个数"""
        pass

    @property
    @abstractmethod
    def red_range(self) -> Tuple[int, int]:
        """红球范围 (min, max)"""
        pass

    @property
    @abstractmethod
    def blue_count(self) -> int:
        """蓝球个数"""
        pass

    @property
    @abstractmethod
    def blue_range(self) -> Tuple[int, int]:
        """蓝球范围 (min, max)"""
        pass

    @property
    @abstractmethod
    def ticket_price(self) -> float:
        """单注价格"""
        pass

    @abstractmethod
    def check_prize(self, ticket_red: List[int], ticket_blue: List[int],
                    draw_red: List[int], draw_blue: List[int]) -> Optional[int]:
        """
        检查中奖等级
        返回奖级编号（1为最高），未中奖返回 None
        """
        pass

    @abstractmethod
    def get_prize_amount(self, tier: int) -> float:
        """获取指定奖级的奖金"""
        pass

    def generate_random_ticket(self, seed: int = None) -> Dict:
        """生成一注随机号码"""
        rng = random.Random(seed) if seed is not None else random
        red_min, red_max = self.red_range
        reds = sorted(rng.sample(range(red_min, red_max + 1), self.red_count))
        blue_min, blue_max = self.blue_range
        blues = sorted(rng.sample(range(blue_min, blue_max + 1), self.blue_count))
        return {"red_balls": reds, "blue_balls": blues}

    def is_valid_ticket(self, red_balls: List[int], blue_balls: List[int]) -> bool:
        """验证一注号码是否合法"""
        red_min, red_max = self.red_range
        blue_min, blue_max = self.blue_range
        if len(red_balls) != self.red_count:
            return False
        if len(set(red_balls)) != len(red_balls):
            return False
        if any(r < red_min or r > red_max for r in red_balls):
            return False
        if len(blue_balls) != self.blue_count:
            return False
        if len(set(blue_balls)) != len(blue_balls):
            return False
        if any(b < blue_min or b > blue_max for b in blue_balls):
            return False
        return True

    def count_matches(self, ticket_red: List[int], ticket_blue: List[int],
                      draw_red: List[int], draw_blue: List[int]) -> Tuple[int, int]:
        """计算红蓝球命中个数"""
        red_match = len(set(ticket_red) & set(draw_red))
        blue_match = len(set(ticket_blue) & set(draw_blue))
        return red_match, blue_match
