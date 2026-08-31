"""
数据管理器
支持 SQLite（本地开发）和 CSV（云端部署）双模式
自动检测运行环境，选择合适的数据源
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np

from config import BASE_DIR, DATA_DIR


class DataManager:
    """统一数据访问层，自动适配本地/云端环境"""

    def __init__(self, lottery_type: str = "ssq"):
        self.lottery_type = lottery_type
        self.csv_path = DATA_DIR / f"{lottery_type}_draws.csv"
        self.db_path = DATA_DIR / "lottery.db"
        self._mode = self._detect_mode()
        self._db = None

    def _detect_mode(self) -> str:
        """检测运行模式：云端用 CSV，本地优先 SQLite"""
        # Streamlit Cloud 环境标志
        is_streamlit_cloud = os.environ.get("STREAMLIT_SHARING", "").lower() == "true" or \
                             os.path.exists("/app/.streamlit")
        # 强制 CSV 模式
        force_csv = os.environ.get("USE_CSV_DATA", "").lower() == "true"

        if is_streamlit_cloud or force_csv:
            return "csv"

        # 本地：如果 SQLite 存在且有数据，用 SQLite
        if self.db_path.exists():
            try:
                from src.storage.database import Database
                db = Database(self.db_path)
                if db.get_draw_count(self.lottery_type) > 0:
                    self._db = db
                    return "sqlite"
            except Exception:
                pass

        # 回退到 CSV
        if self.csv_path.exists():
            return "csv"

        return "csv"

    @property
    def mode(self) -> str:
        return self._mode

    def get_all_draws(self) -> pd.DataFrame:
        """获取全部历史开奖数据"""
        if self._mode == "sqlite" and self._db:
            return self._db.get_all_draws(self.lottery_type)
        return self._read_csv()

    def get_draw_count(self) -> int:
        """获取数据条数"""
        if self._mode == "sqlite" and self._db:
            return self._db.get_draw_count(self.lottery_type)
        df = self._read_csv()
        return len(df)

    def get_latest_issue(self) -> Optional[str]:
        """获取最新期号"""
        df = self.get_all_draws()
        if df.empty:
            return None
        return df["issue_number"].iloc[-1]

    def get_date_range(self) -> Optional[Tuple[str, str]]:
        """获取日期范围"""
        df = self.get_all_draws()
        if df.empty:
            return None
        return (df["draw_date"].iloc[0], df["draw_date"].iloc[-1])

    def save_prediction(self, target_issue: str, strategy_name: str,
                         candidate_tickets: List[Dict], strategy_params: str = None) -> bool:
        """保存预测记录（CSV 模式下写入 JSON 文件）"""
        if self._mode == "sqlite" and self._db:
            return self._db.save_prediction(
                self.lottery_type, target_issue, strategy_name,
                candidate_tickets, strategy_params
            )

        # CSV 模式：写入 JSON 文件
        pred_file = DATA_DIR / f"{self.lottery_type}_predictions.json"
        predictions = []
        if pred_file.exists():
            try:
                predictions = json.loads(pred_file.read_text(encoding="utf-8"))
            except Exception:
                predictions = []

        # 去重（同期同策略覆盖）
        predictions = [p for p in predictions
                       if not (p.get("target_issue") == target_issue
                               and p.get("strategy_name") == strategy_name)]
        predictions.append({
            "lottery_type": self.lottery_type,
            "target_issue": target_issue,
            "strategy_name": strategy_name,
            "strategy_params": strategy_params,
            "candidate_tickets": candidate_tickets,
            "created_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

        try:
            pred_file.write_text(
                json.dumps(predictions, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            return True
        except Exception as e:
            print(f"保存预测失败: {e}")
            return False

    def get_unsettled_predictions(self) -> List[Dict]:
        """获取未结算预测记录"""
        if self._mode == "sqlite" and self._db:
            return self._db.get_unsettled_predictions(self.lottery_type)

        pred_file = DATA_DIR / f"{self.lottery_type}_predictions.json"
        if not pred_file.exists():
            return []
        try:
            return json.loads(pred_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def verify_data_integrity(self) -> Dict:
        """数据完整性校验"""
        from config import LOTTERY_RULES
        df = self.get_all_draws()
        result = {
            "total_count": len(df),
            "issues": [],
            "passed": True,
            "mode": self._mode,
        }

        if df.empty:
            result["issues"].append("数据集为空")
            result["passed"] = False
            return result

        rules = LOTTERY_RULES.get(self.lottery_type, {})
        red_min, red_max = rules.get("red_min", 1), rules.get("red_max", 33)
        red_count = rules.get("red_count", 6)
        blue_min, blue_max = rules.get("blue_min", 1), rules.get("blue_max", 16)
        blue_count = rules.get("blue_count", 1)

        issues_set = set()
        for _, row in df.iterrows():
            reds = row["red_balls"]
            blues = row["blue_balls"]
            issue = row["issue_number"]

            if len(reds) != red_count:
                issues_set.add(f"红球数量异常")
            if len(set(reds)) != len(reds):
                issues_set.add(f"红球有重复")
            if any(r < red_min or r > red_max for r in reds):
                issues_set.add(f"红球超出范围")
            if len(blues) != blue_count:
                issues_set.add(f"蓝球数量异常")
            if any(b < blue_min or b > blue_max for b in blues):
                issues_set.add(f"蓝球超出范围")

        if len(df["issue_number"].unique()) != len(df):
            issues_set.add("存在重复期号")

        result["issues"] = list(issues_set)
        result["passed"] = len(issues_set) == 0
        result["date_range"] = (df["draw_date"].iloc[0], df["draw_date"].iloc[-1])
        return result

    def _read_csv(self) -> pd.DataFrame:
        """从 CSV 读取数据"""
        if not self.csv_path.exists():
            return pd.DataFrame(columns=["issue_number", "draw_date", "red_balls", "blue_balls"])

        df = pd.read_csv(self.csv_path, dtype={"issue_number": str})
        if df.empty:
            return df

        df["red_balls"] = df["red_balls"].apply(
            lambda x: [int(n) for n in str(x).split(",")] if pd.notna(x) and str(x).strip() else []
        )
        df["blue_balls"] = df["blue_balls"].apply(
            lambda x: [int(n) for n in str(x).split(",")] if pd.notna(x) and str(x).strip() else []
        )
        df = df.sort_values("issue_number").reset_index(drop=True)
        return df

    def export_to_csv(self, output_path: str = None) -> str:
        """将 SQLite 数据导出为 CSV"""
        if not self._db:
            from src.storage.database import Database
            self._db = Database(self.db_path)

        df = self._db.get_all_draws(self.lottery_type)
        if df.empty:
            return ""

        export_df = df.copy()
        export_df["red_balls"] = export_df["red_balls"].apply(lambda x: ",".join(map(str, x)))
        export_df["blue_balls"] = export_df["blue_balls"].apply(lambda x: ",".join(map(str, x)))

        out_path = output_path or str(self.csv_path)
        export_df.to_csv(out_path, index=False, encoding="utf-8")
        return out_path

    def import_from_csv(self, csv_path: str = None) -> int:
        """从 CSV 导入数据到 SQLite"""
        from src.storage.database import Database
        if not self._db:
            self._db = Database(self.db_path)

        path = csv_path or str(self.csv_path)
        if not Path(path).exists():
            return 0

        df = pd.read_csv(path, dtype={"issue_number": str})
        draws = []
        for _, row in df.iterrows():
            draws.append({
                "issue_number": str(row["issue_number"]),
                "draw_date": str(row["draw_date"]),
                "red_balls": [int(n) for n in str(row["red_balls"]).split(",") if n.strip() and n.strip() != "nan"],
                "blue_balls": [int(n) for n in str(row["blue_balls"]).split(",") if n.strip() and n.strip() != "nan"],
            })

        return self._db.insert_draws(self.lottery_type, draws)
