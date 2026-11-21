"""LLM 客户端：真实调用 + 不需要 API key 的 dry-run 假客户端。"""
from __future__ import annotations

import os
from types import SimpleNamespace


class LLMError(RuntimeError):
    pass


def model_name() -> str:
    return os.getenv("OPENAI_MODEL", "deepseek-chat")


def make_client():
    """任何兼容 OpenAI 协议的服务都能用：改 OPENAI_BASE_URL 即可。"""
    try:  # .env 里有配置就自动读进来
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise LLMError("没装 openai 包，先执行：pip install -r requirements.txt") from exc
    key = os.getenv("OPENAI_API_KEY")
    base = os.getenv("OPENAI_BASE_URL")
    if not key:
        raise LLMError("没有找到 OPENAI_API_KEY，请写进 .env 或直接设置环境变量")
    return OpenAI(api_key=key, base_url=base) if base else OpenAI(api_key=key)


# ---------------- dry-run：不需要网络，验证循环与工具是否接通 ----------------
class _Fn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _Call:
    def __init__(self, idx, name, args):
        self.id = f"call_{idx}"
        self.type = "function"
        self.function = _Fn(name, args)


class _Msg:
    def __init__(self, content=None, calls=None):
        self.content = content
        self.tool_calls = calls or None

    def model_dump(self, exclude_none: bool = False):
        data = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.function.name, "arguments": c.function.arguments},
                }
                for c in self.tool_calls
            ]
        return data


_DRY_ANSWER = """## 结论
（dry-run 输出，真实运行由模型根据工具结果生成）

## 证据
见上方工具调用轨迹：describe_stats / detect_outliers / compare_period 均已成功返回。

## 建议
把 OPENAI_API_KEY 配好，再跑一次 `python -m src.main --out report.md`，得到真正的诊断报告。"""


class DryRunClient:
    """按预设脚本走三轮：两个工具调用 + 一个最终回答。"""

    def __init__(self):
        script = [
            lambda: _Msg(calls=[_Call(1, "describe_stats", '{"column": "kwh"}')]),
            lambda: _Msg(calls=[_Call(2, "detect_outliers", '{"column": "kwh", "z": 2.5}')]),
            lambda: _Msg(calls=[_Call(3, "compare_period", '{"period_days": 30}')]),
            lambda: _Msg(content=_DRY_ANSWER),
        ]
        state = {"n": 0}

        def create(**_kwargs):
            step = script[min(state["n"], len(script) - 1)]
            state["n"] += 1
            return SimpleNamespace(choices=[SimpleNamespace(message=step())])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
