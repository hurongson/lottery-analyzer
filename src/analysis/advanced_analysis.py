"""
增强分析模块
基于 GitHub 成熟项目的算法优化：
- 位置频率分析（positional frequency）
- 近期衰减加权（recency decay weighting）
- 极端形态检测（extreme pattern detection）
- 覆盖度优化（coverage optimization）
- 综合评分算法（composite scoring）
"""
import math
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter
import numpy as np
import pandas as pd
from config import LOTTERY_RULES


class AdvancedAnalyzer:
    """增强分析器"""

    def __init__(self, lottery_type: str):
        self.lottery_type = lottery_type
        self.rules = LOTTERY_RULES[lottery_type]
        self.is_digital = self.rules.get("is_digital", False)

    def analyze(self, df: pd.DataFrame) -> Dict:
        """执行全部增强分析"""
        if df.empty:
            return {}

        return {
            "positional_frequency": self._positional_frequency(df),
            "recency_weighted": self._recency_weighted_frequency(df),
            "extreme_patterns": self._detect_extreme_patterns(df),
            "pair_correlation": self._pair_correlation(df),
            "composite_scores": self._composite_number_scores(df),
            "optimal_sum_range": self._optimal_sum_range(df),
            "recent_trend_strength": self._recent_trend_strength(df),
        }

    def _positional_frequency(self, df: pd.DataFrame) -> Dict:
        """
        位置频率分析
        分析每个号码在各个排序位置出现的频率
        这是 megamillions-engine 的核心创新
        """
        red_count = self.rules["red_count"]
        red_min, red_max = self.rules["red_min"], self.rules["red_max"]
        all_reds = list(range(red_min, red_max + 1))

        # 初始化位置频率矩阵 [position][number]
        pos_freq = {pos: {n: 0 for n in all_reds} for pos in range(red_count)}

        for _, row in df.iterrows():
            reds = sorted(row["red_balls"]) if not self.is_digital else row["red_balls"]
            for pos, num in enumerate(reds[:red_count]):
                if pos < red_count and num in pos_freq[pos]:
                    pos_freq[pos][num] += 1

        total = len(df)
        # 计算每个位置的热门号码
        pos_hot = {}
        for pos in range(red_count):
            sorted_nums = sorted(pos_freq[pos].items(), key=lambda x: x[1], reverse=True)
            pos_hot[pos] = [n for n, c in sorted_nums[:5]]

        # 蓝球位置频率（如果有）
        blue_pos_hot = {}
        if self.rules["blue_count"] > 0:
            blue_min, blue_max = self.rules["blue_min"], self.rules["blue_max"]
            blue_freq = {n: 0 for n in range(blue_min, blue_max + 1)}
            for _, row in df.iterrows():
                for b in row["blue_balls"]:
                    if b in blue_freq:
                        blue_freq[b] += 1
            sorted_blues = sorted(blue_freq.items(), key=lambda x: x[1], reverse=True)
            blue_pos_hot = [n for n, c in sorted_blues[:5]]

        return {
            "red_positional_hot": pos_hot,
            "blue_hot": blue_pos_hot,
            "total_draws": total,
        }

    def _recency_weighted_frequency(self, df: pd.DataFrame,
                                      half_life: int = 50) -> Dict:
        """
        近期衰减加权频率
        越近的期权重越高，使用指数衰减
        half_life: 半衰期（期数），超过此期数权重减半
        """
        red_min, red_max = self.rules["red_min"], self.rules["red_max"]
        all_reds = list(range(red_min, red_max + 1))
        red_scores = {n: 0.0 for n in all_reds}

        total = len(df)
        for i, (_, row) in enumerate(df.iterrows()):
            # i=0 是最旧的，i=total-1 是最新的
            age = total - 1 - i  # 距离最新的期数
            weight = 0.5 ** (age / half_life)  # 指数衰减
            for num in row["red_balls"]:
                if num in red_scores:
                    red_scores[num] += weight

        # 归一化
        max_score = max(red_scores.values()) if red_scores else 1
        if max_score > 0:
            red_scores = {n: s / max_score for n, s in red_scores.items()}

        sorted_reds = sorted(red_scores.items(), key=lambda x: x[1], reverse=True)
        hot = [n for n, s in sorted_reds[:10]]
        cold = [n for n, s in sorted_reds[-10:]]

        # 蓝球
        blue_scores = {}
        if self.rules["blue_count"] > 0:
            blue_min, blue_max = self.rules["blue_min"], self.rules["blue_max"]
            blue_scores = {n: 0.0 for n in range(blue_min, blue_max + 1)}
            for i, (_, row) in enumerate(df.iterrows()):
                age = total - 1 - i
                weight = 0.5 ** (age / half_life)
                for num in row["blue_balls"]:
                    if num in blue_scores:
                        blue_scores[num] += weight
            max_blue = max(blue_scores.values()) if blue_scores else 1
            if max_blue > 0:
                blue_scores = {n: s / max_blue for n, s in blue_scores.items()}

        return {
            "red_scores": red_scores,
            "blue_scores": blue_scores,
            "hot_red": hot,
            "cold_red": cold,
            "half_life": half_life,
        }

    def _detect_extreme_patterns(self, df: pd.DataFrame) -> Dict:
        """
        极端形态检测
        识别历史上极少出现的形态，用于过滤候选池
        """
        red_count = self.rules["red_count"]
        red_min, red_max = self.rules["red_min"], self.rules["red_max"]
        mid = (red_min + red_max) / 2

        patterns = {
            "all_odd": 0,      # 全奇
            "all_even": 0,     # 全偶
            "all_small": 0,    # 全小
            "all_large": 0,    # 全大
            "all_consecutive": 0,  # 全连号
            "sum_extreme_low": 0,   # 和值极端低
            "sum_extreme_high": 0,  # 和值极端高
            "max_span": 0,     # 最大跨度
            "min_span": 0,     # 最小跨度
        }

        sum_values = []
        span_values = []

        for _, row in df.iterrows():
            reds = row["red_balls"]
            s = sum(reds)
            span = max(reds) - min(reds) if len(reds) >= 2 else 0
            sum_values.append(s)
            span_values.append(span)

            if all(r % 2 == 1 for r in reds):
                patterns["all_odd"] += 1
            if all(r % 2 == 0 for r in reds):
                patterns["all_even"] += 1
            if all(r < mid for r in reds):
                patterns["all_small"] += 1
            if all(r >= mid for r in reds):
                patterns["all_large"] += 1
            if len(reds) >= 2 and max(reds) - min(reds) == len(reds) - 1:
                patterns["all_consecutive"] += 1

        total = len(df)
        sum_mean = np.mean(sum_values) if sum_values else 100
        sum_std = np.std(sum_values) if sum_values else 20
        patterns["sum_extreme_low"] = sum(1 for s in sum_values if s < sum_mean - 2 * sum_std)
        patterns["sum_extreme_high"] = sum(1 for s in sum_values if s > sum_mean + 2 * sum_std)
        patterns["max_span"] = max(span_values) if span_values else 0
        patterns["min_span"] = min(span_values) if span_values else 0

        # 计算各形态出现概率
        probabilities = {k: v / total if total > 0 else 0 for k, v in patterns.items()}

        return {
            "counts": patterns,
            "probabilities": probabilities,
            "sum_mean": sum_mean,
            "sum_std": sum_std,
            "span_mean": np.mean(span_values) if span_values else 0,
            "total": total,
        }

    def _pair_correlation(self, df: pd.DataFrame, top_n: int = 20) -> Dict:
        """
        配对相关性分析
        分析哪些号码经常一起出现
        """
        pair_freq = defaultdict(int)

        for _, row in df.iterrows():
            reds = sorted(row["red_balls"])
            for i in range(len(reds)):
                for j in range(i + 1, len(reds)):
                    pair = (reds[i], reds[j])
                    pair_freq[pair] += 1

        # 排序取前 N
        sorted_pairs = sorted(pair_freq.items(), key=lambda x: x[1], reverse=True)
        top_pairs = [(list(p), c) for p, c in sorted_pairs[:top_n]]

        # 计算期望频率（用于判断正相关/负相关）
        total = len(df)
        red_min, red_max = self.rules["red_min"], self.rules["red_max"]
        single_freq = defaultdict(int)
        for _, row in df.iterrows():
            for r in row["red_balls"]:
                single_freq[r] += 1

        # 正相关配对（实际出现 > 期望）
        positive_corr = []
        for pair, count in sorted_pairs[:50]:
            p_a = single_freq[pair[0]] / total if total > 0 else 0
            p_b = single_freq[pair[1]] / total if total > 0 else 0
            expected = p_a * p_b * total
            actual = count
            if expected > 0 and actual > expected * 1.2:  # 比期望高20%以上
                positive_corr.append((list(pair), round(actual / expected, 2)))

        return {
            "top_pairs": top_pairs,
            "positive_correlation": positive_corr[:10],
            "total_pairs": len(pair_freq),
        }

    def _composite_number_scores(self, df: pd.DataFrame) -> Dict:
        """
        综合号码评分
        多维度加权：频率(0.3) + 近期衰减(0.3) + 遗漏(0.2) + 位置均衡(0.2)
        """
        recency = self._recency_weighted_frequency(df)
        positional = self._positional_frequency(df)

        red_min, red_max = self.rules["red_min"], self.rules["red_max"]
        all_reds = list(range(red_min, red_max + 1))

        # 基础频率
        freq = defaultdict(int)
        for _, row in df.iterrows():
            for r in row["red_balls"]:
                freq[r] += 1
        max_freq = max(freq.values()) if freq else 1

        # 遗漏值
        omission = {}
        latest_idx = len(df) - 1
        for n in all_reds:
            last_seen = latest_idx
            for i in range(latest_idx, -1, -1):
                if n in df.iloc[i]["red_balls"]:
                    last_seen = i
                    break
            omission[n] = latest_idx - last_seen
        max_omission = max(omission.values()) if omission else 1

        # 综合评分
        composite = {}
        for n in all_reds:
            freq_score = freq.get(n, 0) / max_freq if max_freq > 0 else 0
            recency_score = recency["red_scores"].get(n, 0)
            omission_score = omission.get(n, 0) / max_omission if max_omission > 0 else 0
            # 位置均衡分：在多个位置都出现过得分高
            pos_count = sum(1 for pos in positional["red_positional_hot"].values() if n in pos)
            pos_score = pos_count / self.rules["red_count"] if self.rules["red_count"] > 0 else 0

            # 加权综合
            score = (0.30 * freq_score + 0.30 * recency_score +
                     0.20 * omission_score + 0.20 * pos_score)
            composite[n] = round(score, 4)

        sorted_scores = sorted(composite.items(), key=lambda x: x[1], reverse=True)

        return {
            "red_scores": composite,
            "top_red": [n for n, s in sorted_scores[:10]],
            "bottom_red": [n for n, s in sorted_scores[-10:]],
        }

    def _optimal_sum_range(self, df: pd.DataFrame) -> Dict:
        """最优和值范围（历史出现频率最高的区间）"""
        sums = [sum(row["red_balls"]) for _, row in df.iterrows()]
        if not sums:
            return {}

        # 按10为区间统计
        bins = range(min(sums) // 10 * 10, max(sums) // 10 * 10 + 11, 10)
        hist, bin_edges = np.histogram(sums, bins=bins)

        # 找频率最高的3个区间
        top_indices = np.argsort(hist)[-3:][::-1]
        optimal_ranges = []
        for idx in top_indices:
            if hist[idx] > 0:
                optimal_ranges.append({
                    "range": [int(bin_edges[idx]), int(bin_edges[idx + 1])],
                    "count": int(hist[idx]),
                    "probability": round(hist[idx] / len(sums), 4),
                })

        return {
            "optimal_ranges": optimal_ranges,
            "mean": round(np.mean(sums), 1),
            "std": round(np.std(sums), 1),
            "min": min(sums),
            "max": max(sums),
        }

    def _recent_trend_strength(self, df: pd.DataFrame, periods: int = 30) -> Dict:
        """近期趋势强度（最近N期 vs 历史平均的偏离度）"""
        if len(df) < periods:
            periods = len(df)

        recent = df.tail(periods)
        red_min, red_max = self.rules["red_min"], self.rules["red_max"]
        all_reds = list(range(red_min, red_max + 1))

        # 近期频率
        recent_freq = defaultdict(int)
        for _, row in recent.iterrows():
            for r in row["red_balls"]:
                recent_freq[r] += 1

        # 历史平均频率
        hist_freq = defaultdict(int)
        for _, row in df.iterrows():
            for r in row["red_balls"]:
                hist_freq[r] += 1
        hist_avg = {n: hist_freq.get(n, 0) / len(df) * periods for n in all_reds}

        # 趋势强度 = 近期实际 / 历史期望
        trend_strength = {}
        for n in all_reds:
            expected = hist_avg.get(n, 0)
            actual = recent_freq.get(n, 0)
            if expected > 0:
                trend_strength[n] = round(actual / expected, 2)
            else:
                trend_strength[n] = actual * 2  # 历史从未出现，近期出现，强趋势

        # 强热号（近期出现 > 期望1.5倍）
        strong_hot = [n for n, s in sorted(trend_strength.items(), key=lambda x: x[1], reverse=True) if s >= 1.5][:8]
        # 强冷号（近期出现 < 期望0.5倍）
        strong_cold = [n for n, s in sorted(trend_strength.items(), key=lambda x: x[1]) if s <= 0.5][:8]

        return {
            "trend_strength": trend_strength,
            "strong_hot": strong_hot,
            "strong_cold": strong_cold,
            "periods": periods,
        }

    def is_extreme_ticket(self, red_balls: List[int], blue_balls: List[int] = None) -> bool:
        """
        判断一注号码是否为极端形态
        用于候选池过滤
        """
        if not red_balls:
            return True

        red_count = self.rules["red_count"]
        red_min, red_max = self.rules["red_min"], self.rules["red_max"]
        mid = (red_min + red_max) / 2

        s = sum(red_balls)
        span = max(red_balls) - min(red_balls) if len(red_balls) >= 2 else 0

        # 全奇/全偶
        if all(r % 2 == 1 for r in red_balls) or all(r % 2 == 0 for r in red_balls):
            return True

        # 全小/全大
        if all(r < mid for r in red_balls) or all(r >= mid for r in red_balls):
            return True

        # 和值极端（超出均值±2倍标准差）
        # 这里用经验值，具体彩种不同
        expected_sum = red_count * (red_min + red_max) / 2
        if s < expected_sum * 0.5 or s > expected_sum * 1.5:
            return True

        # 连号过多（超过一半）
        sorted_reds = sorted(red_balls)
        consecutive_count = 0
        for i in range(1, len(sorted_reds)):
            if sorted_reds[i] - sorted_reds[i - 1] == 1:
                consecutive_count += 1
        if consecutive_count >= len(red_balls) - 1:  # 全部连号
            return True

        return False

    def calculate_coverage(self, tickets: List[Dict]) -> float:
        """
        计算一组号码的覆盖度
        覆盖度 = 被覆盖的不同号码数 / 总号码数
        """
        red_min, red_max = self.rules["red_min"], self.rules["red_max"]
        all_reds = set(range(red_min, red_max + 1))

        covered = set()
        for t in tickets:
            covered.update(t.get("red_balls", []))

        coverage = len(covered & all_reds) / len(all_reds) if all_reds else 0
        return round(coverage, 4)
