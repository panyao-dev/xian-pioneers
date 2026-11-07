from __future__ import annotations

import sys

from interview_matcher.common.llm_client import LLMClient

DEFAULT_QUESTION = "用两句话说明：给 Android 岗位匹配面试官，为什么要先看技术层级再看简历相似度？"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION

    client = LLMClient()
    print(f"[配置] base_url = {client.base_url}")
    print(f"[配置] model    = {client.model}")
    print(f"[配置] 模式     = {'DRY_RUN 本地模拟' if client.dry_run else '真实调用'}")
    print("-" * 60)
    print(f"[提问] {question}")

    result = client.chat(
        messages=[
            {"role": "system", "content": "你是一名 Android 技术招聘助手，回答简短直接。"},
            {"role": "user", "content": question},
        ]
    )

    print("[回答]")
    print(result["content"])
    print("-" * 60)
    print(
        "[用量] prompt={prompt_tokens} completion={completion_tokens} total={total_tokens}".format(
            **result["usage"]
        )
    )


if __name__ == "__main__":
    main()
