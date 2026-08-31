# 🎰 彩票分析软件

基于 Python 的彩票数据分析与走期回测平台，支持双色球历史数据采集、多维统计分析、多策略走期回测和候选号码生成。

> **免责声明**：本软件仅用于数据分析与技术研究，彩票开奖具有强随机性，任何分析结果均不构成购彩或投资建议。请理性购彩，量力而行。

## ✨ 功能特性

### 📊 数据总览
- 历史开奖数据一览（期号、日期、红蓝球）
- 最新开奖结果展示
- 近期和值、奇偶比趋势图
- 历史数据表格浏览

### 📈 统计分析（10+ 项指标）
- **冷热号分析**：红球/蓝球出现频率排名
- **遗漏值分析**：当前遗漏、历史最大遗漏
- **和值/跨度**：分布统计与趋势
- **结构分布**：奇偶比、大小比、三区分布
- **连号/重号**：出现概率统计
- **关联分析**：号码共现频率

### 🔬 走期回测引擎
- **严格走期**：第N期预测只能使用 ≤ N-1 期数据，杜绝未来数据泄露
- **多策略对比**：随机选号、热号优先、冷号回补、综合策略
- **完整指标**：总投入、总奖金、净收益、ROI、胜率、最大回撤
- **累计收益曲线**：可视化策略表现
- **奖级分布**：各奖级中奖次数统计

### 🎯 候选号码生成
- 基于策略生成候选号码
- 每注号码的统计特征（和值、奇偶比、跨度）
- 预测审计台账（开奖前锁定，开奖后结算）

### ⚙️ 数据管理
- 一键增量/全量数据采集
- 数据完整性校验
- GitHub Actions 每日自动更新

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 数据采集 | requests + BeautifulSoup4 |
| 数据存储 | SQLite（本地）/ CSV（云端，GitHub 托管） |
| 数据处理 | Pandas + NumPy |
| 统计分析 | SciPy + 自定义统计模块 |
| 可视化 | Streamlit + Plotly |
| 定时任务 | GitHub Actions |
| 云端部署 | Streamlit Cloud（免费） |

## 📦 安装

```bash
# 克隆项目
git clone <repository-url>
cd lottery-analyzer

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 🚀 使用

### 1. 采集数据

```bash
# 增量更新（推荐）
python cli.py update

# 全量重新采集
python cli.py update --full
```

### 2. 校验数据

```bash
python cli.py verify
```

### 3. 命令行统计分析

```bash
python cli.py stats
```

### 4. 命令行回测

```bash
# 全部策略回测
python cli.py backtest --warmup 500 --tickets 5

# 指定策略
python cli.py backtest --strategy "热号优先(近50期)"
```

### 5. 启动 Web 界面

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501` 即可使用。

## ☁️ 云端部署（Streamlit Cloud）

本项目已适配云端部署，数据使用 CSV 格式托管在 GitHub 仓库，GitHub Actions 每日自动更新。

### 部署步骤

1. **将项目推送到 GitHub 仓库**（建议私有仓库）

2. **登录 [Streamlit Cloud](https://share.streamlit.io/)**，使用同一个 GitHub 账号

3. **点击 "New app"**，选择：
   - Repository：你的彩票分析仓库
   - Branch：`main`（或 `master`）
   - Main file path：`app.py`

4. **点击 "Deploy"**，等待约 1-2 分钟即可上线

5. **访问地址**：`https://<你的应用名>.streamlit.app`

### 云端数据更新机制

- 历史数据存储在 `data/ssq_draws.csv`，随仓库一起部署
- GitHub Actions 在双色球开奖日（周二、周四、周日）北京时间 22:30 自动采集最新数据并更新 CSV
- Streamlit Cloud 检测到仓库更新后自动重新部署
- 也可在 GitHub Actions 页面手动触发 "Run workflow" 立即更新

### 多项目管理（方案 A）

在同一个 Streamlit Cloud 账号下，可以部署多个独立应用：
- 彩票分析 → `lottery-analyzer.streamlit.app`
- 股票分析 → `stock-analyzer.streamlit.app`
- 其他项目 → 各自独立

每个项目使用独立的 GitHub 仓库、独立的数据集、独立的定时任务，互不影响。

## 📁 项目结构

```
lottery-analyzer/
├── app.py                      # Streamlit Web 应用入口
├── cli.py                      # 命令行工具
├── config.py                   # 全局配置
├── requirements.txt            # Python 依赖
├── data/
│   └── lottery.db              # SQLite 数据库
├── src/
│   ├── models/                 # 彩种模型
│   │   ├── base.py             # 彩种抽象基类
│   │   └── ssq.py              # 双色球实现
│   ├── collector/              # 数据采集
│   │   └── ssq_collector.py    # 双色球数据采集器
│   ├── storage/                # 数据存储
│   │   └── database.py         # SQLite 数据库管理
│   ├── analysis/               # 统计分析
│   │   └── statistics.py       # 统计分析引擎
│   ├── backtest/               # 回测引擎
│   │   ├── engine.py           # 走期回测执行器
│   │   └── strategies.py       # 选号策略库
│   └── utils/                  # 工具函数
├── .github/
│   └── workflows/
│       └── daily_update.yml    # GitHub Actions 每日更新
└── tests/                      # 测试
```

## 🧪 回测策略说明

| 策略 | 说明 |
|------|------|
| 随机选号 | 完全随机生成，作为公平基线 |
| 热号优先 | 基于最近N期频率，优先选择高频号码 |
| 冷号回补 | 基于遗漏值，优先选择长期未出现的号码 |
| 综合策略 | 综合频率、遗漏值和结构约束选号 |

**回测结论**：所有策略的长期净收益均为负，符合彩票的数学本质。回测的价值在于验证策略有效性，而非寻找"必胜公式"。

## 🔧 扩展开发

### 新增彩种

1. 在 `src/models/` 下创建新彩种类，继承 `BaseLottery`
2. 在 `src/models/__init__.py` 的工厂方法中注册
3. 在 `config.py` 中添加彩种规则配置
4. 在 `src/collector/` 下创建对应的数据采集器

### 新增策略

1. 在 `src/backtest/strategies.py` 中继承 `BaseStrategy`
2. 实现 `name`、`description` 和 `generate_tickets` 方法
3. 在 `get_all_strategies()` 中注册

## 📝 数据来源

历史开奖数据来源于 [500.com](https://datachart.500.com/ssq/)，仅供学习研究使用。

## 📄 许可证

MIT License
