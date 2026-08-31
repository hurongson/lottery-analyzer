#!/usr/bin/env python3
"""
彩票分析软件 - Streamlit 可视化界面
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from src.storage.data_manager import DataManager
from src.storage.database import Database
from src.analysis.statistics import LotteryStatistics
from src.backtest.engine import BacktestEngine
from src.backtest.strategies import get_all_strategies, get_strategy_by_name
from src.collector.ssq_collector import collect_ssq_data
from src.collector.dlt_collector import collect_dlt_data
from src.collector.digital_collector import collect_digital_data
from config import DISCLAIMER, LOTTERY_RULES

st.set_page_config(
    page_title="彩票分析软件",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化数据管理器（自动适配本地 SQLite / 云端 CSV）
@st.cache_resource
def get_data_manager(lottery_type):
    return DataManager(lottery_type)

# 侧边栏
with st.sidebar:
    st.title("🎰 彩票分析软件")
    st.markdown("---")

    lottery_options = {
        "双色球 (SSQ)": "ssq",
        "大乐透 (DLT)": "dlt",
        "福彩3D": "fc3d",
        "排列三": "pl3",
        "排列五": "pl5",
    }
    lottery_label = st.selectbox("选择彩种", list(lottery_options.keys()), index=0)
    lt = lottery_options[lottery_label]

    st.markdown("---")
    page = st.radio(
        "功能导航",
        ["📊 数据总览", "📈 统计分析", "🔬 走期回测", "🎯 候选号码", "⚙️ 数据管理"],
        index=0,
    )

    st.markdown("---")
    st.caption(DISCLAIMER)

# 根据选择的彩种创建数据管理器
dm = get_data_manager(lt)
db = dm._db if dm._mode == "sqlite" else None

# 加载数据（缓存）
@st.cache_data(ttl=300)
def load_data(lottery_type):
    return dm.get_all_draws()

df = load_data(lt)
stats = LotteryStatistics(lt)

# ============ 页面1: 数据总览 ============
if page == "📊 数据总览":
    st.header("📊 数据总览")

    if df.empty:
        st.warning("数据库为空，请先在「数据管理」页面采集数据。")
    else:
        # 顶部指标卡片
        col1, col2, col3, col4 = st.columns(4)
        date_range = dm.get_date_range()
        with col1:
            st.metric("历史期数", f"{len(df):,}")
        with col2:
            st.metric("数据起始", date_range[0] if date_range else "-")
        with col3:
            st.metric("最新期号", df["issue_number"].iloc[-1])
        with col4:
            st.metric("最新开奖日", df["draw_date"].iloc[-1])

        st.markdown("---")

        # 最新开奖结果
        st.subheader("🎱 最新开奖结果")
        latest = df.iloc[-1]
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f"**期号：{latest['issue_number']}**")
            st.markdown(f"**日期：{latest['draw_date']}**")
        with col2:
            balls_html = ""
            for n in latest["red_balls"]:
                balls_html += f'<span style="display:inline-block;width:36px;height:36px;line-height:36px;text-align:center;border-radius:50%;background:#e74c3c;color:white;font-weight:bold;margin-right:6px;">{n:02d}</span>'
            balls_html += '<span style="display:inline-block;width:8px;"></span>'
            for n in latest["blue_balls"]:
                balls_html += f'<span style="display:inline-block;width:36px;height:36px;line-height:36px;text-align:center;border-radius:50%;background:#3498db;color:white;font-weight:bold;margin-right:6px;">{n:02d}</span>'
            st.markdown(balls_html, unsafe_allow_html=True)

        st.markdown("---")

        # 近期开奖趋势
        st.subheader("📉 近期开奖趋势（最近30期）")
        recent = df.tail(30).copy()
        recent["sum"] = recent["red_balls"].apply(sum)
        recent["odd_count"] = recent["red_balls"].apply(lambda x: sum(1 for n in x if n % 2 == 1))

        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("红球和值趋势", "红球奇数个数趋势"),
            vertical_spacing=0.12,
        )
        fig.add_trace(
            go.Scatter(x=recent["issue_number"], y=recent["sum"],
                      mode="lines+markers", name="和值",
                      line=dict(color="#e74c3c", width=2)),
            row=1, col=1,
        )
        fig.add_hline(y=101, line_dash="dash", line_color="gray",
                     annotation_text="均值=101", row=1, col=1)
        fig.add_trace(
            go.Bar(x=recent["issue_number"], y=recent["odd_count"],
                  name="奇数个数", marker_color="#3498db"),
            row=2, col=1,
        )
        fig.update_layout(height=500, showlegend=False,
                         xaxis2_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

        # 历史数据表
        with st.expander("📋 查看历史开奖数据（最近50期）"):
            display_df = df.tail(50).copy()
            display_df["红球"] = display_df["red_balls"].apply(lambda x: " ".join(f"{n:02d}" for n in x))
            display_df["蓝球"] = display_df["blue_balls"].apply(lambda x: " ".join(f"{n:02d}" for n in x))
            display_df = display_df[["issue_number", "draw_date", "红球", "蓝球"]]
            display_df.columns = ["期号", "开奖日期", "红球", "蓝球"]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

# ============ 页面2: 统计分析 ============
elif page == "📈 统计分析":
    st.header("📈 统计分析")

    if df.empty:
        st.warning("数据库为空，请先采集数据。")
    else:
        analysis = stats.analyze(df)

        # 分析范围选择
        col1, col2 = st.columns([1, 3])
        with col1:
            analyze_range = st.selectbox(
                "分析范围",
                ["全部历史", "最近100期", "最近50期", "最近30期"],
                index=0,
            )
        with col2:
            st.info(f"当前分析：{len(df)} 期数据，范围 {df['draw_date'].iloc[0]} ~ {df['draw_date'].iloc[-1]}")

        # 根据范围筛选
        if analyze_range == "最近100期":
            analyze_df = df.tail(100)
        elif analyze_range == "最近50期":
            analyze_df = df.tail(50)
        elif analyze_range == "最近30期":
            analyze_df = df.tail(30)
        else:
            analyze_df = df

        analysis = stats.analyze(analyze_df)

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🔥 冷热号", "⏳ 遗漏值", "📊 和值/跨度", "🎯 结构分布", "🔗 关联分析"
        ])

        # Tab1: 冷热号
        with tab1:
            st.subheader("红球出现频率")
            red_freq = analysis["frequency"]["red"]
            freq_df = pd.DataFrame([
                {"号码": n, "出现次数": v["count"], "频率": f"{v['frequency']*100:.2f}%"}
                for n, v in red_freq.items()
            ])
            fig = go.Figure(data=[
                go.Bar(x=freq_df["号码"], y=freq_df["出现次数"],
                      marker_color=freq_df["出现次数"].apply(
                          lambda x: "#e74c3c" if x > freq_df["出现次数"].median() else "#95a5a6"
                      ))
            ])
            fig.add_hline(y=freq_df["出现次数"].mean(), line_dash="dash",
                         annotation_text=f"均值={freq_df['出现次数'].mean():.1f}")
            fig.update_layout(height=400, xaxis_title="红球号码", yaxis_title="出现次数")
            st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🔴 红球热号 TOP10**")
                hot_df = pd.DataFrame({
                    "号码": analysis["frequency"]["red_hot10"],
                    "出现次数": [red_freq[n]["count"] for n in analysis["frequency"]["red_hot10"]],
                })
                st.dataframe(hot_df, use_container_width=True, hide_index=True)
            with col2:
                st.markdown("**🔵 红球冷号 TOP10**")
                cold_df = pd.DataFrame({
                    "号码": analysis["frequency"]["red_cold10"],
                    "出现次数": [red_freq[n]["count"] for n in analysis["frequency"]["red_cold10"]],
                })
                st.dataframe(cold_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("蓝球出现频率")
            blue_freq = analysis["frequency"]["blue"]
            bfreq_df = pd.DataFrame([
                {"号码": n, "出现次数": v["count"], "频率": f"{v['frequency']*100:.2f}%"}
                for n, v in blue_freq.items()
            ])
            fig = go.Figure(data=[
                go.Bar(x=bfreq_df["号码"], y=bfreq_df["出现次数"],
                      marker_color="#3498db")
            ])
            fig.add_hline(y=bfreq_df["出现次数"].mean(), line_dash="dash",
                         annotation_text=f"均值={bfreq_df['出现次数'].mean():.1f}")
            fig.update_layout(height=350, xaxis_title="蓝球号码", yaxis_title="出现次数")
            st.plotly_chart(fig, use_container_width=True)

        # Tab2: 遗漏值
        with tab2:
            st.subheader("当前遗漏值（距离最近一次出现的期数）")
            red_gap = analysis["omission"]["red_current_gap"]
            gap_df = pd.DataFrame([
                {"号码": n, "当前遗漏": v, "历史最大遗漏": analysis["omission"]["red_max_gap"][n]}
                for n, v in red_gap.items()
            ])
            fig = go.Figure()
            fig.add_trace(go.Bar(x=gap_df["号码"], y=gap_df["当前遗漏"],
                                 name="当前遗漏", marker_color="#e67e22"))
            fig.add_trace(go.Scatter(x=gap_df["号码"], y=gap_df["历史最大遗漏"],
                                     mode="lines+markers", name="历史最大遗漏",
                                     line=dict(color="#e74c3c", dash="dash")))
            fig.update_layout(height=400, xaxis_title="红球号码", yaxis_title="遗漏期数")
            st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🔴 红球遗漏 TOP10（最久未出）**")
                top_gap = pd.DataFrame(analysis["omission"]["red_top_gap"], columns=["号码", "遗漏期数"])
                st.dataframe(top_gap, use_container_width=True, hide_index=True)
            with col2:
                st.markdown("**🔵 蓝球遗漏 TOP5**")
                blue_top = pd.DataFrame(analysis["omission"]["blue_top_gap"], columns=["号码", "遗漏期数"])
                st.dataframe(blue_top, use_container_width=True, hide_index=True)

        # Tab3: 和值/跨度
        with tab3:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("红球和值分布")
                s = analysis["sum_value"]
                sums = [sum(balls) for balls in analyze_df["red_balls"]]
                fig = go.Figure(data=[go.Histogram(x=sums, nbinsx=30, marker_color="#e74c3c")])
                fig.add_vline(x=s["mean"], line_dash="dash", line_color="black",
                             annotation_text=f"均值={s['mean']:.1f}")
                fig.update_layout(height=350, xaxis_title="和值", yaxis_title="出现次数")
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"范围: {s['min']} ~ {s['max']} | 均值: {s['mean']:.1f} | 中位数: {s['median']:.1f} | 标准差: {s['std']:.1f}")

            with col2:
                st.subheader("红球跨度分布")
                sp = analysis["span"]
                spans = [max(balls) - min(balls) for balls in analyze_df["red_balls"]]
                fig = go.Figure(data=[go.Histogram(x=spans, nbinsx=20, marker_color="#3498db")])
                fig.add_vline(x=sp["mean"], line_dash="dash", line_color="black",
                             annotation_text=f"均值={sp['mean']:.1f}")
                fig.update_layout(height=350, xaxis_title="跨度", yaxis_title="出现次数")
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"范围: {sp['min']} ~ {sp['max']} | 均值: {sp['mean']:.1f} | 中位数: {sp['median']:.1f}")

        # Tab4: 结构分布
        with tab4:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("奇偶比分布")
                parity = analysis["parity"]
                p_df = pd.DataFrame(list(parity["distribution"].items()), columns=["奇偶比", "出现次数"])
                p_df = p_df.sort_values("出现次数", ascending=False)
                fig = px.pie(p_df, values="出现次数", names="奇偶比", title="红球奇偶比分布")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("大小比分布")
                size = analysis["size"]
                sz_df = pd.DataFrame(list(size["distribution"].items()), columns=["大小比", "出现次数"])
                sz_df = sz_df.sort_values("出现次数", ascending=False)
                fig = px.pie(sz_df, values="出现次数", names="大小比", title="红球大小比分布")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("三区分布")
                zone = analysis["zone"]
                z_df = pd.DataFrame(list(zone["distribution"].items()), columns=["区间比", "出现次数"])
                z_df = z_df.sort_values("出现次数", ascending=False).head(10)
                fig = go.Figure(data=[go.Bar(x=z_df["区间比"], y=z_df["出现次数"], marker_color="#9b59b6")])
                fig.update_layout(height=350, xaxis_title="低:中:高 区间比", yaxis_title="出现次数")
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("连号与重号")
                consec = analysis["consecutive"]
                repeat = analysis["repeat"]
                st.metric("连号出现概率", f"{consec['probability']*100:.1f}%")
                st.metric("重号（与上期相同）平均个数", f"{repeat['mean']:.2f}")
                st.metric("至少1个重号概率", f"{repeat['probability_at_least_one']*100:.1f}%")

        # Tab5: 关联分析
        with tab5:
            st.subheader("红球号码共现 TOP15")
            cooc = analysis["cooccurrence"]
            cooc_df = pd.DataFrame(cooc["top_pairs"])
            cooc_df["号码对"] = cooc_df["pair"].apply(lambda x: f"{x[0]:02d} - {x[1]:02d}")
            fig = go.Figure(data=[
                go.Bar(x=cooc_df["号码对"], y=cooc_df["count"],
                      marker_color="#1abc9c")
            ])
            fig.update_layout(height=400, xaxis_title="号码对", yaxis_title="共同出现次数",
                             xaxis_tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

# ============ 页面3: 走期回测 ============
elif page == "🔬 走期回测":
    st.header("🔬 走期回测")
    st.caption("严格走期回测：第N期预测只能使用 ≤ N-1 期的数据，杜绝未来数据泄露")

    if df.empty:
        st.warning("数据库为空，请先采集数据。")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            warmup = st.number_input("预热期数", min_value=50, max_value=2000, value=500, step=50)
        with col2:
            tickets = st.number_input("每期投注注数", min_value=1, max_value=20, value=5)
        with col3:
            seed = st.number_input("随机种子", min_value=0, max_value=9999, value=42)
        with col4:
            strategies_avail = [s.name for s in get_all_strategies(lt, seed)]
            selected_strategies = st.multiselect("选择策略", strategies_avail, default=strategies_avail)

        run_bt = st.button("🚀 开始回测", type="primary")

        if run_bt:
            if not selected_strategies:
                st.error("请至少选择一个策略")
            else:
                engine = BacktestEngine(lt)
                strats = [get_strategy_by_name(name, lt, seed) for name in selected_strategies]
                strats = [s for s in strats if s]

                progress = st.progress(0)
                status = st.empty()

                results = []
                for i, strategy in enumerate(strats):
                    status.text(f"正在回测：{strategy.name} ({i+1}/{len(strats)})")
                    result = engine.run(strategy, df, warmup=warmup, tickets_per_draw=tickets)
                    results.append(result)
                    progress.progress((i + 1) / len(strats))

                status.empty()
                progress.empty()

                if results:
                    # 汇总对比表
                    st.subheader("📊 回测结果对比")
                    summary = engine.get_summary_table(results)
                    st.dataframe(summary, use_container_width=True, hide_index=True)

                    # 累计收益曲线
                    st.subheader("📈 累计净收益曲线")
                    fig = go.Figure()
                    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
                    for i, r in enumerate(results):
                        fig.add_trace(go.Scatter(
                            x=list(range(len(r["cumulative_profit"]))),
                            y=r["cumulative_profit"],
                            mode="lines", name=r["strategy_name"],
                            line=dict(color=colors[i % len(colors)], width=2)
                        ))
                    fig.add_hline(y=0, line_dash="dash", line_color="gray")
                    fig.update_layout(height=450, xaxis_title="回测期数", yaxis_title="累计净收益（元）")
                    st.plotly_chart(fig, use_container_width=True)

                    # 各策略详情
                    for r in results:
                        with st.expander(f"📋 {r['strategy_name']} 详细结果"):
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("总投入", f"¥{r['total_cost']:,.0f}")
                            with col2:
                                st.metric("总奖金", f"¥{r['total_prize']:,.0f}")
                            with col3:
                                st.metric("净收益", f"¥{r['net_profit']:,.0f}")
                            with col4:
                                st.metric("ROI", f"{r['roi']*100:.2f}%")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("中奖期数", f"{r['win_draws']}/{r['total_draws']}")
                            with col2:
                                st.metric("胜率", f"{r['win_rate']*100:.2f}%")
                            with col3:
                                st.metric("最大回撤", f"¥{r['max_drawdown']:,.0f}")

                            if r.get("prize_distribution_desc"):
                                st.markdown("**奖级分布：**")
                                pd_df = pd.DataFrame(list(r["prize_distribution_desc"].items()), columns=["奖级", "中奖注数"])
                                st.dataframe(pd_df, use_container_width=True, hide_index=True)

        else:
            st.info("👆 配置参数后点击「开始回测」")

# ============ 页面4: 候选号码 ============
elif page == "🎯 候选号码":
    st.header("🎯 候选号码生成")
    st.caption("基于历史数据和选号策略生成候选号码，仅供参考")

    if df.empty:
        st.warning("数据库为空，请先采集数据。")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            strategy_names = [s.name for s in get_all_strategies(lt)]
            sel_strategy = st.selectbox("选择策略", strategy_names, index=0)
        with col2:
            num_tickets = st.number_input("生成注数", min_value=1, max_value=20, value=5)
        with col3:
            seed_val = st.number_input("随机种子", min_value=0, max_value=9999, value=42, key="gen_seed")

        strategy = get_strategy_by_name(sel_strategy, lt, seed_val)

        if st.button("🎲 生成候选号码", type="primary"):
            tickets = strategy.generate_tickets(df, count=num_tickets)

            st.subheader(f"✅ 生成结果（策略：{sel_strategy}）")

            for i, ticket in enumerate(tickets, 1):
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.markdown(f"**第 {i} 注**")
                with col2:
                    balls_html = ""
                    for n in ticket["red_balls"]:
                        balls_html += f'<span style="display:inline-block;width:32px;height:32px;line-height:32px;text-align:center;border-radius:50%;background:#e74c3c;color:white;font-weight:bold;margin-right:5px;font-size:14px;">{n:02d}</span>'
                    balls_html += '<span style="display:inline-block;width:6px;"></span>'
                    for n in ticket["blue_balls"]:
                        balls_html += f'<span style="display:inline-block;width:32px;height:32px;line-height:32px;text-align:center;border-radius:50%;background:#3498db;color:white;font-weight:bold;margin-right:5px;font-size:14px;">{n:02d}</span>'
                    st.markdown(balls_html, unsafe_allow_html=True)

                # 计算该注的统计特征
                reds = ticket["red_balls"]
                s = sum(reds)
                odd = sum(1 for n in reds if n % 2 == 1)
                span = max(reds) - min(reds)
                st.caption(f"和值={s} | 奇偶比={odd}:{6-odd} | 跨度={span}")
                st.markdown("---")

            # 保存到审计台账
            latest_issue = df["issue_number"].iloc[-1]
            # 估算下一期期号
            next_issue = str(int(latest_issue) + 1)
            if dm.save_prediction(next_issue, sel_strategy, tickets):
                st.success(f"✅ 已保存到预测审计台账（目标期号：{next_issue}）")
            else:
                st.warning("保存到审计台账失败")

        # 历史预测记录
        st.markdown("---")
        with st.expander("📋 历史预测记录"):
            preds = dm.get_unsettled_predictions()
            if preds:
                for p in preds:
                    st.markdown(f"**期号 {p['target_issue']}** | 策略：{p['strategy_name']} | 生成时间：{p['created_at']}")
            else:
                st.info("暂无预测记录")

# ============ 页面5: 数据管理 ============
elif page == "⚙️ 数据管理":
    st.header("⚙️ 数据管理")

    is_cloud = dm.mode == "csv"
    mode_label = "☁️ 云端模式（CSV 数据集）" if is_cloud else "💻 本地模式（SQLite）"
    st.info(f"当前运行模式：{mode_label}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("数据采集")
        st.info(f"当前数据集：{len(df)} 条记录")
        if df.empty:
            st.warning("数据集为空")
        else:
            st.write(f"期号范围：{df['issue_number'].iloc[0]} ~ {df['issue_number'].iloc[-1]}")
            st.write(f"日期范围：{df['draw_date'].iloc[0]} ~ {df['draw_date'].iloc[-1]}")

        if is_cloud:
            st.warning("☁️ 云端部署模式下，数据由 GitHub Actions 每日自动更新，无需手动采集。")
            st.caption("如需立即更新数据，请在 GitHub 仓库手动触发 Actions 工作流。")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔄 增量更新", type="primary"):
                    with st.spinner("正在采集最新数据..."):
                        if lt == "ssq":
                            result = collect_ssq_data(db, full_refresh=False)
                            st.success(f"采集完成：新增 {result.get('collected', 0)} 条，总计 {result.get('total', 0)} 条")
                        elif lt == "dlt":
                            result = collect_dlt_data(db, full_refresh=False)
                            st.success(f"采集完成：新增 {result.get('collected', 0)} 条，总计 {result.get('total', 0)} 条")
                        else:
                            count = collect_digital_data(lt, db=db, full_refresh=False)
                            st.success(f"采集完成：更新 {count} 条")
                        dm.export_to_csv()
                        st.cache_data.clear()
                        st.rerun()
            with col_b:
                if st.button("🔄 全量重新采集"):
                    with st.spinner("正在全量采集..."):
                        if lt == "ssq":
                            result = collect_ssq_data(db, full_refresh=True)
                            st.success(f"全量采集完成：共 {result.get('total', 0)} 条")
                        elif lt == "dlt":
                            result = collect_dlt_data(db, full_refresh=True)
                            st.success(f"全量采集完成：共 {result.get('total', 0)} 条")
                        else:
                            count = collect_digital_data(lt, db=db, full_refresh=True)
                            st.success(f"全量采集完成：共 {count} 条")
                        dm.export_to_csv()
                        st.cache_data.clear()
                        st.rerun()

    with col2:
        st.subheader("数据校验")
        if st.button("🔍 执行完整性校验"):
            verify_result = dm.verify_data_integrity()
            if verify_result["passed"]:
                st.success(f"✅ 校验通过：共 {verify_result['total_count']} 条数据，未发现问题")
            else:
                st.error(f"❌ 校验未通过：发现 {len(verify_result['issues'])} 个问题")
                for issue in verify_result["issues"][:20]:
                    st.write(f"- {issue}")

    st.markdown("---")
    st.subheader("📦 数据信息")
    lottery_name = LOTTERY_RULES.get(lt, {}).get("name", lt)
    if is_cloud:
        st.code(f"""
数据模式: 云端 CSV（GitHub 仓库托管）
数据文件: data/{lt}_draws.csv
彩种: {lottery_name}
数据量: {len(df)} 条
更新方式: GitHub Actions 每日自动更新
        """)
    else:
        st.code(f"""
数据模式: 本地 SQLite
数据库路径: {db.db_path}
彩种: {lottery_name}
数据量: {len(df)} 条
表结构:
  - draws: 历史开奖数据
  - predictions: 预测审计台账
  - backtest_results: 回测结果
        """)
