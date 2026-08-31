#!/usr/bin/env python3
"""
彩票分析软件 - 命令行工具
用于数据采集、校验和快速分析
"""
import sys
import argparse
from pathlib import Path

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from src.storage.database import Database
from src.collector.ssq_collector import collect_ssq_data
from src.analysis.statistics import LotteryStatistics
from src.backtest.engine import BacktestEngine
from src.backtest.strategies import get_all_strategies
from config import DISCLAIMER


def cmd_update(args):
    """更新数据"""
    db = Database()
    print("正在采集双色球数据...")
    result = collect_ssq_data(db, full_refresh=args.full)
    print(f"\n采集结果: {result['status']}")
    print(f"新增数据: {result.get('collected', 0)} 条")
    print(f"总数据量: {result.get('total', 0)} 条")
    if result.get("new_issues"):
        print(f"最新期号: {', '.join(result['new_issues'])}")


def cmd_verify(args):
    """校验数据完整性"""
    db = Database()
    result = db.verify_data_integrity("ssq")
    print(f"数据总量: {result['total_count']} 条")
    if result.get("date_range"):
        print(f"日期范围: {result['date_range'][0]} ~ {result['date_range'][1]}")
    print(f"校验结果: {'通过' if result['passed'] else '未通过'}")
    if result["issues"]:
        print("\n发现问题:")
        for issue in result["issues"][:20]:
            print(f"  - {issue}")
        if len(result["issues"]) > 20:
            print(f"  ... 还有 {len(result['issues'])-20} 条问题")


def cmd_stats(args):
    """统计分析"""
    db = Database()
    df = db.get_all_draws("ssq")
    if df.empty:
        print("数据库为空，请先运行 update 命令采集数据")
        return

    stats = LotteryStatistics("ssq")
    analysis = stats.analyze(df)

    print(f"=== 双色球统计分析（共 {len(df)} 期）===")
    print(f"日期范围: {df['draw_date'].iloc[0]} ~ {df['draw_date'].iloc[-1]}")

    print("\n--- 冷热号 ---")
    print(f"红球热号TOP10: {analysis['frequency']['red_hot10']}")
    print(f"红球冷号TOP10: {analysis['frequency']['red_cold10']}")
    print(f"蓝球热号TOP5:  {analysis['frequency']['blue_hot5']}")
    print(f"蓝球冷号TOP5:  {analysis['frequency']['blue_cold5']}")

    print("\n--- 遗漏值 ---")
    print(f"红球当前遗漏TOP10: {analysis['omission']['red_top_gap']}")
    print(f"蓝球当前遗漏TOP5:  {analysis['omission']['blue_top_gap']}")

    print("\n--- 和值 ---")
    s = analysis["sum_value"]
    print(f"范围: {s['min']} ~ {s['max']}, 均值: {s['mean']:.1f}, 中位数: {s['median']:.1f}")

    print("\n--- 奇偶比 ---")
    print(f"最常见: {analysis['parity']['most_common']}")

    print("\n--- 区间分布 ---")
    print(f"最常见: {analysis['zone']['most_common']}")

    print("\n--- 连号 ---")
    print(f"出现概率: {analysis['consecutive']['probability']*100:.1f}%")

    print("\n--- 重号 ---")
    print(f"平均重号数: {analysis['repeat']['mean']:.2f}, 至少1个概率: {analysis['repeat']['probability_at_least_one']*100:.1f}%")


def cmd_backtest(args):
    """回测"""
    db = Database()
    df = db.get_all_draws("ssq")
    if df.empty:
        print("数据库为空，请先运行 update 命令采集数据")
        return

    engine = BacktestEngine("ssq")
    strategies = get_all_strategies("ssq", seed=42)

    if args.strategy:
        strategies = [s for s in strategies if s.name == args.strategy]
        if not strategies:
            print(f"未找到策略: {args.strategy}")
            print(f"可用策略: {[s.name for s in get_all_strategies()]}")
            return

    print(f"开始回测（预热 {args.warmup} 期，每期 {args.tickets} 注）...")
    results = engine.compare_strategies(strategies, df, warmup=args.warmup,
                                          tickets_per_draw=args.tickets, verbose=True)

    print("\n" + "=" * 80)
    print("回测结果对比")
    print("=" * 80)
    table = engine.get_summary_table(results)
    print(table.to_string(index=False))

    print(f"\n{DISCLAIMER}")


def main():
    parser = argparse.ArgumentParser(description="彩票分析软件 - 命令行工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # update
    p_update = subparsers.add_parser("update", help="采集/更新开奖数据")
    p_update.add_argument("--full", action="store_true", help="全量重新采集")
    p_update.set_defaults(func=cmd_update)

    # verify
    p_verify = subparsers.add_parser("verify", help="校验数据完整性")
    p_verify.set_defaults(func=cmd_verify)

    # stats
    p_stats = subparsers.add_parser("stats", help="统计分析")
    p_stats.set_defaults(func=cmd_stats)

    # backtest
    p_bt = subparsers.add_parser("backtest", help="走期回测")
    p_bt.add_argument("--strategy", type=str, default=None, help="指定策略名称")
    p_bt.add_argument("--warmup", type=int, default=100, help="预热期数")
    p_bt.add_argument("--tickets", type=int, default=5, help="每期投注注数")
    p_bt.set_defaults(func=cmd_backtest)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
