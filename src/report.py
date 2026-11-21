"""把一次 agent 运行落成一份 Markdown 报告。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _short(obj, n=600) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=2) if not isinstance(obj, str) else obj
    return text if len(text) <= n else text[:n] + " …"


def save_report(path, question: str, messages, answer: str) -> Path:
    out = Path(path)
    lines = [
        "# 能耗诊断 Agent 报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 问题：{question}",
        "",
        "## 工具调用轨迹",
        "",
    ]
    step = 0
    for msg in messages:
        if msg.get("role") == "tool":
            step += 1
            lines += [f"### 调用 {step}", "", "```json", _short(msg.get("content", "")), "```", ""]
    lines += ["## 最终回答", "", answer or "（空）", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
