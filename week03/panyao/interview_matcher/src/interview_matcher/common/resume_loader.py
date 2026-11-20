"""简历 PDF 文本抽取与基础脱敏。

合规口径：候选人简历不入库、用完即删；存档前先剥掉手机号 / 邮箱 / 链接 / 联系方式行，
Prompt 侧也要求模型不抽取个人信息。
"""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

_PII_PATTERNS = [
    re.compile(r"1[3-9]\d{9}"),  # 手机号
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),  # 邮箱
    re.compile(r"https?://\S+"),  # 链接
]

# 整行含这些关键词的直接剔除（联系方式 / 教育 / 奖项 / 自我评价 / 人口属性）
_PII_LINE_KEYWORDS = [
    "电话", "邮箱", "年龄", "籍贯", "博客", "毕业院校",
    "大学", "学院", "大赛", "竞赛", "奖", "自我评价", "职业规划",
    "性别", "岁", "姓 名", "姓名", "到岗时间",
]

# PDF 水印 / 追踪串：形如 54025e19c9e41ff303R42d-7FlBUxYS7V_OfWOGjm_XRMBJq1w~~
_WATERMARK = re.compile(r"[0-9a-f]{20,}R\d+[-_A-Za-z0-9~]+")

_DATE_LINE = re.compile(r"\d{4}/\d{1,2}[-–—]\d{4}/\d{1,2}")
_NAME_LINE = re.compile(r"^[一-龥]{2,4}$")


def load_pdf_text(path: str | Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def strip_pii(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(keyword in s for keyword in _PII_LINE_KEYWORDS):
            continue
        if _DATE_LINE.search(s):
            continue
        if _NAME_LINE.match(s):
            kept.append("[已脱敏姓名]")
            continue
        s = _WATERMARK.sub("", s).strip()
        if not s:
            continue
        kept.append(s)
    cleaned = "\n".join(kept)
    for pattern in _PII_PATTERNS:
        cleaned = pattern.sub("[已脱敏]", cleaned)
    return cleaned
