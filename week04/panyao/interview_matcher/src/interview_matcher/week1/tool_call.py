from __future__ import annotations

import json
import sys
from pathlib import Path

from interview_matcher.common.llm_client import LLMClient
from interview_matcher.common.tags import SLOT_RULES

POOL_PATH = Path(__file__).parent / "interviewer_pool.json"
MAX_STEPS = 5
# 给模型看的说明书
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_interviewer_pool",
            "description": "按技术领域查询可用面试官，返回姓名、工号、核心擅长方向、可承担轮次。",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "技术领域关键词，例如 SystemUI、Launcher3、Linux内核、设备驱动",
                    }
                },
                "required": ["domain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_interview_slot_rule",
            "description": "查询社招或校招的面试轮次安排，返回每一轮的角色要求。",
            "parameters": {
                "type": "object",
                "properties": {
                    "recruit_type": {
                        "type": "string",
                        "enum": ["社招", "校招"],
                        "description": "招聘类型",
                    }
                },
                "required": ["recruit_type"],
            },
        },
    },
]


# 工具调用
def query_interviewer_pool(domain: str) -> dict:
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    keyword = domain.strip().lower()
    available = [item for item in pool if item["available"]]
    hits = [
        item
        for item in available
        if any(keyword in tag.lower() for tag in item["core_focus"] + item["secondary_skill"])
    ]
    return {
        "domain": domain,
        "total_available": len(available),
        "matched": len(hits),
        "interviewers": [
            {
                "interviewer_id": item["interviewer_id"],
                "name": item["name"],
                "core_focus": item["core_focus"],
                "interview_role": item["interview_role"],
            }
            for item in hits
        ],
    }


def get_interview_slot_rule(recruit_type: str) -> dict:
    rules = SLOT_RULES.get(recruit_type.strip())
    if rules is None:
        return {"error": f"不支持的招聘类型：{recruit_type}，仅支持 社招 / 校招"}
    return {"recruit_type": recruit_type.strip(), "round_count": len(rules), "rounds": rules}


TOOL_IMPL = {
    "query_interviewer_pool": query_interviewer_pool,
    "get_interview_slot_rule": get_interview_slot_rule,
}

def run(question: str, max_steps: int = MAX_STEPS) -> None:
    client = LLMClient()
    messages = [
        {
            "role": "system",
            "content": "你是 Android 招聘助手。需要查面试官或查流程规则时必须调用工具，"
            "不要凭记忆编造。查到数据后用人话总结，并给出下一步建议。",
        },
        {"role": "user", "content": question},
    ]

    print(f"[提问] {question}")
    print("-" * 60)

    for step in range(1, max_steps + 1):
        result = client.chat(messages, tools=TOOLS)

        assistant_msg = {"role": "assistant", "content": result["content"]}
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
            args = json.loads(tc["arguments"] or "{}")
            impl = TOOL_IMPL.get(tc["name"])
            print(f"[第 {step} 步] 模型选择工具：{tc['name']}({args})")
            output = impl(**args) if impl else {"error": f"未实现的工具：{tc['name']}"}
            print(f"          执行结果：{json.dumps(output, ensure_ascii=False)[:300]}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(output, ensure_ascii=False),
                }
            )

    print(f"[警告] 已达最大轮次 {max_steps}，强制终止，避免无限循环。")


DEFAULT_QUESTION = "帮我查一下会 SystemUI 定制的面试官有哪些？"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION
    run(question)


if __name__ == "__main__":
    main()
