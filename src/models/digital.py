"""
数字型彩票模型（福彩3D、排列三、排列五、七星彩）
特点：数字可重复，有位置概念
"""
from typing import List, Dict, Tuple, Optional
import random
from .base import BaseLottery
from config import LOTTERY_RULES


class DigitalLottery(BaseLottery):
    """数字型彩票基类"""

    def __init__(self, lottery_type: str):
        self._lottery_type = lottery_type
        self._rules = LOTTERY_RULES[lottery_type]

    @property
    def lottery_type(self) -> str:
        return self._lottery_type

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

    def generate_random_ticket(self, seed: int = None) -> Dict:
        """生成一注随机号码（数字可重复）"""
        rng = random.Random(seed) if seed is not None else random
        red_min, red_max = self.red_range
        reds = [rng.randint(red_min, red_max) for _ in range(self.red_count)]
        blue_min, blue_max = self.blue_range
        blues = [rng.randint(blue_min, blue_max) for _ in range(self.blue_count)]
        return {"red_balls": reds, "blue_balls": blues}

    def is_valid_ticket(self, red_balls: List[int], blue_balls: List[int]) -> bool:
        """验证号码是否合法（数字可重复）"""
        red_min, red_max = self.red_range
        blue_min, blue_max = self.blue_range
        if len(red_balls) != self.red_count:
            return False
        if any(r < red_min or r > red_max for r in red_balls):
            return False
        if len(blue_balls) != self.blue_count:
            return False
        if any(b < blue_min or b > blue_max for b in blue_balls):
            return False
        return True

    def check_prize(self, ticket_red: List[int], ticket_blue: List[int],
                    draw_red: List[int], draw_blue: List[int]) -> Optional[int]:
        """检查中奖等级（数字型彩票按位置匹配）"""
        # 七星彩：按位置匹配
        if self._lottery_type == "qxc":
            all_ticket = ticket_red + ticket_blue
            all_draw = draw_red + draw_blue
            pos_match = sum(1 for t, d in zip(all_ticket, all_draw) if t == d)
            for tier, info in self._rules["prize_tiers"].items():
                if pos_match >= info["pos_match"]:
                    return tier
            return None

        # 排列五：必须全部位置匹配
        if self._lottery_type == "pl5":
            if ticket_red == draw_red:
                return 1
            return None

        # 3D/排列三：直选、组三、组六
        if ticket_red == draw_red:
            return 1  # 直选

        # 组三：开奖号码有两个相同，投注号码包含相同三个数字（不限顺序）
        draw_set = set(draw_red)
        ticket_set = set(ticket_red)
        if len(draw_set) == 2 and draw_set == ticket_set:
            return 2  # 组三

        # 组六：开奖号码三个都不同，投注号码包含相同三个数字（不限顺序）
        if len(draw_set) == 3 and draw_set == ticket_set:
            return 3  # 组六

        return None

    def get_prize_amount(self, tier: int) -> float:
        return self._rules["prize_amounts"].get(tier, 0)

    def count_matches(self, ticket_red: List[int], ticket_blue: List[int],
                      draw_red: List[int], draw_blue: List[int]) -> Tuple[int, int]:
        """计算位置匹配个数"""
        red_match = sum(1 for t, d in zip(ticket_red, draw_red) if t == d)
        blue_match = sum(1 for t, d in zip(ticket_blue, draw_blue) if t == d)
        return red_match, blue_match


class FC3DLottery(DigitalLottery):
    def __init__(self):
        super().__init__("fc3d")


class PL3Lottery(DigitalLottery):
    def __init__(self):
        super().__init__("pl3")


class PL5Lottery(DigitalLottery):
    def __init__(self):
        super().__init__("pl5")


class QXCLottery(DigitalLottery):
    def __init__(self):
        super().__init__("qxc")
