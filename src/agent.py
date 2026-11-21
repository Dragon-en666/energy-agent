"""Mini tool-calling agent loop."""
from __future__ import annotations

import json
from typing import Callable, List, Tuple

from .tools import TOOL_FUNCS, TOOL_SCHEMAS

SYSTEM_PROMPT = """你是一名建筑能耗诊断助手，可以调用工具分析 CSV 数据。

工作要求：
1. 先看清楚数据长什么样（样本量、区间、各区域均值），再下结论；
2. 至少调用两个不同的工具，用数字说话，禁止凭空猜测；
3. 数据不足以支撑结论时，直接说“数据不足以判断”，并说明还需要什么字段；
4. 最终用中文 Markdown 输出，固定三节：## 结论 / ## 证据 / ## 建议，每条建议都要对应一条证据。"""

MAX_TURNS = 8


def _to_message(msg) -> dict:
    """把 SDK 返回的 message 转成可以追加进 history 的 dict。"""
    if isinstance(msg, dict):
        return msg
    if hasattr(msg, "model_dump"):
        return msg.model_dump(exclude_none=True)
    return msg.dict(exclude_none=True)


def _call_tool(name: str, args: dict) -> dict:
    fn = TOOL_FUNCS.get(name)
    if fn is None:
        return {"error": f"未知工具 {name}"}
    try:
        return fn(**args)
    except TypeError as exc:
        return {"error": f"参数不对：{exc}"}
    except Exception as exc:  # 工具报错要回给模型，而不是让整个 agent 崩掉
        return {"error": f"{type(exc).__name__}: {exc}"}


def run_agent(
    question: str,
    client,
    model: str,
    max_turns: int = MAX_TURNS,
    trace: Callable[[str], None] = print,
) -> Tuple[str, List[dict]]:
    messages: List[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    for turn in range(1, max_turns + 1):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto"
        )
        msg = resp.choices[0].message
        messages.append(_to_message(msg))
        calls = getattr(msg, "tool_calls", None) or []
        if not calls:
            return (msg.content or ""), messages
        for call in calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            trace(f"[turn {turn}] -> {name}({json.dumps(args, ensure_ascii=False)})")
            result = _call_tool(name, args)
            trace(f"[turn {turn}] <- {json.dumps(result, ensure_ascii=False)[:160]}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    return "（已经达到最大轮数，仍未得到最终回答）", messages
