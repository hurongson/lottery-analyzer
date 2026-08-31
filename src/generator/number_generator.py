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
from src.ai.ai_service import AIService


class NumberGenerator:
    """AI 选号生成器"""

    def __init__(self, lottery_type: str = "ssq", ai_service: AIService = None, seed: int = None):
        self.lottery_type = lottery_type
        self.lottery = get_lottery(lottery_type)
        self.stats = LotteryStatistics(lottery_type)
        self.ai = ai_service or AIService()
        self.rng = random.Random(seed) if seed is not None else random.Random()

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
        stats_summary = self._build_stats_summary(analysis)

        # 2. 生成候选池
        candidates = self._generate_candidates(history_df, analysis, candidate_pool_size)

        # 3. AI 筛选
        selected = self.ai.select_lottery_numbers(
            self.lottery.name, candidates, stats_summary, count
        )

        # 4. 生成分析文案
        analysis_text = self.ai.generate_analysis_report(
            self.lottery.name, stats_summary, selected
        )

        return selected, stats_summary, analysis_text

    def _build_stats_summary(self, analysis: Dict) -> Dict:
        """从分析结果构建统计摘要"""
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

        return summary

    def _generate_candidates(self, history_df: pd.DataFrame, analysis: Dict,
                              pool_size: int = 50) -> List[Dict]:
        """
        生成候选号码池
        使用多种策略生成，确保多样性
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

        red_min, red_max = self.lottery.red_range
        blue_min, blue_max = self.lottery.blue_range
        red_count = self.lottery.red_count
        blue_count = self.lottery.blue_count

        sum_mean = sum_stats.get("mean", 100)
        sum_std = sum_stats.get("std", 20)

        def add_candidate(reds, blues, strategy_name, score, features=""):
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
