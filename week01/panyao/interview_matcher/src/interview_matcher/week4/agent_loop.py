"""W4：手写 Agent Loop（输入校验 / 工具参数校验 / 输出校验 / 最大轮数限制）。

与 W3 的差别：W3 重点是"反思"，W4 把 Loop 本身做扎实——
每一步都有一道闸门，校验不通过不崩、不静默放过，而是带原因回灌重试，
并且全程有轮数上限与结构化终止原因，可直接用于线上兜底。

流程：
  输入校验 → [模型决策] → 工具名/参数校验 → 本地执行 → 结果回灌
  → 无工具调用 → 输出校验 → 通过则结束；不通过则回灌修正（限 1 次）
  → 超过 max_steps 则结构化终止

用法：
  uv run w4-loop [问题]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from interview_matcher.common.llm_client import LLMClient
from interview_matcher.week3 import tools
from interview_matcher.week4 import validation

MAX_STEPS = 5
MAX_OUTPUT_RETRIES = 1
TRACE_PATH = Path(__file__).parent / "trace.json"


def _load_pool_ids() -> set[str]:
    path = Path(__file__).parent.parent / "week1" / "interviewer_pool.json"
    pool = json.loads(path.read_text(encoding="utf-8"))
    return {item["interviewer_id"] for item in pool}


SYSTEM_PROMPT = (
    "你是 Android 招聘匹配助手。你的所有工具都是只读或草稿性质：\n"
    "- 读简历只读、不长期存储；\n"
    "- 查日历只给时段建议，不锁定会议；\n"
    "- HR 手动指定的面试官优先级最高；\n"
    "- 推荐卡片只是待 HR 确认的草稿，不自动派单、不通知面试官、不创建会议。\n"
    "工具参数必须严格符合 schema：只传 schema 里定义过的字段，别名字段会被校验拒绝。\n"
    "最终回答必须说明结论，并明确提示需要 HR 确认；不要编造工号、时段或简历内容。"
)


def _execute(tool_name: str, args: dict) -> dict:
    impl = tools.TOOL_IMPL.get(tool_name)
    if impl is None:
        return {"error": f"未实现的工具：{tool_name}"}
    try:
        return impl(**args)
    except TypeError as exc:
        return {"error": f"工具入参不匹配：{exc}"}
    except Exception as exc:  # 工具内部异常不应击穿 Loop
        return {"error": f"工具执行异常：{type(exc).__name__}: {exc}"}


def run(question: str, max_steps: int = MAX_STEPS, model: str | None = None) -> dict:
    """跑一次 Agent Loop，返回结构化结果（含 trace）。model 为空时取 .env 配置。"""
    trace: dict[str, Any] = {"question": question, "steps": [], "terminated_by": None}
    known_ids = _load_pool_ids()

    # ---- 闸门 1：输入校验 ----
    ok, text, input_errors = validation.validate_input(question)
    if not ok:
        trace["terminated_by"] = "input_invalid"
        return {"ok": False, "answer": "", "errors": input_errors, "trace": trace}

    print(f"[输入校验] 通过（{len(text)} 字符）")
    print(f"[提问] {text}")
    print("-" * 60)

    client = LLMClient(model=model)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    output_retries = 0

    for step in range(1, max_steps + 1):
        result = client.chat(messages, tools=tools.TOOLS)
        step_log: dict[str, Any] = {"step": step, "tool_calls": []}

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

        # ---- 收敛分支：无工具调用 → 输出校验 ----
        if not result["tool_calls"]:
            check = validation.validate_output(result["content"], known_ids)
            step_log["output_check"] = check

            if check["ok"]:
                print(f"[第 {step} 步] 模型作答，输出校验通过，循环结束")
                for warn in check["warnings"]:
                    print(f"          [提醒] {warn}")
                print("[回答]")
                print(result["content"].strip())
                trace["steps"].append(step_log)
                trace["terminated_by"] = "answered"
                return {"ok": True, "answer": result["content"].strip(),
                        "errors": [], "warnings": check["warnings"], "trace": trace}

            if output_retries < MAX_OUTPUT_RETRIES:
                output_retries += 1
                print(f"[第 {step} 步] 输出校验未通过：{check['errors']}，回灌修正")
                messages.append({
                    "role": "system",
                    "content": "输出校验未通过：" + "；".join(check["errors"]) + "。请修正后重新作答。",
                })
                trace["steps"].append(step_log)
                continue

            print(f"[第 {step} 步] 输出校验连续未通过，强制终止：{check['errors']}")
            trace["steps"].append(step_log)
            trace["terminated_by"] = "output_invalid"
            return {"ok": False, "answer": result["content"].strip(),
                    "errors": check["errors"], "trace": trace}

        # ---- 工具分支：逐个校验、执行、回灌 ----
        for tc in result["tool_calls"]:
            name = tc["name"]

            # 闸门 2：工具名存在性
            schema = validation.schema_of(name, tools.TOOLS)
            if schema is None:
                error_payload = {"error": f"未知工具：{name}", "hint": "只能调用已注册的工具"}
                print(f"[第 {step} 步] 拒绝未知工具：{name}")
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": json.dumps(error_payload, ensure_ascii=False)})
                step_log["tool_calls"].append({"name": name, "status": "unknown_tool"})
                continue

            # 闸门 3：参数校验
            try:
                args = json.loads(tc["arguments"] or "{}")
                parse_error = None
            except json.JSONDecodeError as exc:
                args = {}
                parse_error = f"arguments 不是合法 JSON：{exc.msg}"

            arg_errors = [parse_error] if parse_error else validation.validate_tool_args(name, args, schema)

            if arg_errors:
                error_payload = {
                    "error": "参数校验未通过，工具未执行",
                    "errors": arg_errors,
                    "hint": "请按 schema 修正参数后重试",
                }
                print(f"[第 {step} 步] 参数校验拒绝 {name}：{arg_errors}")
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": json.dumps(error_payload, ensure_ascii=False)})
                step_log["tool_calls"].append({"name": name, "args": args, "status": "invalid_args",
                                               "errors": arg_errors})
                continue

            output = _execute(name, args)
            print(f"[第 {step} 步] 执行工具 {name}({json.dumps(args, ensure_ascii=False)})")
            print(f"          返回：{json.dumps(output, ensure_ascii=False)[:260]}")
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": json.dumps(output, ensure_ascii=False)})
            step_log["tool_calls"].append({"name": name, "args": args, "status": "ok",
                                           "output_keys": sorted(output.keys())})

        trace["steps"].append(step_log)

    # ---- 闸门 4：最大轮数兜底 ----
    print(f"[终止] 达到最大轮数 {max_steps}，结构化终止（未产出最终回答）")
    trace["terminated_by"] = "max_steps"
    return {
        "ok": False,
        "answer": "",
        "errors": [f"达到最大轮数 {max_steps}，本次未收敛"],
        "trace": trace,
    }


DEFAULT_QUESTION = (
    "请为候选人 demo-001 准备面试官推荐：先读取 HR 手动指定的优先面试官，"
    "再查询他们的可面试时段，最后生成一张待 HR 确认的推荐卡片草稿；不要自动派单。"
)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="W4 手写 Agent Loop（带校验与轮数上限）")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION, help="用户提问")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS, help="最大轮数")
    parser.add_argument("--model", default=None, help="临时覆盖 LLM_MODEL，用于多模型对比")
    args = parser.parse_args()

    result = run(args.question, max_steps=args.max_steps, model=args.model)
    TRACE_PATH.write_text(json.dumps(result["trace"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[trace] 已写入 {TRACE_PATH}")
    print(f"[结果] ok={result['ok']}  terminated_by={result['trace']['terminated_by']}")
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
