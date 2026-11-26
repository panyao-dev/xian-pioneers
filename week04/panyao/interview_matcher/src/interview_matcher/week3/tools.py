"""W3 对外集成工具（只读边界优先）。

四个工具都遵守项目红线：
- 简历只临时读取、脱敏后使用，不回写招聘系统、不下载到长期存储；
- 推荐清单只生成待 HR 确认的草稿，不自动派单、不通知面试官、不创建会议；
- 日历只返回可面试时段建议，不锁定会议；
- HR 手动指定结论优先级最高，工具只读取并覆盖规则排序，不自动改派。

真实招聘系统 / 飞书接口后续在各适配器方法内补 HTTP 调用；当前本地数据
（hr_data.json + 本地 PDF）用于跑通工具调用与反思闭环。
"""

from __future__ import annotations

import json
from pathlib import Path

from interview_matcher.common import resume_loader

DATA_PATH = Path(__file__).parent / "hr_data.json"

# 给模型看的工具说明书（OpenAI function calling schema）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_resume_from_hr_system",
            "description": "从招聘系统 / 飞书文档 / 本地文件只读拉取简历附件文本；不回写、不长期存储。",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_ref": {
                        "type": "string",
                        "description": "本地 PDF 路径、招聘系统单据号或飞书文档标识。",
                    },
                    "source": {
                        "type": "string",
                        "enum": ["local_file", "hr_system", "feishu_doc"],
                        "description": "来源渠道；local_file 读本地 PDF，其余两类为后续只读适配器。",
                    },
                },
                "required": ["resume_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "push_recommendation_card",
            "description": "把面试官推荐清单整理成待 HR 确认的卡片草稿；不自动派单、不创建会议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_ref": {"type": "string", "description": "候选人单据号或简历标识。"},
                    "recommend": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "interviewer_id": {"type": "string"},
                                "name": {"type": "string"},
                                "match_reason": {"type": "string"},
                            },
                            "required": ["interviewer_id", "name"],
                        },
                        "description": "推荐面试官列表，含工号、姓名、匹配理由。",
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["group", "private"],
                        "description": "推送渠道：HR 群聊或私聊。",
                    },
                    "target": {
                        "type": "string",
                        "description": "群聊 ID 或 HR 私聊对象；未配置时只生成草稿。",
                    },
                    "note": {"type": "string", "description": "附带给 HR 的备注。"},
                },
                "required": ["candidate_ref", "recommend"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_interviewer_calendar",
            "description": "只读查询面试官可面试时段，给出排期建议；不锁定、不预订会议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "interviewer_id": {"type": "string", "description": "面试官工号，例如 XA-1042。"},
                    "date_from": {"type": "string", "description": "可选，起始日期 YYYY-MM-DD。"},
                    "date_to": {"type": "string", "description": "可选，截止日期 YYYY-MM-DD。"},
                },
                "required": ["interviewer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_hr_override",
            "description": "读取 HR 手动指定的优先面试官；人工结论覆盖规则排序，优先级最高。",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_ref": {"type": "string", "description": "候选人单据号或简历标识。"},
                    "preferred_interviewer_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "HR 当次手动指定的面试官工号；不传则读取本地 HR 覆盖记录。",
                    },
                    "source": {"type": "string", "description": "人工结论来源，例如 hr_message / hr_system。"},
                },
                "required": ["candidate_ref"],
            },
        },
    },
]


def _load_data() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def fetch_resume_from_hr_system(resume_ref: str, source: str = "local_file") -> dict:
    """只读拉取简历；本地文件走 resume_loader 脱敏，外部来源留适配器位。"""
    if source == "local_file":
        raw = resume_loader.load_pdf_text(resume_ref)
        text = resume_loader.strip_pii(raw)
        return {
            "read_only": True,
            "persisted": False,
            "source": source,
            "resume_ref": resume_ref,
            "text": text,
            "text_length": len(text),
            "pii_redacted": True,
        }

    return {
        "read_only": True,
        "persisted": False,
        "source": source,
        "resume_ref": resume_ref,
        "status": "adapter_not_connected",
        "message": "招聘系统 / 飞书文档适配器尚未连接；当前只支持本地 PDF 只读解析，不回写、不长期存储。",
    }


def push_recommendation_card(
    candidate_ref: str,
    recommend: list[dict],
    channel: str = "private",
    target: str | None = None,
    note: str | None = None,
) -> dict:
    """生成推荐卡片草稿；默认不真实推送，更不自动派单。"""
    lines = [
        f"{idx + 1}. {item.get('interviewer_id', '')} {item.get('name', '')}："
        f"{item.get('match_reason', '待补充匹配理由')}"
        for idx, item in enumerate(recommend)
    ]
    card = {
        "title": "面试官推荐清单（待 HR 确认）",
        "candidate_ref": candidate_ref,
        "channel": channel,
        "target": target,
        "lines": lines,
        "note": note,
    }
    return {
        "auto_dispatch": False,
        "requires_human_confirm": True,
        "pushed": False,
        "card": card,
        "message": "清单仅生成草稿：不通知面试官、不创建会议、不自动派单；由 HR 手动指定或确认后再排期。",
    }


def query_interviewer_calendar(
    interviewer_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """只读返回可面试时段；不锁定会议。"""
    data = _load_data()
    slots = list(data.get("calendar", {}).get(interviewer_id, []))
    if date_from:
        slots = [s for s in slots if s >= date_from]
    if date_to:
        slots = [s for s in slots if s <= date_to + " 23:59"]
    return {
        "interviewer_id": interviewer_id,
        "read_only": True,
        "locked": False,
        "available_slots": slots,
        "message": "仅返回可面试时段建议，不锁定、不预订会议；最终排期由 HR 确认。",
    }


def notify_hr_override(
    candidate_ref: str,
    preferred_interviewer_ids: list[str] | None = None,
    source: str = "hr_message",
) -> dict:
    """读取 HR 手动覆盖结论；人工优先级最高，工具不改派。"""
    if preferred_interviewer_ids:
        preferred = list(preferred_interviewer_ids)
        note = "HR 当次手动指定"
    else:
        data = _load_data()
        record = data.get("hr_override", {}).get(candidate_ref, {})
        preferred = list(record.get("preferred_interviewer_ids", []))
        note = record.get("note")

    return {
        "override_applied": bool(preferred),
        "preferred_interviewer_ids": preferred,
        "priority": "manual_highest",
        "rule_sort_locked": False,
        "source": source,
        "note": note,
        "message": "人工指定优先于规则排序；工具只读取结论并置顶，不自动改派面试官。",
    }


TOOL_IMPL = {
    "fetch_resume_from_hr_system": fetch_resume_from_hr_system,
    "push_recommendation_card": push_recommendation_card,
    "query_interviewer_calendar": query_interviewer_calendar,
    "notify_hr_override": notify_hr_override,
}
