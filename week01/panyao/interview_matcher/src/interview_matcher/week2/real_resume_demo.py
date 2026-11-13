"""真实简历解析演示：PDF → 脱敏 → 按 zero_shot / few_shot / cot 三策略抽取标签。

用法：
  uv run w2-real <简历.pdf> [简历2.pdf ...]            # 每份跑三策略
  uv run w2-real <简历.pdf> zero_shot                 # 只跑指定策略
策略：zero_shot / few_shot / cot。明细落 `week2/results.json`。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from interview_matcher.common import resume_loader
from interview_matcher.common.llm_client import LLMClient
from interview_matcher.week2 import extract, prompts

RESULTS_PATH = Path(__file__).parent / "results.json"


def run_one(pdf_path: str, strategy: str, client: LLMClient) -> dict:
    raw = resume_loader.load_pdf_text(pdf_path)
    text = resume_loader.strip_pii(raw)
    resume = {"resume_id": Path(pdf_path).stem, "name": Path(pdf_path).stem, "resume_text": text}
    rec = extract.extract(strategy, resume, client=client)
    rec["oov_tags"] = extract.oov_tags(rec["pred"])
    print(f"\n===== {resume['resume_id']} [{strategy}] =====")
    print(f"脱敏文本长度：{len(text)}  解析成功：{rec['parse_ok']}  {rec['parse_error'] or ''}")
    for field, tags in rec["pred"].items():
        print(f"  {field}: {tags}")
    print(f"  OOV: {rec['oov_tags']}  用量: {rec['usage']}")
    return rec


def main() -> None:
    if len(sys.argv) < 2:
        print("用法：uv run w2-real <pdf...> [zero_shot|few_shot|cot]")
        sys.exit(1)

    args = sys.argv[1:]
    strategy: str | None = None
    if args[-1] in prompts.STRATEGIES:
        strategy = args.pop()
    pdf_paths = args
    strategies = [strategy] if strategy else list(prompts.STRATEGIES)

    client = LLMClient()
    records: list[dict] = []
    for pdf_path in pdf_paths:
        for one in strategies:
            records.append(run_one(pdf_path, one, client))

    RESULTS_PATH.write_text(
        json.dumps({"strategies": strategies, "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n明细已写入：{RESULTS_PATH}")


if __name__ == "__main__":
    main()
