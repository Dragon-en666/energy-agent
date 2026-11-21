"""命令行入口：python -m src.main --question "..." [--dry-run] [--out report.md]"""
from __future__ import annotations

import argparse
import sys

from .agent import run_agent
from .llm import DryRunClient, LLMError, make_client, model_name
from .report import save_report
from .tools import data_path, set_data_path

DEFAULT_Q = (
    "这是某栋楼 90 天的分区域用电数据（kwh）。"
    "请判断最近一个月哪些区域用电异常、整体趋势如何，并给出 3 条可执行的节能建议。"
)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="能耗诊断 Agent")
    p.add_argument("--question", "-q", default=DEFAULT_Q)
    p.add_argument("--data", "-d", default=None, help="CSV 路径，默认 data/energy.csv")
    p.add_argument("--out", "-o", default=None, help="把结果写成 Markdown 报告")
    p.add_argument("--dry-run", action="store_true", help="不联网，用脚本化的假模型验证循环")
    p.add_argument("--quiet", action="store_true", help="不打印工具调用过程")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.data:
        set_data_path(args.data)
    trace = (lambda _msg: None) if args.quiet else print

    try:
        client = DryRunClient() if args.dry_run else make_client()
        model = "dry-run" if args.dry_run else model_name()
    except LLMError as exc:
        print(f"[配置问题] {exc}", file=sys.stderr)
        return 2

    print(f"[数据] {data_path()}")
    answer, messages = run_agent(args.question, client=client, model=model, trace=trace)
    print("\n" + "=" * 60 + "\n" + answer.strip() + "\n" + "=" * 60)
    if args.out:
        saved = save_report(args.out, args.question, messages, answer)
        print(f"[报告] {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
