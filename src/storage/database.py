"""
SQLite 数据存储层
负责历史开奖数据的持久化、查询和校验
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pandas as pd

from config import DB_PATH


class Database:
    """彩票数据库管理"""

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path) if db_path else str(DB_PATH)
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """初始化数据表"""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS draws (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_type TEXT NOT NULL,
                    issue_number TEXT NOT NULL,
                    draw_date TEXT NOT NULL,
                    red_balls TEXT NOT NULL,
                    blue_balls TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(lottery_type, issue_number)
                );

                CREATE INDEX IF NOT EXISTS idx_draws_lottery_date
                    ON draws(lottery_type, draw_date);
                CREATE INDEX IF NOT EXISTS idx_draws_issue
                    ON draws(lottery_type, issue_number);

                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_type TEXT NOT NULL,
                    target_issue TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    strategy_params TEXT,
                    candidate_tickets TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    result_red TEXT,
                    result_blue TEXT,
                    prize_tier INTEGER,
                    settled_at TEXT,
                    UNIQUE(lottery_type, target_issue, strategy_name)
                );

                CREATE INDEX IF NOT EXISTS idx_predictions_target
                    ON predictions(lottery_type, target_issue);

                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_type TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    start_issue TEXT NOT NULL,
                    end_issue TEXT NOT NULL,
                    total_draws INTEGER NOT NULL,
                    total_tickets INTEGER NOT NULL,
                    total_cost REAL NOT NULL,
                    total_prize REAL NOT NULL,
                    net_profit REAL NOT NULL,
                    win_draws INTEGER NOT NULL,
                    win_rate REAL NOT NULL,
                    prize_distribution TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def insert_draws(self, lottery_type: str, draws: List[Dict]) -> int:
        """
        批量插入开奖数据（忽略已存在的期号）
        返回实际插入的条数
        """
        inserted = 0
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for d in draws:
                try:
                    cursor.execute(
                        """INSERT OR IGNORE INTO draws
                           (lottery_type, issue_number, draw_date, red_balls, blue_balls)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            lottery_type,
                            d["issue_number"],
                            d["draw_date"],
                            ",".join(map(str, d["red_balls"])),
                            ",".join(map(str, d["blue_balls"])),
                        ),
                    )
                    if cursor.rowcount > 0:
                        inserted += 1
                except Exception as e:
                    print(f"插入期号 {d.get('issue_number')} 失败: {e}")
        return inserted

    def get_all_draws(self, lottery_type: str) -> pd.DataFrame:
        """获取指定彩种的全部历史开奖数据，按期号升序"""
        with self._get_conn() as conn:
            df = pd.read_sql_query(
                """SELECT issue_number, draw_date, red_balls, blue_balls
                   FROM draws
                   WHERE lottery_type = ?
                   ORDER BY issue_number ASC""",
                conn,
                params=(lottery_type,),
            )
        if not df.empty:
            df["red_balls"] = df["red_balls"].apply(
                lambda x: [int(n) for n in x.split(",")] if x else []
            )
            df["blue_balls"] = df["blue_balls"].apply(
                lambda x: [int(n) for n in x.split(",")] if x else []
            )
        return df

    def get_draws_before(self, lottery_type: str, issue_number: str) -> pd.DataFrame:
        """获取指定期号之前（不含）的所有开奖数据"""
        with self._get_conn() as conn:
            df = pd.read_sql_query(
                """SELECT issue_number, draw_date, red_balls, blue_balls
                   FROM draws
                   WHERE lottery_type = ? AND issue_number < ?
                   ORDER BY issue_number ASC""",
                conn,
                params=(lottery_type, issue_number),
            )
        if not df.empty:
            df["red_balls"] = df["red_balls"].apply(
                lambda x: [int(n) for n in x.split(",")] if x else []
            )
            df["blue_balls"] = df["blue_balls"].apply(
                lambda x: [int(n) for n in x.split(",")] if x else []
            )
        return df

    def get_latest_issue(self, lottery_type: str) -> Optional[str]:
        """获取最新期号"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT issue_number FROM draws WHERE lottery_type = ? ORDER BY issue_number DESC LIMIT 1",
                (lottery_type,),
            ).fetchone()
        return row["issue_number"] if row else None

    def get_draw_count(self, lottery_type: str) -> int:
        """获取开奖数据条数"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM draws WHERE lottery_type = ?",
                (lottery_type,),
            ).fetchone()
        return row["cnt"] if row else 0

    def get_date_range(self, lottery_type: str) -> Optional[Tuple[str, str]]:
        """获取数据日期范围"""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT MIN(draw_date) as min_date, MAX(draw_date) as max_date
                   FROM draws WHERE lottery_type = ?""",
                (lottery_type,),
            ).fetchone()
        if row and row["min_date"]:
            return (row["min_date"], row["max_date"])
        return None

    def save_prediction(self, lottery_type: str, target_issue: str,
                        strategy_name: str, candidate_tickets: List[Dict],
                        strategy_params: str = None) -> bool:
        """保存预测记录（开奖前锁定）"""
        import json
        with self._get_conn() as conn:
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO predictions
                       (lottery_type, target_issue, strategy_name, strategy_params, candidate_tickets)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        lottery_type, target_issue, strategy_name,
                        strategy_params, json.dumps(candidate_tickets, ensure_ascii=False),
                    ),
                )
                return True
            except Exception as e:
                print(f"保存预测失败: {e}")
                return False

    def get_unsettled_predictions(self, lottery_type: str) -> List[Dict]:
        """获取未结算的预测记录"""
        import json
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM predictions
                   WHERE lottery_type = ? AND settled_at IS NULL
                   ORDER BY target_issue ASC""",
                (lottery_type,),
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["candidate_tickets"] = json.loads(d["candidate_tickets"]) if d["candidate_tickets"] else []
            results.append(d)
        return d

    def save_backtest_result(self, result: Dict) -> bool:
        """保存回测结果"""
        import json
        with self._get_conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO backtest_results
                       (lottery_type, strategy_name, start_issue, end_issue,
                        total_draws, total_tickets, total_cost, total_prize,
                        net_profit, win_draws, win_rate, prize_distribution)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result["lottery_type"], result["strategy_name"],
                        result["start_issue"], result["end_issue"],
                        result["total_draws"], result["total_tickets"],
                        result["total_cost"], result["total_prize"],
                        result["net_profit"], result["win_draws"],
                        result["win_rate"],
                        json.dumps(result.get("prize_distribution", {}), ensure_ascii=False),
                    ),
                )
                return True
            except Exception as e:
                print(f"保存回测结果失败: {e}")
                return False

    def verify_data_integrity(self, lottery_type: str) -> Dict:
        """
        数据完整性校验
        返回校验结果字典
        """
        df = self.get_all_draws(lottery_type)
        result = {
            "total_count": len(df),
            "issues": [],
            "passed": True,
        }

        if df.empty:
            result["issues"].append("数据库为空")
            result["passed"] = False
            return result

        # 检查期号连续性（双色球期号格式：YYYYNNN，可能有跳号但不应重复）
        issues = df["issue_number"].tolist()
        if len(issues) != len(set(issues)):
            result["issues"].append("存在重复期号")
            result["passed"] = False

        # 检查红球合法性
        from config import LOTTERY_RULES
        rules = LOTTERY_RULES.get(lottery_type, {})
        red_min, red_max = rules.get("red_min", 1), rules.get("red_max", 33)
        red_count = rules.get("red_count", 6)
        blue_min, blue_max = rules.get("blue_min", 1), rules.get("blue_max", 16)
        blue_count = rules.get("blue_count", 1)

        for _, row in df.iterrows():
            reds = row["red_balls"]
            blues = row["blue_balls"]
            issue = row["issue_number"]

            if len(reds) != red_count:
                result["issues"].append(f"期号 {issue}: 红球数量异常 ({len(reds)})")
                result["passed"] = False
            if len(set(reds)) != len(reds):
                result["issues"].append(f"期号 {issue}: 红球有重复")
                result["passed"] = False
            if any(r < red_min or r > red_max for r in reds):
                result["issues"].append(f"期号 {issue}: 红球超出范围")
                result["passed"] = False
            if sorted(reds) != reds:
                result["issues"].append(f"期号 {issue}: 红球未排序")
                result["passed"] = False

            if len(blues) != blue_count:
                result["issues"].append(f"期号 {issue}: 蓝球数量异常 ({len(blues)})")
                result["passed"] = False
            if any(b < blue_min or b > blue_max for b in blues):
                result["issues"].append(f"期号 {issue}: 蓝球超出范围")
                result["passed"] = False

        result["date_range"] = (df["draw_date"].iloc[0], df["draw_date"].iloc[-1])
        return result
