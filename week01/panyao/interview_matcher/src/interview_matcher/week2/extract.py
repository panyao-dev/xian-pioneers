from __future__ import annotations

import json
import re

from interview_matcher.common.llm_client import LLMClient
from interview_matcher.common.tags import ANDROID_LEVELS, ANDROID_TAGS

from interview_matcher.week2 import prompts

REQUIRED_FIELDS = [
    "primary_level",
    "core_focus",
    "secondary_skill",
    "not_suitable_interview",
]

VOCAB = set(ANDROID_LEVELS) | set(ANDROID_TAGS)


def oov_tags(pred: dict[str, list[str]]) -> list[str]:
    """找出模型编出来、不在封闭词表内的标签。"""
    return sorted({tag for tags in pred.values() for tag in tags if tag not in VOCAB})



def parse_json(text: str) -> tuple[dict, bool, str | None]:
    """从模型返回文本里抠出 JSON 对象。

    容忍：Markdown 代码块、CoT 在 JSON 前写的 reasoning 文字、首尾多余字符。
    解析失败时返回空结构 + parse_ok=False。
    """
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
    if fence:
        cleaned = fence.group(1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return {}, False, "未找到 JSON 对象"

    try:
        obj = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        return {}, False, f"JSON 解析失败：{exc.msg}"

    if not isinstance(obj, dict):
        return {}, False, "返回不是 JSON 对象"

    pred: dict[str, list[str]] = {}
    for field in REQUIRED_FIELDS:
        raw = obj.get(field, [])
        if isinstance(raw, list):
            pred[field] = [str(x).strip() for x in raw if str(x).strip()]
        elif isinstance(raw, str) and raw.strip():
            pred[field] = [raw.strip()]
        else:
            pred[field] = []
    return pred, True, None





def extract(strategy: str, resume: dict, client: LLMClient | None = None) -> dict:
    client = client or LLMClient()
    messages = prompts.build_messages(strategy, resume["resume_text"])
    result = client.chat(messages, temperature=0.2)

    pred, parse_ok, parse_error = parse_json(result["content"])
    return {
        "resume_id": resume["resume_id"],
        "name": resume["name"],
        "strategy": strategy,
        "pred": pred,
        "raw": result["content"],
        "parse_ok": parse_ok,
        "parse_error": parse_error,
        "usage": result.get("usage", {}),
    }
