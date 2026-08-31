"""
选号策略定义
所有策略实现统一接口，可插拔、可回测
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import random
import numpy as np
import pandas as pd

from src.models import get_lottery
from src.analysis.statistics import LotteryStatistics


class BaseStrategy(ABC):
    """选号策略基类"""

    def __init__(self, lottery_type: str = "ssq", seed: int = None):
        self.lottery_type = lottery_type
        self.lottery = get_lottery(lottery_type)
        self.seed = seed
        self.rng = random.Random(seed) if seed is not None else random.Random()

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """策略描述"""
        pass

    @abstractmethod
    def generate_tickets(self, history_df: pd.DataFrame, count: int = 5) -> List[Dict]:
        """
        根据历史数据生成候选号码
        history_df: 截至当前期的历史数据（不含目标期）
        count: 生成注数
        返回: [{"red_balls": [...], "blue_balls": [...]}, ...]
        """
        pass

    def _ensure_unique(self, tickets: List[Dict]) -> List[Dict]:
        """确保生成的注数不重复"""
        seen = set()
        unique = []
        for t in tickets:
            key = (tuple(sorted(t["red_balls"])), tuple(sorted(t["blue_balls"])))
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return unique


class RandomStrategy(BaseStrategy):
    """随机选号策略（基线）"""

    @property
    def name(self) -> str:
        return "随机选号"

    @property
    def description(self) -> str:
        return "完全随机生成号码，作为公平基线对比"

    def generate_tickets(self, history_df: pd.DataFrame, count: int = 5) -> List[Dict]:
        tickets = []
        for _ in range(count * 3):  # 多生成一些以确保唯一
            tickets.append(self.lottery.generate_random_ticket(seed=self.rng.randint(0, 2**31)))
            if len(self._ensure_unique(tickets)) >= count:
                break
        return self._ensure_unique(tickets)[:count]


class HotNumberStrategy(BaseStrategy):
    """热号优先策略（基于近期频率）"""

    def __init__(self, lottery_type: str = "ssq", seed: int = None,
                 recent_periods: int = 50, hot_ratio: float = 0.5):
        super().__init__(lottery_type, seed)
        self.recent_periods = recent_periods
        self.hot_ratio = hot_ratio  # 热号占比

    @property
    def name(self) -> str:
        return f"热号优先(近{self.recent_periods}期)"

    @property
    def description(self) -> str:
        return f"基于最近{self.recent_periods}期出现频率，优先选择高频号码"

    def generate_tickets(self, history_df: pd.DataFrame, count: int = 5) -> List[Dict]:
        if len(history_df) < 10:
            # 数据不足时退化为随机
            return RandomStrategy(self.lottery_type, self.seed).generate_tickets(history_df, count)

        recent = history_df.tail(self.recent_periods)
        stats = LotteryStatistics(self.lottery_type)
        scores = stats.get_number_score(recent, method="frequency")

        red_scores = scores["red"]
        blue_scores = scores["blue"]

        # 按评分排序
        red_sorted = sorted(red_scores.items(), key=lambda x: x[1], reverse=True)
        blue_sorted = sorted(blue_scores.items(), key=lambda x: x[1], reverse=True)

        red_min, red_max = self.lottery.red_range
        blue_min, blue_max = self.lottery.blue_range
        red_count = self.lottery.red_count
        blue_count = self.lottery.blue_count

        # 热号池（前50%）和冷号池
        hot_count = int(len(red_sorted) * self.hot_ratio)
        hot_reds = [n for n, _ in red_sorted[:hot_count]]
        cold_reds = [n for n, _ in red_sorted[hot_count:]]
        hot_blues = [n for n, _ in blue_sorted[:max(1, len(blue_sorted)//2)]]
        cold_blues = [n for n, _ in blue_sorted[max(1, len(blue_sorted)//2):]]

        tickets = []
        for _ in range(count * 5):
            # 从热号池中选大部分，冷号池选少部分
            hot_pick = max(1, int(red_count * self.hot_ratio))
            cold_pick = red_count - hot_pick
            reds = self.rng.sample(hot_reds, min(hot_pick, len(hot_reds)))
            if cold_pick > 0 and cold_reds:
                reds.extend(self.rng.sample(cold_reds, min(cold_pick, len(cold_reds))))
            reds = sorted(set(reds))
            while len(reds) < red_count:
                n = self.rng.randint(red_min, red_max)
                if n not in reds:
                    reds.append(n)
            reds = sorted(reds[:red_count])

            # 蓝球：优先热号
            if hot_blues and self.rng.random() < 0.7:
                blues = [self.rng.choice(hot_blues)]
            else:
                blues = [self.rng.choice(cold_blues)] if cold_blues else [self.rng.randint(blue_min, blue_max)]

            tickets.append({"red_balls": reds, "blue_balls": blues})
            if len(self._ensure_unique(tickets)) >= count:
                break

        return self._ensure_unique(tickets)[:count]


class ColdNumberStrategy(BaseStrategy):
    """冷号回补策略（基于遗漏值）"""

    def __init__(self, lottery_type: str = "ssq", seed: int = None,
                 recent_periods: int = 100):
        super().__init__(lottery_type, seed)
        self.recent_periods = recent_periods

    @property
    def name(self) -> str:
        return f"冷号回补(近{self.recent_periods}期)"

    @property
    def description(self) -> str:
        return f"基于遗漏值，优先选择长期未出现的号码（均值回归假设）"

    def generate_tickets(self, history_df: pd.DataFrame, count: int = 5) -> List[Dict]:
        if len(history_df) < 10:
            return RandomStrategy(self.lottery_type, self.seed).generate_tickets(history_df, count)

        recent = history_df.tail(self.recent_periods)
        stats = LotteryStatistics(self.lottery_type)
        scores = stats.get_number_score(recent, method="omission")

        red_scores = scores["red"]
        blue_scores = scores["blue"]

        red_sorted = sorted(red_scores.items(), key=lambda x: x[1], reverse=True)
        blue_sorted = sorted(blue_scores.items(), key=lambda x: x[1], reverse=True)

        # 冷号池（遗漏最大的前40%）
        cold_red_count = max(6, int(len(red_sorted) * 0.4))
        cold_reds = [n for n, _ in red_sorted[:cold_red_count]]
        cold_blues = [n for n, _ in blue_sorted[:max(3, len(blue_sorted)//3)]]

        red_min, red_max = self.lottery.red_range
        blue_min, blue_max = self.lottery.blue_range
        red_count = self.lottery.red_count

        tickets = []
        for _ in range(count * 5):
            # 从冷号池中选4个，其余随机
            cold_pick = min(4, len(cold_reds))
            reds = self.rng.sample(cold_reds, cold_pick)
            while len(reds) < red_count:
                n = self.rng.randint(red_min, red_max)
                if n not in reds:
                    reds.append(n)
            reds = sorted(reds[:red_count])

            if cold_blues and self.rng.random() < 0.6:
                blues = [self.rng.choice(cold_blues)]
            else:
                blues = [self.rng.randint(blue_min, blue_max)]

            tickets.append({"red_balls": reds, "blue_balls": blues})
            if len(self._ensure_unique(tickets)) >= count:
                break

        return self._ensure_unique(tickets)[:count]


class CompositeStrategy(BaseStrategy):
    """综合策略（频率+遗漏+结构约束）"""

    def __init__(self, lottery_type: str = "ssq", seed: int = None,
                 recent_periods: int = 50):
        super().__init__(lottery_type, seed)
        self.recent_periods = recent_periods

    @property
    def name(self) -> str:
        return f"综合策略(近{self.recent_periods}期)"

    @property
    def description(self) -> str:
        return "综合频率、遗漏值和结构约束（和值/奇偶/区间）选号"

    def generate_tickets(self, history_df: pd.DataFrame, count: int = 5) -> List[Dict]:
        if len(history_df) < 20:
            return RandomStrategy(self.lottery_type, self.seed).generate_tickets(history_df, count)

        recent = history_df.tail(self.recent_periods)
        stats = LotteryStatistics(self.lottery_type)
        analysis = stats.analyze(recent)
        scores = stats.get_number_score(recent, method="composite")

        red_scores = scores["red"]
        blue_scores = scores["blue"]

        # 历史和值范围（用于约束）
        sum_stats = analysis["sum_value"]
        sum_low = sum_stats["mean"] - sum_stats["std"]
        sum_high = sum_stats["mean"] + sum_stats["std"]

        # 最常见奇偶比和区间分布
        common_parity = analysis["parity"]["most_common"][0][0] if analysis["parity"]["most_common"] else "3:3"
        common_zone = analysis["zone"]["most_common"][0][0] if analysis["zone"]["most_common"] else "2:2:2"

        red_min, red_max = self.lottery.red_range
        blue_min, blue_max = self.lottery.blue_range
        red_count = self.lottery.red_count

        tickets = []
        attempts = 0
        while len(tickets) < count and attempts < count * 20:
            attempts += 1
            # 基于综合评分加权随机选择
            red_nums = list(red_scores.keys())
            red_weights = np.array([max(0.01, red_scores[n]) for n in red_nums])
            red_weights = red_weights / red_weights.sum()

            reds = sorted(self.rng.choices(red_nums, weights=red_weights, k=red_count * 2))
            reds = sorted(list(dict.fromkeys(reds))[:red_count])
            if len(reds) < red_count:
                remaining = [n for n in range(red_min, red_max + 1) if n not in reds]
                reds.extend(self.rng.sample(remaining, red_count - len(reds)))
                reds = sorted(reds)

            # 结构约束过滤
            s = sum(reds)
            if s < sum_low * 0.7 or s > sum_high * 1.3:
                continue

            # 蓝球
            blue_nums = list(blue_scores.keys())
            blue_weights = np.array([max(0.01, blue_scores[n]) for n in blue_nums])
            blue_weights = blue_weights / blue_weights.sum()
            blues = [int(self.rng.choices(blue_nums, weights=blue_weights, k=1)[0])]

            ticket = {"red_balls": reds, "blue_balls": blues}
            if self.lottery.is_valid_ticket(reds, blues):
                tickets.append(ticket)

        return self._ensure_unique(tickets)[:count]


def get_all_strategies(lottery_type: str = "ssq", seed: int = None) -> List[BaseStrategy]:
    """获取所有可用策略"""
    return [
        RandomStrategy(lottery_type, seed),
        HotNumberStrategy(lottery_type, seed),
        ColdNumberStrategy(lottery_type, seed),
        CompositeStrategy(lottery_type, seed),
    ]


def get_strategy_by_name(name: str, lottery_type: str = "ssq", seed: int = None) -> Optional[BaseStrategy]:
    """根据名称获取策略"""
    for s in get_all_strategies(lottery_type, seed):
        if s.name == name:
            return s
    return None
