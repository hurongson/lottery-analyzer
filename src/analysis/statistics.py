"""
统计分析引擎
计算彩票历史数据的各项统计指标
"""
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
import numpy as np
import pandas as pd

from src.models import get_lottery


class LotteryStatistics:
    """彩票统计分析器"""

    def __init__(self, lottery_type: str = "ssq"):
        self.lottery_type = lottery_type
        self.lottery = get_lottery(lottery_type)
        self.red_min, self.red_max = self.lottery.red_range
        self.blue_min, self.blue_max = self.lottery.blue_range

    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        执行完整统计分析
        df: 包含 red_balls, blue_balls 列的 DataFrame
        """
        if df.empty:
            return {}

        return {
            "basic": self._basic_stats(df),
            "frequency": self._frequency_analysis(df),
            "omission": self._omission_analysis(df),
            "parity": self._parity_analysis(df),
            "size": self._size_analysis(df),
            "sum_value": self._sum_analysis(df),
            "span": self._span_analysis(df),
            "zone": self._zone_analysis(df),
            "consecutive": self._consecutive_analysis(df),
            "repeat": self._repeat_analysis(df),
            "cooccurrence": self._cooccurrence_analysis(df),
        }

    def _basic_stats(self, df: pd.DataFrame) -> Dict:
        """基础统计"""
        total = len(df)
        all_reds = [n for balls in df["red_balls"] for n in balls]
        all_blues = [n for balls in df["blue_balls"] for n in balls]
        return {
            "total_draws": total,
            "date_range": (df["draw_date"].iloc[0], df["draw_date"].iloc[-1]) if "draw_date" in df.columns else None,
            "red_mean": np.mean(all_reds),
            "red_std": np.std(all_reds),
            "blue_mean": np.mean(all_blues),
            "blue_std": np.std(all_blues),
        }

    def _frequency_analysis(self, df: pd.DataFrame) -> Dict:
        """
        频率分析（冷热号）
        返回每个号码的出现次数、频率、排名
        """
        red_counter = Counter()
        blue_counter = Counter()
        for balls in df["red_balls"]:
            red_counter.update(balls)
        for balls in df["blue_balls"]:
            blue_counter.update(balls)

        total = len(df)
        red_freq = {}
        for n in range(self.red_min, self.red_max + 1):
            count = red_counter.get(n, 0)
            red_freq[n] = {
                "count": count,
                "frequency": count / total if total > 0 else 0,
                "expected": total * (self.lottery.red_count / (self.red_max - self.red_min + 1)),
            }

        blue_freq = {}
        for n in range(self.blue_min, self.blue_max + 1):
            count = blue_counter.get(n, 0)
            blue_freq[n] = {
                "count": count,
                "frequency": count / total if total > 0 else 0,
                "expected": total * (self.lottery.blue_count / (self.blue_max - self.blue_min + 1)),
            }

        # 冷热排名
        red_ranking = sorted(red_freq.items(), key=lambda x: x[1]["count"], reverse=True)
        blue_ranking = sorted(blue_freq.items(), key=lambda x: x[1]["count"], reverse=True)

        return {
            "red": red_freq,
            "blue": blue_freq,
            "red_hot10": [n for n, _ in red_ranking[:10]],
            "red_cold10": [n for n, _ in red_ranking[-10:]],
            "blue_hot5": [n for n, _ in blue_ranking[:5]],
            "blue_cold5": [n for n, _ in blue_ranking[-5:]],
        }

    def _omission_analysis(self, df: pd.DataFrame) -> Dict:
        """
        遗漏值分析
        计算每个号码距离最近一次出现的期数，以及历史最大遗漏
        """
        red_last_seen = {}
        red_max_gap = {}
        red_current_gap = {}
        blue_last_seen = {}
        blue_max_gap = {}
        blue_current_gap = {}

        for n in range(self.red_min, self.red_max + 1):
            red_last_seen[n] = -1
            red_max_gap[n] = 0
        for n in range(self.blue_min, self.blue_max + 1):
            blue_last_seen[n] = -1
            blue_max_gap[n] = 0

        for idx, row in df.iterrows():
            for n in row["red_balls"]:
                if red_last_seen[n] >= 0:
                    gap = idx - red_last_seen[n]
                    red_max_gap[n] = max(red_max_gap[n], gap)
                red_last_seen[n] = idx
            for n in row["blue_balls"]:
                if blue_last_seen[n] >= 0:
                    gap = idx - blue_last_seen[n]
                    blue_max_gap[n] = max(blue_max_gap[n], gap)
                blue_last_seen[n] = idx

        total = len(df)
        for n in range(self.red_min, self.red_max + 1):
            red_current_gap[n] = total - 1 - red_last_seen[n] if red_last_seen[n] >= 0 else total
        for n in range(self.blue_min, self.blue_max + 1):
            blue_current_gap[n] = total - 1 - blue_last_seen[n] if blue_last_seen[n] >= 0 else total

        return {
            "red_current_gap": red_current_gap,
            "red_max_gap": red_max_gap,
            "blue_current_gap": blue_current_gap,
            "blue_max_gap": blue_max_gap,
            "red_top_gap": sorted(red_current_gap.items(), key=lambda x: x[1], reverse=True)[:10],
            "blue_top_gap": sorted(blue_current_gap.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    def _parity_analysis(self, df: pd.DataFrame) -> Dict:
        """奇偶比分析"""
        parity_dist = Counter()
        for balls in df["red_balls"]:
            odd = sum(1 for n in balls if n % 2 == 1)
            even = len(balls) - odd
            parity_dist[f"{odd}:{even}"] += 1
        total = len(df)
        return {
            "distribution": dict(parity_dist),
            "percentage": {k: v / total for k, v in parity_dist.items()},
            "most_common": parity_dist.most_common(3),
        }

    def _size_analysis(self, df: pd.DataFrame) -> Dict:
        """大小比分析（以中位数为界）"""
        mid = (self.red_min + self.red_max) / 2
        size_dist = Counter()
        for balls in df["red_balls"]:
            big = sum(1 for n in balls if n > mid)
            small = len(balls) - big
            size_dist[f"{big}:{small}"] += 1
        total = len(df)
        return {
            "distribution": dict(size_dist),
            "percentage": {k: v / total for k, v in size_dist.items()},
            "most_common": size_dist.most_common(3),
        }

    def _sum_analysis(self, df: pd.DataFrame) -> Dict:
        """和值分析"""
        sums = [sum(balls) for balls in df["red_balls"]]
        return {
            "min": min(sums),
            "max": max(sums),
            "mean": np.mean(sums),
            "median": np.median(sums),
            "std": np.std(sums),
            "recent_10": sums[-10:],
            "trend": sums[-20:],
        }

    def _span_analysis(self, df: pd.DataFrame) -> Dict:
        """跨度分析（最大值-最小值）"""
        spans = [max(balls) - min(balls) for balls in df["red_balls"]]
        return {
            "min": min(spans),
            "max": max(spans),
            "mean": np.mean(spans),
            "median": np.median(spans),
            "distribution": dict(Counter(spans)),
            "recent_10": spans[-10:],
        }

    def _zone_analysis(self, df: pd.DataFrame) -> Dict:
        """
        三区分布分析
        将红球分为三个区间：低(1-11), 中(12-22), 高(23-33)
        """
        zone_ranges = [
            (1, 11, "低区"),
            (12, 22, "中区"),
            (23, 33, "高区"),
        ]
        zone_dist = Counter()
        for balls in df["red_balls"]:
            counts = []
            for low, high, _ in zone_ranges:
                counts.append(sum(1 for n in balls if low <= n <= high))
            zone_dist[f"{counts[0]}:{counts[1]}:{counts[2]}"] += 1

        total = len(df)
        return {
            "zone_ranges": [(z[0], z[1], z[2]) for z in zone_ranges],
            "distribution": dict(zone_dist),
            "percentage": {k: v / total for k, v in zone_dist.items()},
            "most_common": zone_dist.most_common(3),
        }

    def _consecutive_analysis(self, df: pd.DataFrame) -> Dict:
        """连号分析"""
        consec_counts = []
        has_consec = 0
        for balls in df["red_balls"]:
            sorted_balls = sorted(balls)
            max_consec = 1
            current = 1
            for i in range(1, len(sorted_balls)):
                if sorted_balls[i] == sorted_balls[i-1] + 1:
                    current += 1
                    max_consec = max(max_consec, current)
                else:
                    current = 1
            consec_counts.append(max_consec)
            if max_consec >= 2:
                has_consec += 1

        total = len(df)
        return {
            "probability": has_consec / total if total > 0 else 0,
            "max_consec_distribution": dict(Counter(consec_counts)),
            "recent_10": consec_counts[-10:],
        }

    def _repeat_analysis(self, df: pd.DataFrame) -> Dict:
        """重号分析（与上一期相同的号码个数）"""
        repeat_counts = []
        for i in range(1, len(df)):
            prev = set(df["red_balls"].iloc[i-1])
            curr = set(df["red_balls"].iloc[i])
            repeat_counts.append(len(prev & curr))

        if not repeat_counts:
            return {"distribution": {}, "mean": 0, "recent_10": []}

        return {
            "distribution": dict(Counter(repeat_counts)),
            "mean": np.mean(repeat_counts),
            "probability_at_least_one": sum(1 for c in repeat_counts if c >= 1) / len(repeat_counts),
            "recent_10": repeat_counts[-10:],
        }

    def _cooccurrence_analysis(self, df: pd.DataFrame, top_n: int = 15) -> Dict:
        """
        关联分析（号码共现）
        找出最常一起出现的号码对
        """
        pair_counter = Counter()
        for balls in df["red_balls"]:
            sorted_balls = sorted(balls)
            for i in range(len(sorted_balls)):
                for j in range(i+1, len(sorted_balls)):
                    pair_counter[(sorted_balls[i], sorted_balls[j])] += 1

        return {
            "top_pairs": [
                {"pair": list(pair), "count": count}
                for pair, count in pair_counter.most_common(top_n)
            ],
            "total_pairs": len(pair_counter),
        }

    def get_recent_trends(self, df: pd.DataFrame, periods: int = 30) -> Dict:
        """获取近期趋势（最近N期的统计）"""
        if len(df) < periods:
            periods = len(df)
        recent_df = df.tail(periods).copy()
        return self.analyze(recent_df)

    def get_number_score(self, df: pd.DataFrame, method: str = "composite") -> Dict:
        """
        综合号码评分（用于选号参考）
        method: 'frequency' 频率优先, 'omission' 遗漏优先, 'composite' 综合
        返回红球和蓝球的评分字典
        """
        analysis = self.analyze(df)
        freq = analysis["frequency"]
        omission = analysis["omission"]
        total = len(df)

        red_scores = {}
        for n in range(self.red_min, self.red_max + 1):
            if method == "frequency":
                # 频率越高分越高
                red_scores[n] = freq["red"][n]["frequency"]
            elif method == "omission":
                # 遗漏越大分越高（冷号回补假设）
                max_gap = max(omission["red_current_gap"].values()) if omission["red_current_gap"] else 1
                red_scores[n] = omission["red_current_gap"][n] / max_gap if max_gap > 0 else 0
            else:
                # 综合：频率标准化 + 遗漏标准化
                freq_score = freq["red"][n]["frequency"]
                max_freq = max(v["frequency"] for v in freq["red"].values()) if freq["red"] else 1
                max_gap = max(omission["red_current_gap"].values()) if omission["red_current_gap"] else 1
                gap_score = omission["red_current_gap"][n] / max_gap if max_gap > 0 else 0
                red_scores[n] = 0.5 * (freq_score / max_freq if max_freq > 0 else 0) + 0.5 * gap_score

        blue_scores = {}
        for n in range(self.blue_min, self.blue_max + 1):
            if method == "frequency":
                blue_scores[n] = freq["blue"][n]["frequency"]
            elif method == "omission":
                max_gap = max(omission["blue_current_gap"].values()) if omission["blue_current_gap"] else 1
                blue_scores[n] = omission["blue_current_gap"][n] / max_gap if max_gap > 0 else 0
            else:
                freq_score = freq["blue"][n]["frequency"]
                max_freq = max(v["frequency"] for v in freq["blue"].values()) if freq["blue"] else 1
                max_gap = max(omission["blue_current_gap"].values()) if omission["blue_current_gap"] else 1
                gap_score = omission["blue_current_gap"][n] / max_gap if max_gap > 0 else 0
                blue_scores[n] = 0.5 * (freq_score / max_freq if max_freq > 0 else 0) + 0.5 * gap_score

        return {"red": red_scores, "blue": blue_scores}
