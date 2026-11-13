# 面试官匹配 Agent（Agent Lab 作业工程）

用真实业务——Android 岗位面试官匹配——作为学习营 8 周作业的主线
## 入口命令

| 命令 | 对应模块 | 说明 |
|---|---|---|
| `uv run w1-hello` | `interview_matcher.week1.hello` | 单轮调通，输出 token 用量 |
| `uv run w1-tool-call` | `interview_matcher.week1.tool_call` | 工具调用闭环，可带自定义问题 |
| `uv run w2-real <pdf...>` | `interview_matcher.week2.real_resume_demo` | 真实简历 PDF 脱敏后，按 zero/few-shot/CoT 三策略抽取标签 |

带参数示例：`uv run w1-tool-call "社招一般安排几轮面试？"`

## 依赖管理

```powershell
uv add requests        # 加依赖：自动写入 pyproject.toml 并同步 .venv
uv remove requests     # 删依赖
uv sync                # 按 lock 文件还原环境
uv run <命令>           # 在项目环境里执行，无需手动激活 venv
```

## 运行环境

- uv 0.13.7 + Python 3.12（`.python-version` 指定）
- 依赖只有 `openai`（DRY_RUN 模式下连它都不需要）
- PyPI 源已在 `pyproject.toml` 里配成阿里云镜像

> 说明：这里用 `openai` SDK 只是因为 GLM 网关是 **OpenAI 兼容协议**，客户端代码通用；
> 实际请求的模型是 `glm-5.2`，不走 OpenAI 官方服务。
