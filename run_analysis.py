#!/usr/bin/env python3
"""
定时分析主脚本
开奖前1小时自动运行：数据更新 → 统计分析 → AI选号10组 → 推送 → 生成HTML报告

用法：
    python run_analysis.py --lottery ssq    # 双色球
    python run_analysis.py --lottery dlt    # 大乐透
    python run_analysis.py --lottery all    # 全部（自动判断今天哪种开奖）
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from config import COLLECTOR_CONFIG, GENERATOR_CONFIG, REPORT_DIR
from src.storage.database import Database
from src.storage.data_manager import DataManager
from src.collector.ssq_collector import collect_ssq_data
from src.collector.dlt_collector import collect_dlt_data
from src.ai.ai_service import AIService
from src.push.push_service import PushService
from src.generator.number_generator import NumberGenerator
from src.models import get_lottery


def get_today_draw_lotteries():
    """判断今天有哪些彩票开奖"""
    today = datetime.now().weekday()  # 0=周一
    results = []
    for lt, cfg in COLLECTOR_CONFIG.items():
        if today in cfg.get("draw_days", []):
            results.append(lt)
    return results


def run_analysis(lottery_type: str, skip_update: bool = False, no_push: bool = False):
    """
    执行单彩种分析流程

    Args:
        lottery_type: 彩种类型 ssq/dlt
        skip_update: 跳过数据更新
        no_push: 跳过推送（仅生成报告）
    """
    lottery = get_lottery(lottery_type)
    cfg = COLLECTOR_CONFIG[lottery_type]
    print(f"\n{'='*60}")
    print(f"开始分析：{lottery.name}（{lottery_type}）")
    print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # 1. 数据更新
    if not skip_update:
        print("\n[1/5] 更新数据...")
        db = Database()
        if lottery_type == "ssq":
            result = collect_ssq_data(db, full_refresh=False)
        else:
            result = collect_dlt_data(db, full_refresh=False)
        print(f"  数据更新完成：{result.get('status')}，新增 {result.get('collected', 0)} 条，总计 {result.get('total', 0)} 条")

        # 同步到 CSV
        dm = DataManager(lottery_type)
        csv_path = dm.export_to_csv()
        print(f"  CSV 已同步：{csv_path}")
    else:
        print("\n[1/5] 跳过数据更新")

    # 2. 加载数据
    print("\n[2/5] 加载历史数据...")
    dm = DataManager(lottery_type)
    df = dm.get_all_draws()
    if df.empty:
        print("  错误：无历史数据，请先采集数据")
        return None
    print(f"  历史数据：{len(df)} 期，期号范围 {df['issue_number'].iloc[0]} ~ {df['issue_number'].iloc[-1]}")

    # 3. AI 选号
    print(f"\n[3/5] AI 分析选号（生成 {GENERATOR_CONFIG['recommend_count']} 组）...")
    ai = AIService()
    print(f"  AI 服务：{'已配置' if ai.is_configured else '未配置（将使用统计评分排序）'}")
    print(f"  AI 模型：{ai.model}")

    generator = NumberGenerator(lottery_type, ai_service=ai, seed=GENERATOR_CONFIG["random_seed"])
    selected, stats_summary, analysis_text = generator.generate(
        df,
        count=GENERATOR_CONFIG["recommend_count"],
        candidate_pool_size=GENERATOR_CONFIG["candidate_pool_size"],
    )
    print(f"  选号完成：{len(selected)} 组")

    # 4. 计算目标期号和开奖时间
    latest_issue = df["issue_number"].iloc[-1]
    try:
        target_issue = str(int(latest_issue) + 1)
    except ValueError:
        target_issue = latest_issue

    draw_time = cfg.get("draw_time", "20:00")
    today_str = datetime.now().strftime("%Y-%m-%d")
    full_draw_time = f"{today_str} {draw_time}"

    print(f"\n[4/5] 目标期号：{target_issue}，开奖时间：{full_draw_time}")

    # 5. 推送
    push_result = None
    if not no_push:
        print("\n[5/5] 推送结果...")
        push = PushService()
        if push.has_channel:
            push_result = push.push_lottery_result(
                lottery_name=lottery.name,
                issue_number=target_issue,
                draw_time=full_draw_time,
                selected_tickets=selected,
                analysis_text=analysis_text,
                stats_summary=stats_summary,
            )
            channels = []
            if push_result.get("feishu"):
                channels.append("飞书")
            if push_result.get("wecom"):
                channels.append("企业微信")
            if push_result.get("dingtalk"):
                channels.append("钉钉")
            if channels:
                print(f"  推送成功：{', '.join(channels)}")
            else:
                print(f"  推送失败：{push_result.get('errors', [])}")
        else:
            print("  未配置推送渠道，跳过推送")
            print("  配置方式：设置环境变量 FEISHU_WEBHOOK / WECOM_WEBHOOK / DINGTALK_WEBHOOK")
    else:
        print("\n[5/5] 跳过推送")

    # 6. 生成 HTML 报告
    print("\n生成 HTML 报告...")
    report_dir = REPORT_DIR / lottery_type
    report_dir.mkdir(parents=True, exist_ok=True)
    report_filename = f"{target_issue}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    report_path = report_dir / report_filename

    push_svc = PushService()
    push_svc.generate_html_report(
        lottery_name=lottery.name,
        issue_number=target_issue,
        draw_time=full_draw_time,
        selected_tickets=selected,
        analysis_text=analysis_text,
        stats_summary=stats_summary,
        output_path=str(report_path),
    )
    print(f"  报告已生成：{report_path}")

    # 7. 保存预测记录
    dm.save_prediction(target_issue, "AI推荐", selected)

    # 输出摘要
    print(f"\n{'='*60}")
    print(f"分析完成！{lottery.name}第{target_issue}期")
    print(f"推荐 {len(selected)} 组号码，开奖时间：{full_draw_time}")
    print(f"{'='*60}\n")

    # 打印推荐号码
    for i, t in enumerate(selected, 1):
        reds = " ".join(f"{n:02d}" for n in t["red_balls"])
        blues = " ".join(f"{n:02d}" for n in t["blue_balls"])
        reason = t.get("ai_reason", "")
        print(f"  第{i:2d}组：🔴 {reds}  🔵 {blues}  {reason}")

    return {
        "lottery_type": lottery_type,
        "lottery_name": lottery.name,
        "target_issue": target_issue,
        "draw_time": full_draw_time,
        "selected": selected,
        "analysis_text": analysis_text,
        "stats_summary": stats_summary,
        "report_path": str(report_path),
        "push_result": push_result,
    }


def main():
    parser = argparse.ArgumentParser(description="彩票 AI 分析与推送")
    parser.add_argument("--lottery", type=str, default="all",
                       choices=["ssq", "dlt", "all"],
                       help="彩种类型（默认 all：自动判断今日开奖彩种）")
    parser.add_argument("--skip-update", action="store_true",
                       help="跳过数据更新")
    parser.add_argument("--no-push", action="store_true",
                       help="跳过推送（仅生成报告）")
    args = parser.parse_args()

    if args.lottery == "all":
        today_lotteries = get_today_draw_lotteries()
        if not today_lotteries:
            print("今天没有彩票开奖，退出。")
            return
        print(f"今日开奖彩种：{', '.join(today_lotteries)}")
        for lt in today_lotteries:
            run_analysis(lt, skip_update=args.skip_update, no_push=args.no_push)
    else:
        run_analysis(args.lottery, skip_update=args.skip_update, no_push=args.no_push)


if __name__ == "__main__":
    main()
