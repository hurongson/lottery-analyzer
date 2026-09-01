"""
AI 选号生成器
结合统计分析生成候选池，再由 AI 筛选优化出最终推荐号码
"""
import random
from typing import List, Dict, Tuple
import numpy as np
import pandas as pd

from src.models import get_lottery
from src.analysis.statistics import LotteryStatistics
from src.analysis.advanced_analysis import AdvancedAnalyzer
from src.ai.ai_service import AIService


class NumberGenerator:
    """AI 选号生成器"""

    def __init__(self, lottery_type: str = "ssq", ai_service: AIService = None, seed: int = None):
        self.lottery_type = lottery_type
        self.lottery = get_lottery(lottery_type)
        self.stats = LotteryStatistics(lottery_type)
        self.advanced = AdvancedAnalyzer(lottery_type)
        self.ai = ai_service or AIService()
        self.rng = random.Random(seed) if seed is not None else random.Random()
        from config import LOTTERY_RULES
        self.is_digital = LOTTERY_RULES.get(lottery_type, {}).get("is_digital", False)

    def generate(self, history_df: pd.DataFrame, count: int = 10,
                 candidate_pool_size: int = 50) -> Tuple[List[Dict], Dict, str]:
        """
        生成推荐号码

        Args:
            history_df: 历史开奖数据
            count: 最终推荐组数
            candidate_pool_size: 候选池大小

        Returns:
            (推荐号码列表, 统计摘要, AI分析文案)
        """
        # 1. 统计分析
        analysis = self.stats.analyze(history_df)
        advanced = self.advanced.analyze(history_df)
        stats_summary = self._build_stats_summary(analysis, advanced)

        # 2. 生成候选池（数字型彩票用专门逻辑）
        if self.is_digital:
            candidates = self._generate_digital_candidates(history_df, analysis, advanced, candidate_pool_size)
        else:
            candidates = self._generate_candidates(history_df, analysis, advanced, candidate_pool_size)

        # 3. 覆盖度优化：确保10组号码覆盖尽可能多的号码
        candidates = self._optimize_coverage(candidates, count)

        # 4. AI 筛选
        selected = self.ai.select_lottery_numbers(
            self.lottery.name, candidates, stats_summary, count
        )

        # 4. 生成分析文案
        analysis_text = self.ai.generate_analysis_report(
            self.lottery.name, stats_summary, selected
        )

        return selected, stats_summary, analysis_text

    def _generate_digital_candidates(self, history_df: pd.DataFrame, analysis: Dict,
                                       advanced: Dict = None, pool_size: int = 50) -> List[Dict]:
        """数字型彩票候选池生成（允许重复，有位置概念）"""
        candidates = []
        seen = set()

        freq = analysis.get("frequency", {})
        omission = analysis.get("omission", {})
        sum_stats = analysis.get("sum_value", {})

        red_hot = freq.get("red_hot10", [])
        red_cold = freq.get("red_cold10", [])
        red_gap = omission.get("red_current_gap", {})

        # 增强分析
        recency_scores = {}
        composite_scores = {}
        if advanced:
            recency_scores = advanced.get("recency_weighted", {}).get("red_scores", {})
            composite_scores = advanced.get("composite_scores", {}).get("red_scores", {})

        red_min, red_max = self.lottery.red_range
        blue_min, blue_max = self.lottery.blue_range
        red_count = self.lottery.red_count
        blue_count = self.lottery.blue_count

        sum_mean = sum_stats.get("mean", 10)
        sum_std = sum_stats.get("std", 5)

        def weighted_pick(numbers, weights=None):
            """按权重随机选一个数字"""
            if not numbers:
                return self.rng.randint(red_min, red_max)
            if weights is None:
                return self.rng.choice(numbers)
            total = sum(weights)
            if total == 0:
                return self.rng.choice(numbers)
            r = self.rng.uniform(0, total)
            cumsum = 0
            for n, w in zip(numbers, weights):
                cumsum += w
                if r <= cumsum:
                    return n
            return numbers[-1]

        def add_candidate(reds, blues, strategy_name, score, features=""):
            # 数字型彩票：过滤全同号（如000、111）等极端形态
            if len(set(reds)) == 1:  # 所有数字都相同
                return False
            key = (tuple(reds), tuple(blues))  # 数字型不排序，顺序有意义
            if key not in seen and self.lottery.is_valid_ticket(reds, blues):
                seen.add(key)
                candidates.append({
                    "red_balls": reds,  # 不排序
                    "blue_balls": blues,
                    "score": score,
                    "strategy": strategy_name,
                    "features": features,
                })
                return True
            return False

        all_nums = list(range(red_min, red_max + 1))

        # 策略1：热号为主（30%）
        n_hot = int(pool_size * 0.3)
        hot_weights = {n: 10 - i for i, n in enumerate(red_hot[:10])}
        for _ in range(n_hot * 5):
            if len([c for c in candidates if c["strategy"] == "hot"]) >= n_hot:
                break
            reds = [weighted_pick(all_nums, [hot_weights.get(n, 1) for n in all_nums]) for _ in range(red_count)]
            blues = [self.rng.choice(red_hot[:5]) if red_hot and blue_count > 0 else self.rng.randint(blue_min, blue_max) for _ in range(blue_count)]
            s = sum(reds)
            score = 1.0 if abs(s - sum_mean) < sum_std else 0.5
            add_candidate(reds, blues, "hot", score, f"热号为主 和值={s}")

        # 策略2：冷号回补（25%）
        n_cold = int(pool_size * 0.25)
        cold_weights = {n: gap for n, gap in red_gap.items()}
        for _ in range(n_cold * 5):
            if len([c for c in candidates if c["strategy"] == "cold"]) >= n_cold:
                break
            reds = [weighted_pick(all_nums, [cold_weights.get(n, 1) for n in all_nums]) for _ in range(red_count)]
            blues = [self.rng.choice(red_cold[:5]) if red_cold and blue_count > 0 else self.rng.randint(blue_min, blue_max) for _ in range(blue_count)]
            s = sum(reds)
            score = 0.8 if abs(s - sum_mean) < sum_std * 1.5 else 0.4
            add_candidate(reds, blues, "cold", score, f"冷号回补 和值={s}")

        # 策略3：冷热均衡（25%）
        n_balance = int(pool_size * 0.25)
        balance_weights = {n: (hot_weights.get(n, 1) + cold_weights.get(n, 1)) / 2 for n in all_nums}
        for _ in range(n_balance * 5):
            if len([c for c in candidates if c["strategy"] == "balance"]) >= n_balance:
                break
            reds = [weighted_pick(all_nums, [balance_weights.get(n, 1) for n in all_nums]) for _ in range(red_count)]
            blues = [self.rng.randint(blue_min, blue_max) for _ in range(blue_count)]
            s = sum(reds)
            score = 0.9 if abs(s - sum_mean) < sum_std * 1.2 else 0.5
            add_candidate(reds, blues, "balance", score, f"冷热均衡 和值={s}")

        # 策略4：结构优化（20%）- 关注奇偶比、大小比
        n_struct = pool_size - len(candidates)
        for _ in range(n_struct * 5):
            if len(candidates) >= pool_size:
                break
            # 生成结构合理的号码
            reds = []
            for pos in range(red_count):
                if pos % 2 == 0:
                    reds.append(self.rng.choice(red_hot[:8]) if red_hot else self.rng.randint(red_min, red_max))
                else:
                    reds.append(self.rng.choice(red_cold[:8]) if red_cold else self.rng.randint(red_min, red_max))
            blues = [self.rng.randint(blue_min, blue_max) for _ in range(blue_count)]
            s = sum(reds)
            odd_count = sum(1 for r in reds if r % 2 == 1)
            score = 0.85 if abs(s - sum_mean) < sum_std and 1 <= odd_count <= red_count - 1 else 0.4
            add_candidate(reds, blues, "structure", score, f"结构优化 奇={odd_count} 和={s}")

        # 不足则随机补充
        while len(candidates) < pool_size:
            reds = [self.rng.randint(red_min, red_max) for _ in range(red_count)]
            blues = [self.rng.randint(blue_min, blue_max) for _ in range(blue_count)]
            add_candidate(reds, blues, "random", 0.3, "随机补充")

        return candidates

    def _build_stats_summary(self, analysis: Dict, advanced: Dict = None) -> Dict:
        """从分析结果构建统计摘要（包含增强分析）"""
        summary = {}

        freq = analysis.get("frequency", {})
        summary["hot_red"] = freq.get("red_hot10", [])
        summary["cold_red"] = freq.get("red_cold10", [])
        summary["hot_blue"] = freq.get("blue_hot5", [])
        summary["cold_blue"] = freq.get("blue_cold5", [])

        omission = analysis.get("omission", {})
        summary["omission_red"] = omission.get("red_top_gap", [])
        summary["omission_blue"] = omission.get("blue_top_gap", [])

        sum_val = analysis.get("sum_value", {})
        if sum_val:
            summary["sum_range"] = f"{sum_val.get('mean', 0):.0f}±{sum_val.get('std', 0):.0f}"

        parity = analysis.get("parity", {})
        if parity.get("most_common"):
            summary["common_parity"] = parity["most_common"][0][0]

        zone = analysis.get("zone", {})
        if zone.get("most_common"):
            summary["common_zone"] = zone["most_common"][0][0]

        # 增强分析数据
        if advanced:
            recency = advanced.get("recency_weighted", {})
            if recency:
                summary["recent_hot"] = recency.get("hot_red", [])[:6]
                summary["recent_cold"] = recency.get("cold_red", [])[:6]

            composite = advanced.get("composite_scores", {})
            if composite:
                summary["composite_top"] = composite.get("top_red", [])[:6]

            optimal_sum = advanced.get("optimal_sum_range", {})
            if optimal_sum:
                ranges = optimal_sum.get("optimal_ranges", [])
                if ranges:
                    summary["optimal_sum_ranges"] = [f"{r['range'][0]}-{r['range'][1]}" for r in ranges[:3]]

            trend = advanced.get("recent_trend_strength", {})
            if trend:
                summary["strong_hot"] = trend.get("strong_hot", [])[:5]
                summary["strong_cold"] = trend.get("strong_cold", [])[:5]

            pair_corr = advanced.get("pair_correlation", {})
            if pair_corr:
                pos_pairs = pair_corr.get("positive_correlation", [])
                if pos_pairs:
                    summary["hot_pairs"] = [f"{p[0][0]}-{p[0][1]}" for p in pos_pairs[:5]]

        return summary

    def _optimize_coverage(self, candidates: List[Dict], target_count: int) -> List[Dict]:
        """
        覆盖度优化：从候选池中选出覆盖度最高的 target_count 组号码
        使用贪心算法，每次选择覆盖最多新号码的候选
        """
        if len(candidates) <= target_count:
            return candidates

        selected = []
        covered = set()
        remaining = candidates.copy()

        for _ in range(target_count):
            best_candidate = None
            best_new_coverage = -1

            for c in remaining:
                reds = set(c.get("red_balls", []))
                blues = set(c.get("blue_balls", []))
                new_coverage = len((reds | blues) - covered)
                # 综合评分：新覆盖度 + 原始分数
                total_score = new_coverage * 2 + c.get("score", 0)
                if total_score > best_new_coverage:
                    best_new_coverage = total_score
                    best_candidate = c

            if best_candidate:
                selected.append(best_candidate)
                covered.update(best_candidate.get("red_balls", []))
                covered.update(best_candidate.get("blue_balls", []))
                remaining.remove(best_candidate)
            else:
                break

        # 如果选不够，用剩余候选补充
        if len(selected) < target_count:
            for c in remaining:
                if c not in selected:
                    selected.append(c)
                    if len(selected) >= target_count:
                        break

        return selected[:target_count]

    def _generate_candidates(self, history_df: pd.DataFrame, analysis: Dict,
                              advanced: Dict = None, pool_size: int = 50) -> List[Dict]:
        """
        生成候选号码池
        使用多种策略生成，确保多样性，过滤极端形态
        """
        candidates = []
        seen = set()

        freq = analysis.get("frequency", {})
        omission = analysis.get("omission", {})
        sum_stats = analysis.get("sum_value", {})

        red_hot = freq.get("red_hot10", [])
        red_cold = freq.get("red_cold10", [])
        blue_hot = freq.get("blue_hot5", [])
        blue_cold = freq.get("blue_cold5", [])
        red_gap = omission.get("red_current_gap", {})
        blue_gap = omission.get("blue_current_gap", {})

        # 增强分析数据
        recency_scores = {}
        composite_scores = {}
        positional_hot = {}
        if advanced:
            recency_scores = advanced.get("recency_weighted", {}).get("red_scores", {})
            composite_scores = advanced.get("composite_scores", {}).get("red_scores", {})
            positional_hot = advanced.get("positional_frequency", {}).get("red_positional_hot", {})

        red_min, red_max = self.lottery.red_range
        blue_min, blue_max = self.lottery.blue_range
        red_count = self.lottery.red_count
        blue_count = self.lottery.blue_count

        sum_mean = sum_stats.get("mean", 100)
        sum_std = sum_stats.get("std", 20)

        def add_candidate(reds, blues, strategy_name, score, features=""):
            # 极端形态过滤
            if self.advanced.is_extreme_ticket(reds, blues):
                return False
            key = (tuple(sorted(reds)), tuple(sorted(blues)))
            if key not in seen and self.lottery.is_valid_ticket(reds, blues):
                seen.add(key)
                candidates.append({
                    "red_balls": sorted(reds),
                    "blue_balls": sorted(blues),
                    "score": score,
                    "strategy": strategy_name,
                    "features": features,
                })
                return True
            return False

        # 策略1：热号为主（30%候选）
        n_hot = int(pool_size * 0.3)
        for _ in range(n_hot * 3):
            if len([c for c in candidates if c["strategy"] == "hot"]) >= n_hot:
                break
            hot_pick = min(red_count - 1, max(2, int(red_count * 0.6)))
            reds = self.rng.sample(red_hot[:15], min(hot_pick, len(red_hot[:15])))
            remaining = [n for n in range(red_min, red_max + 1) if n not in reds]
            reds.extend(self.rng.sample(remaining, red_count - len(reds)))
            blues = self.rng.sample(blue_hot, min(blue_count, len(blue_hot))) if blue_hot else [self.rng.randint(blue_min, blue_max)]
            s = sum(reds)
            score = 1.0 if abs(s - sum_mean) < sum_std else 0.5
            add_candidate(reds, blues, "hot", score, f"热号为主 和值={s}")

        # 策略2：冷号回补（25%候选）
        n_cold = int(pool_size * 0.25)
        cold_reds_sorted = sorted(red_gap.items(), key=lambda x: x[1], reverse=True)
        cold_red_nums = [n for n, _ in cold_reds_sorted[:15]]
        for _ in range(n_cold * 3):
            if len([c for c in candidates if c["strategy"] == "cold"]) >= n_cold:
                break
            cold_pick = min(red_count - 1, max(2, int(red_count * 0.5)))
            reds = self.rng.sample(cold_red_nums, min(cold_pick, len(cold_red_nums)))
            remaining = [n for n in range(red_min, red_max + 1) if n not in reds]
            reds.extend(self.rng.sample(remaining, red_count - len(reds)))
            cold_blues_sorted = sorted(blue_gap.items(), key=lambda x: x[1], reverse=True)
            cold_blue_nums = [n for n, _ in cold_blues_sorted[:8]]
            blues = self.rng.sample(cold_blue_nums, min(blue_count, len(cold_blue_nums))) if cold_blue_nums else [self.rng.randint(blue_min, blue_max)]
            s = sum(reds)
            score = 0.8 if abs(s - sum_mean) < sum_std * 1.5 else 0.4
            add_candidate(reds, blues, "cold", score, f"冷号回补 和值={s}")

        # 策略3：冷热均衡（25%候选）
        n_balance = int(pool_size * 0.25)
        for _ in range(n_balance * 3):
            if len([c for c in candidates if c["strategy"] == "balance"]) >= n_balance:
                break
            hot_pick = red_count // 2
            cold_pick = red_count - hot_pick
            reds = self.rng.sample(red_hot[:12], min(hot_pick, len(red_hot[:12])))
            reds.extend(self.rng.sample(red_cold[:12], min(cold_pick, len(red_cold[:12]))))
            remaining = [n for n in range(red_min, red_max + 1) if n not in reds]
            while len(reds) < red_count:
                reds.append(self.rng.choice(remaining))
                remaining.remove(reds[-1])
            blues = [self.rng.choice(blue_hot + blue_cold)] if (blue_hot or blue_cold) else [self.rng.randint(blue_min, blue_max)]
            s = sum(reds)
            odd = sum(1 for n in reds if n % 2 == 1)
            score = 1.2 if (abs(s - sum_mean) < sum_std and 2 <= odd <= 4) else 0.6
            add_candidate(reds, blues, "balance", score, f"冷热均衡 和值={s} 奇偶={odd}:{red_count-odd}")

        # 策略4：结构优化（20%候选）- 和值/奇偶/区间均衡
        n_struct = pool_size - len(candidates)
        for _ in range(n_struct * 5):
            if len(candidates) >= pool_size:
                break
            # 随机生成但过滤结构
            reds = sorted(self.rng.sample(range(red_min, red_max + 1), red_count))
            blues = [self.rng.randint(blue_min, blue_max)]
            s = sum(reds)
            odd = sum(1 for n in reds if n % 2 == 1)
            # 结构过滤：和值在合理范围，奇偶比均衡
            if abs(s - sum_mean) < sum_std * 1.2 and 2 <= odd <= 4:
                # 区间分布检查
                zone_low = sum(1 for n in reds if n <= 11)
                zone_mid = sum(1 for n in reds if 12 <= n <= 22)
                zone_high = sum(1 for n in reds if n >= 23)
                if min(zone_low, zone_mid, zone_high) >= 1:
                    score = 1.5
                    add_candidate(reds, blues, "structure", score,
                                f"结构优化 和值={s} 奇偶={odd}:{red_count-odd} 区间={zone_low}:{zone_mid}:{zone_high}")

        # 按评分排序
        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        return candidates[:pool_size]
