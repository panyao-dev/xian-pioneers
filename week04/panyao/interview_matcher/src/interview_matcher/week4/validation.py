"""W4 校验层：输入校验 + 工具参数校验 + 输出校验。

设计取向：所有校验都是"可回灌的"——校验不通过不抛异常终止，
而是把具体错误原因交回模型，让它修正后重试，最多重试有限次。
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------- 输入校验

MAX_QUESTION_CHARS = 2000
MIN_QUESTION_CHARS = 4


def validate_input(question: Any) -> tuple[bool, str, list[str]]:
    """校验用户输入。返回 (是否通过, 归一化文本, 错误列表)。"""
    errors: list[str] = []

    if not isinstance(question, str):
        return False, "", [f"输入必须是字符串，实际类型：{type(question).__name__}"]

    text = question.strip()
    if len(text) < MIN_QUESTION_CHARS:
        errors.append(f"输入过短（{len(text)} 字符），至少 {MIN_QUESTION_CHARS} 字符")
    if len(text) > MAX_QUESTION_CHARS:
        errors.append(f"输入过长（{len(text)} 字符），上限 {MAX_QUESTION_CHARS} 字符")
    if "\x00" in text:
        errors.append("输入包含空字节，疑似非法内容")

    return not errors, text, errors


# ------------------------------------------------------------ 工具参数校验

_TYPE_MAP: dict[str, Any] = {
    "string": str,
    "array": list,
    "object": dict,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def _check_value(value: Any, schema: dict, path: str) -> list[str]:
    """按 JSON Schema 子集校验单个值：type / enum / items / minItems / maxItems。"""
    errors: list[str] = []
    expected = schema.get("type")

    if expected:
        py_type = _TYPE_MAP.get(expected)
        if py_type is None:
            return errors
        # bool 是 int 的子类，需要单独排除，避免 True 被当成 integer 通过
        if expected in {"integer", "number"} and isinstance(value, bool):
            return [f"{path} 类型错误：期望 {expected}，实际 boolean"]
        if not isinstance(value, py_type):
            errors.append(f"{path} 类型错误：期望 {expected}，实际 {type(value).__name__}")
            return errors

    enum = schema.get("enum")
    if enum is not None and value not in enum:
        errors.append(f"{path} 取值 {value!r} 不在允许范围 {enum} 内")

    if isinstance(value, list):
        items = schema.get("items")
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if min_items is not None and len(value) < min_items:
            errors.append(f"{path} 元素过少：至少 {min_items} 个，实际 {len(value)} 个")
        if max_items is not None and len(value) > max_items:
            errors.append(f"{path} 元素过多：最多 {max_items} 个，实际 {len(value)} 个")
        if isinstance(items, dict):
            for idx, item in enumerate(value):
                errors.extend(_check_value(item, items, f"{path}[{idx}]"))

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                errors.append(f"{path} 缺少必填字段：{key}")
        if schema.get("additionalProperties") is not True:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                errors.append(f"{path} 出现未定义字段：{', '.join(unknown)}（只允许 schema 内字段）")
        for key, sub_schema in properties.items():
            if key in value and isinstance(sub_schema, dict):
                errors.extend(_check_value(value[key], sub_schema, f"{path}.{key}"))

    return errors


def validate_tool_args(tool_name: str, args: Any, schema: dict) -> list[str]:
    """校验模型给出的工具参数。schema 即工具 TOOLS 里的 parameters 段。"""
    if not isinstance(args, dict):
        return [f"工具 {tool_name} 的 arguments 必须是 JSON 对象，实际：{type(args).__name__}"]
    return _check_value(args, schema, f"{tool_name}.arguments")


def schema_of(tool_name: str, tools: list[dict]) -> dict | None:
    for tool in tools:
        fn = tool.get("function", {})
        if fn.get("name") == tool_name:
            return fn.get("parameters", {})
    return None


# ---------------------------------------------------------------- 输出校验

_PII_PATTERNS = [
    (re.compile(r"1[3-9]\d{9}"), "疑似手机号"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "疑似邮箱"),
    (re.compile(r"\d{17}[\dXx]"), "疑似身份证号"),
]
_INTERVIEWER_ID = re.compile(r"XA-\d{4}")

# 输出里不允许出现的越界表述（业务红线）
_FORBIDDEN_PHRASES = [
    ("已自动派单", "不得声称自动派单"),
    ("已通知面试官", "不得声称已通知面试官"),
    ("已锁定会议", "不得声称已锁定会议"),
    ("已创建会议", "不得声称已创建会议"),
    ("已回写招聘系统", "不得声称回写招聘系统"),
]

MIN_ANSWER_CHARS = 8


def validate_output(answer: Any, known_interviewer_ids: set[str]) -> dict:
    """校验模型最终回答：完整性、PII 泄漏、编造工号、业务越界表述。"""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(answer, str) or not answer.strip():
        return {"ok": False, "errors": ["最终回答为空"], "warnings": []}

    text = answer.strip()
    if len(text) < MIN_ANSWER_CHARS:
        errors.append(f"最终回答过短（{len(text)} 字符），至少要说明结论")

    for pattern, label in _PII_PATTERNS:
        if pattern.search(text):
            errors.append(f"回答中{label}未脱敏，必须去掉个人联系方式")

    for phrase, label in _FORBIDDEN_PHRASES:
        if phrase in text:
            errors.append(f"回答出现「{phrase}」：{label}")

    unknown = sorted({m for m in _INTERVIEWER_ID.findall(text)} - known_interviewer_ids)
    if unknown:
        errors.append(f"回答提到面试官池中不存在的工号：{', '.join(unknown)}，疑似编造")

    if "确认" not in text:
        warnings.append("回答未提示需 HR 确认；若本次已产出推荐草稿，应明确待确认")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
