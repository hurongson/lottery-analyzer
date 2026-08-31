"""
双色球数据采集器
从 500.com 采集历史开奖数据
"""
import re
import time
from typing import List, Dict, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import COLLECTOR_CONFIG


class SSQCollector:
    """双色球历史数据采集器"""

    def __init__(self):
        config = COLLECTOR_CONFIG["ssq"]
        self.url = config["history_url"]
        self.headers = config["headers"]
        self.timeout = config["timeout"]
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_history(self, start_issue: str = None, end_issue: str = None) -> List[Dict]:
        """
        采集历史开奖数据
        500.com 的 history.php 一次性返回全部历史数据
        返回按时间升序排列的数据列表
        """
        try:
            params = {"limit": "10000"}
            resp = self.session.get(self.url, params=params, timeout=self.timeout)
            resp.encoding = "gb2312"
            if resp.status_code != 200:
                print(f"请求失败: HTTP {resp.status_code}")
                return []

            draws = self._parse_html(resp.text)
            print(f"采集到 {len(draws)} 条历史数据")

            # 按期号筛选
            if start_issue:
                draws = [d for d in draws if d["issue_number"] >= start_issue]
            if end_issue:
                draws = [d for d in draws if d["issue_number"] <= end_issue]

            # 按期号升序排列
            draws.sort(key=lambda x: x["issue_number"])
            return draws

        except requests.RequestException as e:
            print(f"请求异常: {e}")
            return []

    def _parse_html(self, html: str) -> List[Dict]:
        """解析 500.com 历史数据 HTML"""
        draws = []
        soup = BeautifulSoup(html, "lxml")

        # 找到数据表格
        table = soup.find("tbody", id="tdata")
        if not table:
            table = soup.find("table", class_="t_tr1")
            if table:
                table = table.find("tbody")

        if not table:
            return draws

        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 8:
                continue

            try:
                # 期号
                issue_number = cols[0].get_text(strip=True)
                if not issue_number or not issue_number.isdigit():
                    continue

                # 红球（第1-6列）
                red_balls = []
                for i in range(1, 7):
                    ball_text = cols[i].get_text(strip=True)
                    if ball_text.isdigit():
                        red_balls.append(int(ball_text))

                # 蓝球（第7列）
                blue_balls = []
                blue_text = cols[7].get_text(strip=True)
                if blue_text.isdigit():
                    blue_balls.append(int(blue_text))

                # 开奖日期（通常在最后一列或倒数第二列）
                draw_date = ""
                for col in cols[::-1]:
                    text = col.get_text(strip=True)
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                    if date_match:
                        draw_date = date_match.group(1)
                        break

                if not draw_date:
                    # 尝试从期号推断年份
                    year = "20" + issue_number[:2] if len(issue_number) >= 5 else "2024"
                    draw_date = f"{year}-01-01"

                if len(red_balls) == 6 and len(blue_balls) == 1:
                    red_balls.sort()
                    draws.append({
                        "issue_number": issue_number,
                        "draw_date": draw_date,
                        "red_balls": red_balls,
                        "blue_balls": blue_balls,
                    })
            except (ValueError, IndexError) as e:
                continue

        return draws

    def fetch_latest(self) -> Optional[Dict]:
        """获取最新一期开奖数据"""
        draws = self.fetch_history()
        return draws[-1] if draws else None


def collect_ssq_data(db, full_refresh: bool = False) -> Dict:
    """
    采集双色球数据并入库
    返回采集统计信息
    """
    collector = SSQCollector()
    latest_issue = db.get_latest_issue("ssq")

    if full_refresh or not latest_issue:
        print("开始全量采集双色球历史数据...")
        draws = collector.fetch_history()
    else:
        print(f"数据库最新期号: {latest_issue}，开始增量采集...")
        # 从最新期号之后开始采集
        draws = collector.fetch_history(start_issue=latest_issue)
        # 过滤掉已存在的期号
        draws = [d for d in draws if d["issue_number"] > latest_issue]

    if not draws:
        return {"status": "no_new_data", "collected": 0, "total": db.get_draw_count("ssq")}

    inserted = db.insert_draws("ssq", draws)
    return {
        "status": "success",
        "collected": inserted,
        "new_issues": [d["issue_number"] for d in draws[-5:]],  # 最新5期
        "total": db.get_draw_count("ssq"),
    }
