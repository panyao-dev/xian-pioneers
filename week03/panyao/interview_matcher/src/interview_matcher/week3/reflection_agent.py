"""W3 反思式工具调用 Agent。

流程：模型选择工具 → 本地执行只读工具 → 反思结果是否可信/合规 →
把工具结果与反思意见回灌 → 无工具调用时收敛。默认不接真实飞书推送，
所有对外动作都停在"草稿/建议"边界，等 HR 人工确认。
"""

from __future__ import annotations

import json
import sys

from interview_matcher.common.llm_client import LLMClient
from interview_matcher.week3 import tools

MAX_STEPS = 5

SYSTEM_PROMPT = (
    "你是 Android 招聘匹配助手。可用工具均为只读或草稿性质：\n"
    "- 读取简历只读不长期存储；\n"
    "- 查日历只给时段建议，不锁定会议；\n"
    "- HR 手动指定的面试官优先级最高，覆盖规则排序；\n"
    "- 推荐卡片只是待 HR 确认的草稿，不自动派单、不通知面试官、不创建会议。\n"
    "不要编造工具未返回的面试官、时段或简历内容；工具结果为空时如实说明。"
)


def reflect(tool_name: str, output: dict) -> list[str]:
    """对工具返回做合规与可信度反思，返回需要回灌给模型的意见。"""
    issues: list[str] = []

    if tool_name == "fetch_resume_from_hr_system":
        if output.get("status") == "adapter_not_connected":
            issues.append("招聘系统适配器未连接：只能依据本地可读文件，不要编造外部简历内容。")
        elif not output.get("text"):
            issues.append("简历文本为空：需要让 HR 补充附件或换可读来源，不要硬抽标签。")

    elif tool_name == "query_interviewer_calendar":
        if not output.get("available_slots"):
            issues.append("该面试官当前无可读时段：结果中标注不可约，不要编造时间。")

    elif tool_name == "notify_hr_override":
        if not output.get("preferred_interviewer_ids"):
            issues.append("暂无 HR 手动覆盖结论：按规则排序结果推荐，不要冒充人工指定。")
        else:
            issues.append("存在 HR 手动指定：这些面试官必须排在规则结果之前。")

    elif tool_name == "push_recommendation_card":
        issues.append("卡片是待确认草稿：不自动派单、不创建会议，必须提示由 HR 确认。")

    return issues


def run(question: str, max_steps: int = MAX_STEPS) -> None:
    client = LLMClient()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    print(f"[提问] {question}")
    print("-" * 60)

    for step in range(1, max_steps + 1):
        result = client.chat(messages, tools=tools.TOOLS)

        assistant_msg: dict = {"role": "assistant", "content": result["content"]}
        if result["tool_calls"]:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in result["tool_calls"]
            ]
        messages.append(assistant_msg)

        if not result["tool_calls"]:
            print(f"[第 {step} 步] 模型直接作答，循环结束")
            print("[回答]")
            print(result["content"])
            return

        for tc in result["tool_calls"]:
            try:
                args = json.loads(tc["arguments"] or "{}")
            except json.JSONDecodeError as exc:
                args = {}
                print(f"[工具参数解析失败] {exc}")

            impl = tools.TOOL_IMPL.get(tc["name"])
            print(f"[第 {step} 步] 模型选择工具：{tc['name']}({json.dumps(args, ensure_ascii=False)})")
            output = impl(**args) if impl else {"error": f"未实现的工具：{tc['name']}"}
            print(f"          执行结果：{json.dumps(output, ensure_ascii=False)[:300]}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(output, ensure_ascii=False),
                }
            )

            issues = reflect(tc["name"], output)
            if issues:
                reflection = "；".join(issues)
                print(f"          反思意见：{reflection}")
                messages.append({"role": "system", "content": f"反思：{reflection}"})

    print(f"[警告] 已达最大轮次 {max_steps}，强制终止，避免无限循环。")


DEFAULT_QUESTION = (
    "请为候选人 demo-001 准备面试官推荐：先读取 HR 手动指定的优先面试官，"
    "再查询他们的可面试时段，最后生成一张待 HR 确认的推荐卡片草稿；不要自动派单。"
)


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION
    run(question)


if __name__ == "__main__":
    main()
