from __future__ import annotations

import json

from interview_matcher.common.tags import ANDROID_LEVELS, ANDROID_TAGS

# 三套提示词拼装器

STRATEGIES = ("zero_shot", "few_shot", "cot")

# 独立示例：车机方向，只给 Few-Shot 用，不参与评测，避免标签泄漏。
FEW_SHOT_EXAMPLE = {
    "resume_text": (
        "车机团队 3 年。负责 Flyme Auto 车机桌面与 HMI 定制，"
        "处理车机按键与仪表联动；做过车机 HMI 布局适配。"
    ),
    "output": {
        "primary_level": ["车机专项"],
        "core_focus": ["Flyme Auto车机定制", "车机HMI"],
        "secondary_skill": [],
        "not_suitable_interview": ["Linux内核", "HAL硬件抽象层开发"],
    },
}

SYSTEM_ROLE = (
    "你是 Android 技术简历解析专家，只根据简历里明确写到的项目事实抽取标签，"
    "禁止编造简历没提到的技术；不抽取性别、年龄、婚育、院校等个人信息。"
)

WORDLIST = (
    f"【层级词表】{ '、'.join(ANDROID_LEVELS) }\n"
    f"【技能词表】{ '、'.join(ANDROID_TAGS) }"
)

FIELD_RULES = (
    "【字段定义】\n"
    "- primary_level：主攻层级，1~2 个，必须来自层级词表；\n"
    "- core_focus：深度主导、完整项目落地的方向，3~6 个，只放技能词表里的主攻深度方向；\n"
    "- secondary_skill：会用过但非主攻的方向，0~5 个，可为空；\n"
    "- not_suitable_interview：相邻但无深度实践、不适合做主考的方向，3~8 个；"
    "禁止把整张词表都填进来，只挑简历事实相邻的方向。"
)

OUTPUT_CONTRACT = (
    "【输出格式】只输出一个 JSON 对象，不要解释、不要 Markdown 代码块：\n"
    '{"primary_level": [], "core_focus": [], "secondary_skill": [], '
    '"not_suitable_interview": []}'
)

COT_CONTRACT = (
    "【输出格式】先输出 reasoning 字段记录分步判断，再输出结果字段：\n"
    '{"reasoning": "...", "primary_level": [], "core_focus": [], '
    '"secondary_skill": [], "not_suitable_interview": []}'
)


def _base_task(resume_text: str) -> str:
    return (
        "请解析下面这份 Android 技术简历，输出结构化标签。\n\n"
        f"{WORDLIST}\n\n"
        f"{FIELD_RULES}\n\n"
        f"{OUTPUT_CONTRACT}\n\n"
        f"【简历】\n{resume_text}"
    )


def _few_shot_block() -> str:
    ex = FEW_SHOT_EXAMPLE
    return (
        "【示例】\n"
        f"简历：{ex['resume_text']}\n"
        f"输出：{json.dumps(ex['output'], ensure_ascii=False)}\n\n"
    )


def build_messages(strategy: str, resume_text: str) -> list[dict[str, str]]:
    """按策略构造 messages。strategy 必须来自 STRATEGIES。"""
    if strategy not in STRATEGIES:
        raise ValueError(f"未知策略：{strategy}")

    if strategy == "zero_shot":
        return [
            {"role": "system", "content": SYSTEM_ROLE},
            {"role": "user", "content": _base_task(resume_text)},
        ]

    if strategy == "few_shot":
        user = _few_shot_block() + _base_task(resume_text)
        return [
            {"role": "system", "content": SYSTEM_ROLE},
            {"role": "user", "content": user},
        ]

    # CoT：在任务里插入分步思考要求，输出契约带 reasoning。
    cot_task = (
        "请解析下面这份 Android 技术简历，输出结构化标签。\n\n"
        f"{WORDLIST}\n\n"
        f"{FIELD_RULES}\n\n"
        "【思考步骤】先在 reasoning 中按三步判断：\n"
        "1. 列出简历明确写到的项目事实；\n"
        "2. 区分哪些是深度主导/完整落地，哪些只是会用过；相邻但无深度实践的归入 not_suitable；\n"
        "3. 把事实映射到词表标签，词表外的说法不要造新标签。\n\n"
        f"{COT_CONTRACT}\n\n"
        f"【简历】\n{resume_text}"
    )
    return [
        {"role": "system", "content": SYSTEM_ROLE},
        {"role": "user", "content": cot_task},
    ]
