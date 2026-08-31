"""
AI 服务模块
接入 OpenAI 兼容 API（支持 DeepSeek / 通义千问 / GPT / Ollama 等）
用于基于统计数据筛选优化彩票号码，并生成解读
"""
import os
import json
from typing import List, Dict, Optional
import requests


class AIService:
    """AI 服务（OpenAI 兼容接口）"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or os.environ.get("AI_API_KEY", "")
        self.base_url = base_url or os.environ.get("AI_BASE_URL", "https://api.deepseek.com/v1")
        self.model = model or os.environ.get("AI_MODEL", "deepseek-chat")
        self.timeout = 60

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: List[Dict], temperature: float = 0.7,
             max_tokens: int = 2000) -> Optional[str]:
        """
        调用聊天补全接口
        messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
        返回 AI 回复文本，失败返回 None
        """
        if not self.is_configured:
            print("[AI] 未配置 API Key，跳过 AI 调用")
            return None

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[AI] 调用失败: {e}")
            return None

    def select_lottery_numbers(self, lottery_name: str, candidate_tickets: List[Dict],
                                stats_summary: Dict, count: int = 10) -> List[Dict]:
        """
        基于统计数据和候选池，AI 筛选优化出指定组数的号码

        Args:
            lottery_name: 彩种名称
            candidate_tickets: 候选号码池 [{"red_balls": [...], "blue_balls": [...], "score": ...}]
            stats_summary: 统计摘要 {hot_numbers, cold_numbers, omission, sum_range, ...}
            count: 需要选出的组数

        Returns:
            筛选后的号码列表，每组附带 ai_reason 字段
        """
        if not self.is_configured or not candidate_tickets:
            # 无 AI 时按 score 排序取前 count 组
            sorted_tickets = sorted(candidate_tickets, key=lambda x: x.get("score", 0), reverse=True)
            result = []
            for t in sorted_tickets[:count]:
                result.append({
                    "red_balls": t["red_balls"],
                    "blue_balls": t["blue_balls"],
                    "score": t.get("score", 0),
                    "ai_reason": "（未配置AI，按统计评分排序）",
                })
            return result

        # 构建候选池摘要（控制 token 数量）
        candidate_text = ""
        for i, t in enumerate(candidate_tickets[:30], 1):
            reds = " ".join(f"{n:02d}" for n in t["red_balls"])
            blues = " ".join(f"{n:02d}" for n in t["blue_balls"])
            score = t.get("score", 0)
            features = t.get("features", "")
            candidate_text += f"{i}. 红球[{reds}] 蓝球[{blues}] 评分:{score:.2f} {features}\n"

        stats_text = self._format_stats_summary(stats_summary)

        system_prompt = f"""你是一位专业的彩票数据分析助手。你的任务是基于统计数据从候选号码池中筛选出{count}组最具参考价值的号码。

重要原则：
1. 彩票开奖是随机独立事件，不存在"必中"号码。你的筛选仅基于统计规律和数据特征，不保证中奖。
2. 优先选择统计特征均衡的号码（和值适中、奇偶比合理、区间分布均匀）。
3. 适当兼顾热号（近期高频）和冷号（长期遗漏）的平衡。
4. 避免选择极端结构（全奇/全偶/和值极端/连号过多）。
5. 每组号码之间应有所差异，不要高度相似。

请以 JSON 格式输出，格式如下：
{{
  "selected": [
    {{
      "index": 1,
      "red_balls": [01, 05, 12, 18, 25, 30],
      "blue_balls": [08],
      "reason": "简短理由（30字以内）"
    }}
  ],
  "overall_analysis": "整体分析说明（100字以内）"
}}

只输出 JSON，不要输出其他内容。"""

        user_prompt = f"""彩种：{lottery_name}

【统计摘要】
{stats_text}

【候选号码池】（共{len(candidate_tickets)}组，展示前30组）
{candidate_text}

请从中筛选出{count}组最具参考价值的号码，输出 JSON。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self.chat(messages, temperature=0.6, max_tokens=3000)
        if not response:
            # AI 失败时回退到评分排序
            sorted_tickets = sorted(candidate_tickets, key=lambda x: x.get("score", 0), reverse=True)
            return [
                {
                    "red_balls": t["red_balls"],
                    "blue_balls": t["blue_balls"],
                    "score": t.get("score", 0),
                    "ai_reason": "（AI调用失败，按统计评分排序）",
                }
                for t in sorted_tickets[:count]
            ]

        # 解析 AI 返回的 JSON
        try:
            # 清理可能的 markdown 代码块标记
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            # 找到 JSON 开始位置
            json_start = cleaned.find("{")
            if json_start >= 0:
                cleaned = cleaned[json_start:]
            json_end = cleaned.rfind("}")
            if json_end >= 0:
                cleaned = cleaned[:json_end + 1]

            result = json.loads(cleaned)
            selected = result.get("selected", [])
            overall = result.get("overall_analysis", "")

            final_tickets = []
            for item in selected[:count]:
                reds = sorted([int(n) for n in item.get("red_balls", [])])
                blues = sorted([int(n) for n in item.get("blue_balls", [])])
                final_tickets.append({
                    "red_balls": reds,
                    "blue_balls": blues,
                    "score": 0,
                    "ai_reason": item.get("reason", ""),
                    "overall_analysis": overall,
                })

            # 如果 AI 返回的组数不足，用候选池补充
            if len(final_tickets) < count:
                existing_keys = set(
                    (tuple(t["red_balls"]), tuple(t["blue_balls"])) for t in final_tickets
                )
                sorted_candidates = sorted(candidate_tickets, key=lambda x: x.get("score", 0), reverse=True)
                for t in sorted_candidates:
                    key = (tuple(t["red_balls"]), tuple(t["blue_balls"]))
                    if key not in existing_keys:
                        final_tickets.append({
                            "red_balls": t["red_balls"],
                            "blue_balls": t["blue_balls"],
                            "score": t.get("score", 0),
                            "ai_reason": "（补充候选）",
                        })
                        existing_keys.add(key)
                        if len(final_tickets) >= count:
                            break

            return final_tickets[:count]

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[AI] 解析返回结果失败: {e}")
            print(f"[AI] 原始返回: {response[:500]}")
            # 回退到评分排序
            sorted_tickets = sorted(candidate_tickets, key=lambda x: x.get("score", 0), reverse=True)
            return [
                {
                    "red_balls": t["red_balls"],
                    "blue_balls": t["blue_balls"],
                    "score": t.get("score", 0),
                    "ai_reason": "（AI返回解析失败，按统计评分排序）",
                }
                for t in sorted_tickets[:count]
            ]

    def generate_analysis_report(self, lottery_name: str, stats_summary: Dict,
                                  selected_tickets: List[Dict]) -> str:
        """
        生成 AI 分析报告文字（用于推送和报告）
        """
        if not self.is_configured:
            return self._generate_template_report(lottery_name, stats_summary, selected_tickets)

        stats_text = self._format_stats_summary(stats_summary)
        tickets_text = ""
        for i, t in enumerate(selected_tickets, 1):
            reds = " ".join(f"{n:02d}" for n in t["red_balls"])
            blues = " ".join(f"{n:02d}" for n in t["blue_balls"])
            reason = t.get("ai_reason", "")
            tickets_text += f"第{i}组：红球[{reds}] 蓝球[{blues}] - {reason}\n"

        system_prompt = """你是一位专业的彩票数据分析撰稿人。请根据统计数据和推荐号码，撰写一段简洁的分析推送文案。

要求：
1. 开头说明本期分析结论（1-2句）
2. 简要提及关键统计特征（热号/冷号/和值区间）
3. 提醒理性购彩，彩票是随机事件
4. 总字数控制在200字以内
5. 语气专业、客观，不夸大效果
6. 不要使用"必中""稳赚"等误导性词汇"""

        user_prompt = f"""彩种：{lottery_name}

【统计摘要】
{stats_text}

【推荐号码】
{tickets_text}

请撰写分析推送文案。"""

        response = self.chat(
            [{"role": "system", "content": system_prompt},
             {"role": "user", "content": user_prompt}],
            temperature=0.5, max_tokens=800
        )
        return response if response else self._generate_template_report(lottery_name, stats_summary, selected_tickets)

    def _format_stats_summary(self, stats: Dict) -> str:
        """格式化统计摘要为文本"""
        lines = []
        if "hot_red" in stats:
            lines.append(f"红球热号：{' '.join(f'{n:02d}' for n in stats['hot_red'][:6])}")
        if "cold_red" in stats:
            lines.append(f"红球冷号：{' '.join(f'{n:02d}' for n in stats['cold_red'][:6])}")
        if "hot_blue" in stats:
            lines.append(f"蓝球热号：{' '.join(f'{n:02d}' for n in stats['hot_blue'][:3])}")
        if "cold_blue" in stats:
            lines.append(f"蓝球冷号：{' '.join(f'{n:02d}' for n in stats['cold_blue'][:3])}")
        if "sum_range" in stats:
            lines.append(f"和值区间：{stats['sum_range']}")
        if "common_parity" in stats:
            lines.append(f"常见奇偶比：{stats['common_parity']}")
        if "omission_red" in stats:
            lines.append(f"红球高遗漏：{' '.join(f'{n:02d}({g}期)' for n, g in stats['omission_red'][:5])}")
        return "\n".join(lines) if lines else "（无统计数据）"

    def _generate_template_report(self, lottery_name: str, stats: Dict,
                                   tickets: List[Dict]) -> str:
        """无 AI 时生成模板报告"""
        lines = [f"【{lottery_name}本期分析】"]
        if "hot_red" in stats:
            lines.append(f"红球热号：{' '.join(f'{n:02d}' for n in stats['hot_red'][:6])}")
        if "cold_red" in stats:
            lines.append(f"红球冷号：{' '.join(f'{n:02d}' for n in stats['cold_red'][:6])}")
        lines.append(f"共推荐{len(tickets)}组号码，仅供参考。")
        lines.append("彩票开奖具有随机性，请理性购彩。")
        return "\n".join(lines)
