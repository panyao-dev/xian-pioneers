"""LLM 客户端封装：OpenAI 兼容网关。
环境变量（可写在 .env，也可直接 export / $env:）：
    LLM_BASE_URL  默认 http://221.131.102.69:18088/v1（GLM 网关，OpenAI 兼容）
    LLM_API_KEY   自己的 key
    LLM_MODEL     默认 glm-5.2
    DRY_RUN       1/true 时不请求网关，返回本地模拟响应（仅用于验证代码链路）
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_BASE_URL = "http://221.131.102.69:18088/v1"
DEFAULT_MODEL = "glm-5.2"


def _load_dotenv() -> None:
    """不引入第三方依赖的极简 .env 读取：从当前目录逐级向上找 .env。"""
    try:
        from pathlib import Path

        here = Path(__file__).resolve()
        for parent in [Path.cwd(), *here.parents]:
            env_file = parent / ".env"
            if env_file.is_file():
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
                return
    except OSError:
        return


_load_dotenv()


def is_dry_run() -> bool:
    return os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}


class LLMClient:
    """把 OpenAI SDK 收敛成 chat() 一个方法，返回统一结构。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL)
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.dry_run = is_dry_run() or not self.api_key
        self._client = None
        if not self.dry_run:
            from openai import OpenAI  # 延迟导入：DRY_RUN 时无需安装 openai

            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    # ------------------------------------------------------------------ #
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """返回 {"content": str, "tool_calls": [...], "usage": {...}}"""
        if self.dry_run:
            return self._fake_chat(messages, tools)

        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools or None,
            temperature=temperature,
        )
        choice = resp.choices[0].message
        tool_calls = [
            {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
            for tc in (choice.tool_calls or [])
        ]
        usage = resp.usage
        return {
            "content": choice.content or "",
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            },
        }

    # ------------------------------------------------------------------ #
    def _fake_chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        """DRY_RUN 模拟：只覆盖 W1 两个工具，输出一律带【DRY_RUN】前缀，避免被当成真实结果。"""
        zero = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = str(msg.get("content", ""))
                break

        tool_names = [t["function"]["name"] for t in (tools or [])]
        already_called = any(m.get("role") == "tool" for m in messages)

        if already_called:
            last_tool = ""
            for msg in reversed(messages):
                if msg.get("role") == "tool":
                    last_tool = str(msg.get("content", ""))
                    break
            try:
                payload = json.loads(last_tool)
            except json.JSONDecodeError:
                payload = {}
            if "interviewers" in payload:
                names = "、".join(
                    f"{i['name']}({i['interviewer_id']})" for i in payload["interviewers"]
                ) or "无"
                content = (
                    f"【DRY_RUN 模拟输出】当前可面试 {payload['total_available']} 人，"
                    f"命中 {payload['domain']} 方向 {payload['matched']} 人：{names}。"
                )
            elif "rounds" in payload:
                rounds = "；".join(f"第{r['round']}轮 {r['role']}" for r in payload["rounds"])
                content = (
                    f"【DRY_RUN 模拟输出】{payload['recruit_type']}共 "
                    f"{payload['round_count']} 轮：{rounds}。"
                )
            else:
                content = f"【DRY_RUN 模拟输出】工具返回：{last_tool[:120]}"
            return {"content": content, "tool_calls": [], "usage": zero}

        if tools:
            if "query_interviewer_pool" in tool_names and any(
                k in last_user for k in ("面试官", "池", "查")
            ):
                domain = "SystemUI" if "SystemUI" in last_user else "Linux内核"
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_fake_1",
                            "name": "query_interviewer_pool",
                            "arguments": json.dumps({"domain": domain}, ensure_ascii=False),
                        }
                    ],
                    "usage": zero,
                }
            if "get_interview_slot_rule" in tool_names and any(
                k in last_user for k in ("轮", "社招", "校招")
            ):
                recruit = "社招" if "社招" in last_user else "校招"
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_fake_2",
                            "name": "get_interview_slot_rule",
                            "arguments": json.dumps({"recruit_type": recruit}, ensure_ascii=False),
                        }
                    ],
                    "usage": zero,
                }

        return {
            "content": "【DRY_RUN 模拟输出】未配置 LLM_API_KEY，这是本地模拟回复；"
            "配好 key 后重跑即为真实模型输出。",
            "tool_calls": [],
            "usage": zero,
        }
