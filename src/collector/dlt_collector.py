"""
大乐透数据采集器
从 500.com 采集历史开奖数据
"""
import re
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from config import COLLECTOR_CONFIG


class DLTCollector:
    """大乐透历史数据采集器"""

    def __init__(self):
        config = COLLECTOR_CONFIG["dlt"]
        self.url = config["history_url"]
        self.headers = config["headers"]
        self.timeout = config["timeout"]
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_history(self, start_issue: str = None, end_issue: str = None) -> List[Dict]:
        """
        采集历史开奖数据
        500.com 的 history.php 一次性返回全部历史数据
        """
        try:
            params = {"limit": "10000"}
            resp = self.session.get(self.url, params=params, timeout=self.timeout)
            resp.encoding = "gb2312"
            if resp.status_code != 200:
                print(f"请求失败: HTTP {resp.status_code}")
                return []

            draws = self._parse_html(resp.text)
            print(f"采集到 {len(draws)} 条大乐透历史数据")

            if start_issue:
                draws = [d for d in draws if d["issue_number"] >= start_issue]
            if end_issue:
                draws = [d for d in draws if d["issue_number"] <= end_issue]

            draws.sort(key=lambda x: x["issue_number"])
            return draws

        except requests.RequestException as e:
            print(f"请求异常: {e}")
            return []

    def _parse_html(self, html: str) -> List[Dict]:
        """解析 500.com 大乐透历史数据 HTML"""
        draws = []
        soup = BeautifulSoup(html, "lxml")

        tbody = soup.find("tbody", id="tdata")
        if not tbody:
            table = soup.find("table", id="tablelist")
            if table:
                tbody = table.find("tbody")

        if not tbody:
            return draws

        rows = tbody.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 8:
                continue

            try:
                issue_number = cols[0].get_text(strip=True)
                if not issue_number or not issue_number.isdigit():
                    continue

                # 前区（第1-5列）
                red_balls = []
                for i in range(1, 6):
                    ball_text = cols[i].get_text(strip=True)
                    if ball_text.isdigit():
                        red_balls.append(int(ball_text))

                # 后区（第6-7列）
                blue_balls = []
                for i in range(6, 8):
                    ball_text = cols[i].get_text(strip=True)
                    if ball_text.isdigit():
                        blue_balls.append(int(ball_text))

                # 开奖日期
                draw_date = ""
                for col in cols[::-1]:
                    text = col.get_text(strip=True)
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                    if date_match:
                        draw_date = date_match.group(1)
                        break

                if not draw_date:
                    year = "20" + issue_number[:2] if len(issue_number) >= 5 else "2024"
                    draw_date = f"{year}-01-01"

                if len(red_balls) == 5 and len(blue_balls) == 2:
                    red_balls.sort()
                    blue_balls.sort()
                    draws.append({
                        "issue_number": issue_number,
                        "draw_date": draw_date,
                        "red_balls": red_balls,
                        "blue_balls": blue_balls,
                    })
            except (ValueError, IndexError):
                continue

        return draws


def collect_dlt_data(db, full_refresh: bool = False) -> Dict:
    """采集大乐透数据并入库"""
    collector = DLTCollector()
    latest_issue = db.get_latest_issue("dlt")

    if full_refresh or not latest_issue:
        print("开始全量采集大乐透历史数据...")
        draws = collector.fetch_history()
    else:
        print(f"数据库最新期号: {latest_issue}，开始增量采集...")
        draws = collector.fetch_history(start_issue=latest_issue)
        draws = [d for d in draws if d["issue_number"] > latest_issue]

    if not draws:
        return {"status": "no_new_data", "collected": 0, "total": db.get_draw_count("dlt")}

    inserted = db.insert_draws("dlt", draws)
    return {
        "status": "success",
        "collected": inserted,
        "new_issues": [d["issue_number"] for d in draws[-5:]],
        "total": db.get_draw_count("dlt"),
    }
