"""
彩票分析软件 - 全局配置
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.resolve()

# 数据目录
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 报告目录
REPORT_DIR = DATA_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# 数据库路径
DB_PATH = DATA_DIR / "lottery.db"

# 数据采集配置
COLLECTOR_CONFIG = {
    "ssq": {
        "name": "双色球",
        "history_url": "https://datachart.500.com/ssq/history/newinc/history.php",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://datachart.500.com/ssq/history/history.shtml",
        },
        "timeout": 30,
        "draw_time": "21:15",  # 开奖时间（北京时间）
        "draw_days": [1, 3, 6],  # 开奖日：周二、周四、周日 (0=周一)
    },
    "dlt": {
        "name": "大乐透",
        "history_url": "https://datachart.500.com/dlt/history/newinc/history.php",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://datachart.500.com/dlt/history/history.shtml",
        },
        "timeout": 30,
        "draw_time": "20:30",  # 开奖时间（北京时间）
        "draw_days": [0, 2, 5],  # 开奖日：周一、周三、周六 (0=周一)
    },
    "fc3d": {
        "name": "福彩3D",
        "draw_time": "21:15",
        "draw_days": [0, 1, 2, 3, 4, 5, 6],  # 每天开奖
    },
    "pl3": {
        "name": "排列三",
        "draw_time": "20:30",
        "draw_days": [0, 1, 2, 3, 4, 5, 6],  # 每天开奖
    },
    "pl5": {
        "name": "排列五",
        "draw_time": "20:30",
        "draw_days": [0, 1, 2, 3, 4, 5, 6],  # 每天开奖
    },
    "qxc": {
        "name": "七星彩",
        "draw_time": "20:30",
        "draw_days": [1, 4, 6],  # 周二、周五、周日
    },
}

# 彩种规则配置
LOTTERY_RULES = {
    "ssq": {
        "name": "双色球",
        "red_count": 6,
        "red_min": 1,
        "red_max": 33,
        "blue_count": 1,
        "blue_min": 1,
        "blue_max": 16,
        "draw_days": [1, 3, 6],
        "prize_tiers": {
            1: {"desc": "一等奖", "red_match": 6, "blue_match": 1},
            2: {"desc": "二等奖", "red_match": 6, "blue_match": 0},
            3: {"desc": "三等奖", "red_match": 5, "blue_match": 1},
            4: {"desc": "四等奖", "red_match": 5, "blue_match": 0},
            5: {"desc": "五等奖", "red_match": 4, "blue_match": 1},
            6: {"desc": "六等奖", "red_match": 4, "blue_match": 0},
            7: {"desc": "七等奖", "red_match": 3, "blue_match": 1},
            8: {"desc": "八等奖", "red_match": 2, "blue_match": 1},
            9: {"desc": "九等奖", "red_match": 1, "blue_match": 1},
            10: {"desc": "九等奖", "red_match": 0, "blue_match": 1},
        },
        "prize_amounts": {
            1: 5000000,
            2: 200000,
            3: 3000,
            4: 200,
            5: 10,
            6: 10,
            7: 10,
            8: 5,
            9: 5,
            10: 5,
        },
        "ticket_price": 2,
    },
    "dlt": {
        "name": "大乐透",
        "red_count": 5,        # 前区个数
        "red_min": 1,
        "red_max": 35,
        "blue_count": 2,       # 后区个数
        "blue_min": 1,
        "blue_max": 12,
        "draw_days": [0, 2, 5],
        "prize_tiers": {
            1: {"desc": "一等奖", "red_match": 5, "blue_match": 2},
            2: {"desc": "二等奖", "red_match": 5, "blue_match": 1},
            3: {"desc": "三等奖", "red_match": 5, "blue_match": 0},
            4: {"desc": "四等奖", "red_match": 4, "blue_match": 2},
            5: {"desc": "五等奖", "red_match": 4, "blue_match": 1},
            6: {"desc": "六等奖", "red_match": 3, "blue_match": 2},
            7: {"desc": "七等奖", "red_match": 4, "blue_match": 0},
            8: {"desc": "八等奖", "red_match": 3, "blue_match": 1},
            9: {"desc": "九等奖", "red_match": 2, "blue_match": 2},
        },
        "prize_amounts": {
            1: 10000000,
            2: 5000000,
            3: 10000,
            4: 3000,
            5: 300,
            6: 200,
            7: 100,
            8: 15,
            9: 5,
        },
        "ticket_price": 2,
    },
    "fc3d": {
        "name": "福彩3D",
        "red_count": 3,
        "red_min": 0,
        "red_max": 9,
        "blue_count": 0,
        "blue_min": 0,
        "blue_max": 0,
        "draw_days": [0, 1, 2, 3, 4, 5, 6],
        "is_digital": True,
        "prize_tiers": {
            1: {"desc": "直选", "match_type": "exact"},
            2: {"desc": "组三", "match_type": "group3"},
            3: {"desc": "组六", "match_type": "group6"},
        },
        "prize_amounts": {1: 1040, 2: 346, 3: 173},
        "ticket_price": 2,
    },
    "pl3": {
        "name": "排列三",
        "red_count": 3,
        "red_min": 0,
        "red_max": 9,
        "blue_count": 0,
        "blue_min": 0,
        "blue_max": 0,
        "draw_days": [0, 1, 2, 3, 4, 5, 6],
        "is_digital": True,
        "prize_tiers": {
            1: {"desc": "直选", "match_type": "exact"},
            2: {"desc": "组三", "match_type": "group3"},
            3: {"desc": "组六", "match_type": "group6"},
        },
        "prize_amounts": {1: 1040, 2: 346, 3: 173},
        "ticket_price": 2,
    },
    "pl5": {
        "name": "排列五",
        "red_count": 5,
        "red_min": 0,
        "red_max": 9,
        "blue_count": 0,
        "blue_min": 0,
        "blue_max": 0,
        "draw_days": [0, 1, 2, 3, 4, 5, 6],
        "is_digital": True,
        "prize_tiers": {
            1: {"desc": "一等奖", "match_type": "exact"},
        },
        "prize_amounts": {1: 100000},
        "ticket_price": 2,
    },
    "qxc": {
        "name": "七星彩",
        "red_count": 6,
        "red_min": 0,
        "red_max": 9,
        "blue_count": 1,
        "blue_min": 0,
        "blue_max": 9,
        "draw_days": [1, 4, 6],
        "is_digital": True,
        "prize_tiers": {
            1: {"desc": "一等奖", "pos_match": 7},
            2: {"desc": "二等奖", "pos_match": 6},
            3: {"desc": "三等奖", "pos_match": 5},
            4: {"desc": "四等奖", "pos_match": 4},
            5: {"desc": "五等奖", "pos_match": 3},
            6: {"desc": "六等奖", "pos_match": 2},
        },
        "prize_amounts": {1: 5000000, 2: 50000, 3: 3000, 4: 500, 5: 30, 6: 5},
        "ticket_price": 2,
    },
}

# AI 配置（通过环境变量设置，不硬编码密钥）
AI_CONFIG = {
    "api_key": os.environ.get("AI_API_KEY", ""),
    "base_url": os.environ.get("AI_BASE_URL", "https://api.deepseek.com/v1"),
    "model": os.environ.get("AI_MODEL", "deepseek-chat"),
}

# 推送配置（通过环境变量设置）
PUSH_CONFIG = {
    "feishu_webhook": os.environ.get("FEISHU_WEBHOOK", ""),
    "wecom_webhook": os.environ.get("WECOM_WEBHOOK", ""),
    "dingtalk_webhook": os.environ.get("DINGTALK_WEBHOOK", ""),
}

# 选号配置
GENERATOR_CONFIG = {
    "recommend_count": 10,       # 推荐组数
    "candidate_pool_size": 50,   # 候选池大小
    "random_seed": 42,
}

# 回测默认配置
BACKTEST_CONFIG = {
    "warmup_periods": 100,
    "tickets_per_draw": 5,
    "random_seed": 42,
}

# 免责声明
DISCLAIMER = (
    "本软件仅用于数据分析与技术研究，彩票开奖具有强随机性，"
    "任何分析结果均不构成购彩或投资建议。请理性购彩，量力而行。"
)
