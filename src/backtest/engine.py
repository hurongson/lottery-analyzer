"""
走期回测引擎
严格逐期回测：第N期预测只能使用 ≤ N-1 期的数据
"""
from typing import List, Dict, Optional, Tuple
from collections import Counter
import numpy as np
import pandas as pd

from src.models import get_lottery
from src.backtest.strategies import BaseStrategy


class BacktestEngine:
    """走期回测引擎"""

    def __init__(self, lottery_type: str = "ssq"):
        self.lottery_type = lottery_type
        self.lottery = get_lottery(lottery_type)

    def run(self, strategy: BaseStrategy, df: pd.DataFrame,
            warmup: int = 100, tickets_per_draw: int = 5,
            verbose: bool = False) -> Dict:
        """
        执行走期回测

        Args:
            strategy: 选号策略
            df: 全部历史数据
            warmup: 预热期数（前N期仅用于训练，不参与回测）
            tickets_per_draw: 每期投注注数
            verbose: 是否打印进度

        Returns:
            回测结果字典
        """
        if len(df) <= warmup:
            return {"error": f"数据不足：共{len(df)}期，预热需要{warmup}期"}

        total_cost = 0.0
        total_prize = 0.0
        win_draws = 0
        prize_distribution = Counter()
        draw_results = []
        cumulative_profit = []

        test_df = df.iloc[warmup:].reset_index(drop=True)

        for idx in range(len(test_df)):
            # 当前期的真实开奖结果
            current_draw = test_df.iloc[idx]
            target_issue = current_draw["issue_number"]

            # 历史数据：只包含当前期之前的所有数据（严格走期）
            history_df = df.iloc[:warmup + idx].copy()

            # 策略生成候选号码
            try:
                tickets = strategy.generate_tickets(history_df, count=tickets_per_draw)
            except Exception as e:
                if verbose:
                    print(f"期号 {target_issue} 生成号码失败: {e}")
                tickets = []

            # 计算本期结果
            draw_red = current_draw["red_balls"]
            draw_blue = current_draw["blue_balls"]
            draw_cost = len(tickets) * self.lottery.ticket_price
            draw_prize = 0.0
            draw_best_tier = None
            ticket_details = []

            for ticket in tickets:
                tier = self.lottery.check_prize(
                    ticket["red_balls"], ticket["blue_balls"],
                    draw_red, draw_blue
                )
                prize = self.lottery.get_prize_amount(tier) if tier else 0
                draw_prize += prize
                if tier:
                    prize_distribution[tier] += 1
                    if draw_best_tier is None or tier < draw_best_tier:
                        draw_best_tier = tier
                ticket_details.append({
                    "red_balls": ticket["red_balls"],
                    "blue_balls": ticket["blue_balls"],
                    "prize_tier": tier,
                    "prize_amount": prize,
                })

            total_cost += draw_cost
            total_prize += draw_prize
            if draw_prize > 0:
                win_draws += 1

            net = draw_prize - draw_cost
            cumulative_profit.append(total_prize - total_cost)

            draw_results.append({
                "issue_number": target_issue,
                "draw_date": current_draw.get("draw_date", ""),
                "draw_red": draw_red,
                "draw_blue": draw_blue,
                "tickets": ticket_details,
                "cost": draw_cost,
                "prize": draw_prize,
                "net": net,
                "best_tier": draw_best_tier,
                "cumulative_profit": total_prize - total_cost,
            })

            if verbose and (idx + 1) % 100 == 0:
                print(f"已回测 {idx+1}/{len(test_df)} 期，"
                      f"累计投入: {total_cost:.0f}, 累计奖金: {total_prize:.0f}, "
                      f"净收益: {total_prize-total_cost:.0f}")

        total_draws = len(test_df)
        result = {
            "lottery_type": self.lottery_type,
            "strategy_name": strategy.name,
            "strategy_description": strategy.description,
            "start_issue": test_df["issue_number"].iloc[0],
            "end_issue": test_df["issue_number"].iloc[-1],
            "warmup_periods": warmup,
            "total_draws": total_draws,
            "tickets_per_draw": tickets_per_draw,
            "total_tickets": total_draws * tickets_per_draw,
            "total_cost": total_cost,
            "total_prize": total_prize,
            "net_profit": total_prize - total_cost,
            "roi": (total_prize - total_cost) / total_cost if total_cost > 0 else 0,
            "win_draws": win_draws,
            "win_rate": win_draws / total_draws if total_draws > 0 else 0,
            "avg_prize_per_win": total_prize / win_draws if win_draws > 0 else 0,
            "prize_distribution": dict(prize_distribution),
            "prize_distribution_desc": {
                self.lottery.get_prize_desc(k) if hasattr(self.lottery, 'get_prize_desc') else f"第{k}级": v
                for k, v in prize_distribution.items()
            },
            "draw_results": draw_results,
            "cumulative_profit": cumulative_profit,
            "max_drawdown": self._calc_max_drawdown(cumulative_profit),
            "best_single_draw": max(draw_results, key=lambda x: x["prize"]) if draw_results else None,
            "worst_single_draw": min(draw_results, key=lambda x: x["net"]) if draw_results else None,
        }
        return result

    def _calc_max_drawdown(self, cumulative: List[float]) -> float:
        """计算最大回撤"""
        if not cumulative:
            return 0
        peak = cumulative[0]
        max_dd = 0
        for val in cumulative:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def compare_strategies(self, strategies: List[BaseStrategy], df: pd.DataFrame,
                            warmup: int = 100, tickets_per_draw: int = 5,
                            verbose: bool = False) -> List[Dict]:
        """
        多策略对比回测
        返回各策略的回测结果列表
        """
        results = []
        for strategy in strategies:
            if verbose:
                print(f"\n开始回测策略: {strategy.name}")
            result = self.run(strategy, df, warmup, tickets_per_draw, verbose)
            results.append(result)
            if verbose:
                print(f"策略 {strategy.name} 完成: 净收益 {result.get('net_profit', 0):.0f}, "
                      f"胜率 {result.get('win_rate', 0)*100:.1f}%")
        return results

    def get_summary_table(self, results: List[Dict]) -> pd.DataFrame:
        """将多策略回测结果转为对比表格"""
        rows = []
        for r in results:
            rows.append({
                "策略": r["strategy_name"],
                "回测期数": r["total_draws"],
                "总投入": r["total_cost"],
                "总奖金": r["total_prize"],
                "净收益": r["net_profit"],
                "ROI": f"{r['roi']*100:.2f}%",
                "中奖期数": r["win_draws"],
                "胜率": f"{r['win_rate']*100:.2f}%",
                "最大回撤": r["max_drawdown"],
            })
        return pd.DataFrame(rows)
