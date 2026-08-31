"""
推送模块
支持飞书 Webhook、企业微信 Webhook、钉钉 Webhook
同时生成 HTML 报告存档
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
import requests


class PushService:
    """推送服务"""

    def __init__(self):
        self.feishu_webhook = os.environ.get("FEISHU_WEBHOOK", "")
        self.wecom_webhook = os.environ.get("WECOM_WEBHOOK", "")
        self.dingtalk_webhook = os.environ.get("DINGTALK_WEBHOOK", "")
        self.timeout = 30

    @property
    def has_channel(self) -> bool:
        return bool(self.feishu_webhook or self.wecom_webhook or self.dingtalk_webhook)

    def push_lottery_result(self, lottery_name: str, issue_number: str,
                             draw_time: str, selected_tickets: List[Dict],
                             analysis_text: str, stats_summary: Dict = None) -> Dict:
        """
        推送彩票分析结果

        Args:
            lottery_name: 彩种名称
            issue_number: 目标期号
            draw_time: 开奖时间
            selected_tickets: 推荐号码列表
            analysis_text: AI 分析文案
            stats_summary: 统计摘要

        Returns:
            推送结果字典
        """
        results = {"feishu": False, "wecom": False, "dingtalk": False, "errors": []}

        # 构建号码文本
        tickets_text = ""
        for i, t in enumerate(selected_tickets, 1):
            reds = " ".join(f"{n:02d}" for n in t["red_balls"])
            blues = " ".join(f"{n:02d}" for n in t["blue_balls"])
            reason = t.get("ai_reason", "")
            tickets_text += f"第{i}组：🔴{reds}  🔵{blues}"
            if reason:
                tickets_text += f"\n  理由：{reason}"
            tickets_text += "\n"

        # 统计摘要文本
        stats_text = ""
        if stats_summary:
            if "hot_red" in stats_summary:
                stats_text += f"红球热号：{' '.join(f'{n:02d}' for n in stats_summary['hot_red'][:6])}\n"
            if "cold_red" in stats_summary:
                stats_text += f"红球冷号：{' '.join(f'{n:02d}' for n in stats_summary['cold_red'][:6])}\n"
            if "hot_blue" in stats_summary:
                stats_text += f"蓝球热号：{' '.join(f'{n:02d}' for n in stats_summary['hot_blue'][:3])}\n"
            if "sum_range" in stats_summary:
                stats_text += f"和值区间：{stats_summary['sum_range']}\n"

        full_text = (
            f"🎰【{lottery_name}第{issue_number}期 AI 分析推荐】\n"
            f"⏰ 开奖时间：{draw_time}\n"
            f"{'='*30}\n"
            f"📊 统计特征\n{stats_text}"
            f"{'='*30}\n"
            f"🎯 推荐{len(selected_tickets)}组号码\n\n{tickets_text}"
            f"{'='*30}\n"
            f"💡 {analysis_text}\n\n"
            f"⚠️ 免责声明：彩票开奖具有随机性，本分析仅供参考，不构成购彩建议。请理性购彩，量力而行。"
        )

        # 飞书推送
        if self.feishu_webhook:
            try:
                ok = self._push_feishu(full_text, lottery_name, issue_number)
                results["feishu"] = ok
                if not ok:
                    results["errors"].append("飞书推送失败")
            except Exception as e:
                results["errors"].append(f"飞书推送异常: {e}")

        # 企业微信推送
        if self.wecom_webhook:
            try:
                ok = self._push_wecom(full_text)
                results["wecom"] = ok
                if not ok:
                    results["errors"].append("企业微信推送失败")
            except Exception as e:
                results["errors"].append(f"企业微信推送异常: {e}")

        # 钉钉推送
        if self.dingtalk_webhook:
            try:
                ok = self._push_dingtalk(full_text)
                results["dingtalk"] = ok
                if not ok:
                    results["errors"].append("钉钉推送失败")
            except Exception as e:
                results["errors"].append(f"钉钉推送异常: {e}")

        return results

    def _push_feishu(self, text: str, lottery_name: str, issue_number: str) -> bool:
        """飞书 Webhook 推送（富文本卡片）"""
        # 尝试交互式卡片，失败则回退到纯文本
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"🎰 {lottery_name}第{issue_number}期 AI 推荐"
                    },
                    "template": "red"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": text.replace("\n", "\n")
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 仅供参考，理性购彩"
                            }
                        ]
                    }
                ]
            }
        }

        try:
            resp = requests.post(self.feishu_webhook, json=card, timeout=self.timeout)
            data = resp.json()
            if data.get("code") == 0 or data.get("StatusCode") == 0:
                return True
            # 卡片失败，回退纯文本
            return self._push_feishu_text(text)
        except Exception:
            return self._push_feishu_text(text)

    def _push_feishu_text(self, text: str) -> bool:
        """飞书纯文本推送"""
        try:
            resp = requests.post(
                self.feishu_webhook,
                json={"msg_type": "text", "content": {"text": text}},
                timeout=self.timeout,
            )
            data = resp.json()
            return data.get("code") == 0 or data.get("StatusCode") == 0
        except Exception:
            return False

    def _push_wecom(self, text: str) -> bool:
        """企业微信 Webhook 推送"""
        try:
            resp = requests.post(
                self.wecom_webhook,
                json={"msgtype": "text", "text": {"content": text}},
                timeout=self.timeout,
            )
            data = resp.json()
            return data.get("errcode") == 0
        except Exception:
            return False

    def _push_dingtalk(self, text: str) -> bool:
        """钉钉 Webhook 推送"""
        try:
            resp = requests.post(
                self.dingtalk_webhook,
                json={"msgtype": "text", "text": {"content": text}},
                timeout=self.timeout,
            )
            data = resp.json()
            return data.get("errcode") == 0
        except Exception:
            return False

    def generate_html_report(self, lottery_name: str, issue_number: str,
                              draw_time: str, selected_tickets: List[Dict],
                              analysis_text: str, stats_summary: Dict = None,
                              output_path: str = None) -> str:
        """
        生成 HTML 分析报告（用于存档和 GitHub Pages）
        """
        from pathlib import Path

        tickets_html = ""
        for i, t in enumerate(selected_tickets, 1):
            reds_html = "".join(
                f'<span class="ball red">{n:02d}</span>' for n in t["red_balls"]
            )
            blues_html = "".join(
                f'<span class="ball blue">{n:02d}</span>' for n in t["blue_balls"]
            )
            reason = t.get("ai_reason", "")
            tickets_html += f"""
            <div class="ticket">
                <div class="ticket-num">第 {i} 组</div>
                <div class="balls">{reds_html}<span class="ball-sep"></span>{blues_html}</div>
                <div class="reason">{reason}</div>
            </div>"""

        stats_html = ""
        if stats_summary:
            stats_items = []
            if "hot_red" in stats_summary:
                stats_items.append(("红球热号", " ".join(f"{n:02d}" for n in stats_summary["hot_red"][:6])))
            if "cold_red" in stats_summary:
                stats_items.append(("红球冷号", " ".join(f"{n:02d}" for n in stats_summary["cold_red"][:6])))
            if "hot_blue" in stats_summary:
                stats_items.append(("蓝球热号", " ".join(f"{n:02d}" for n in stats_summary["hot_blue"][:3])))
            if "cold_blue" in stats_summary:
                stats_items.append(("蓝球冷号", " ".join(f"{n:02d}" for n in stats_summary["cold_blue"][:3])))
            if "sum_range" in stats_summary:
                stats_items.append(("和值区间", stats_summary["sum_range"]))
            if "common_parity" in stats_summary:
                stats_items.append(("常见奇偶比", stats_summary["common_parity"]))

            for label, value in stats_items:
                stats_html += f'<div class="stat-item"><span class="stat-label">{label}</span><span class="stat-value">{value}</span></div>'

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{lottery_name}第{issue_number}期 AI 分析报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #e74c3c, #c0392b); color: #fff; padding: 24px; text-align: center; }}
        .header h1 {{ font-size: 20px; margin-bottom: 8px; }}
        .header .meta {{ font-size: 13px; opacity: 0.9; }}
        .section {{ padding: 20px; border-bottom: 1px solid #eee; }}
        .section h2 {{ font-size: 16px; color: #e74c3c; margin-bottom: 12px; }}
        .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
        .stat-item {{ display: flex; flex-direction: column; padding: 8px; background: #f9f9f9; border-radius: 6px; }}
        .stat-label {{ font-size: 11px; color: #999; margin-bottom: 4px; }}
        .stat-value {{ font-size: 14px; font-weight: 600; color: #333; }}
        .ticket {{ padding: 12px; background: #fafafa; border-radius: 8px; margin-bottom: 10px; }}
        .ticket-num {{ font-size: 13px; color: #e74c3c; font-weight: 600; margin-bottom: 8px; }}
        .balls {{ margin-bottom: 6px; }}
        .ball {{ display: inline-block; width: 32px; height: 32px; line-height: 32px; text-align: center; border-radius: 50%; color: #fff; font-weight: bold; font-size: 13px; margin-right: 4px; }}
        .ball.red {{ background: #e74c3c; }}
        .ball.blue {{ background: #3498db; }}
        .ball-sep {{ display: inline-block; width: 8px; }}
        .reason {{ font-size: 12px; color: #666; margin-top: 4px; }}
        .analysis {{ font-size: 14px; line-height: 1.8; color: #555; }}
        .footer {{ padding: 16px 20px; background: #f9f9f9; font-size: 11px; color: #999; text-align: center; line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎰 {lottery_name}第{issue_number}期</h1>
            <div class="meta">AI 分析推荐 | 开奖时间：{draw_time} | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>
        <div class="section">
            <h2>📊 统计特征</h2>
            <div class="stats">{stats_html}</div>
        </div>
        <div class="section">
            <h2>🎯 推荐 {len(selected_tickets)} 组号码</h2>
            {tickets_html}
        </div>
        <div class="section">
            <h2>💡 分析说明</h2>
            <div class="analysis">{analysis_text.replace(chr(10), '<br>')}</div>
        </div>
        <div class="footer">
            ⚠️ 免责声明：彩票开奖具有随机性，本分析由 AI 基于历史统计数据生成，仅供参考，不构成购彩建议。<br>请理性购彩，量力而行。
        </div>
    </div>
</body>
</html>"""

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(html, encoding="utf-8")
        return html
