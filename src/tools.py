"""能耗诊断 Agent 的 3 个工具（不需要 LLM 也能单独测试）。"""
from pathlib import Path

import numpy as np
import pandas as pd

_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "energy.csv"
_DATA_PATH = _DEFAULT


def set_data_path(path):
    global _DATA_PATH
    _DATA_PATH = Path(path)


def data_path():
    return _DATA_PATH


def _load():
    df = pd.read_csv(_DATA_PATH, parse_dates=["date"])
    df = df.sort_values(["date", "zone"]).reset_index(drop=True)
    return df


def describe_stats(column: str = "kwh") -> dict:
    """数据整体画像：样本量、区间、均值、按区域的均值。"""
    df = _load()
    if column not in df.columns:
        return {"error": f"列 {column} 不存在，可选：{list(df.columns)}"}
    s = pd.to_numeric(df[column], errors="coerce").dropna()
    by_zone = (
        df.groupby("zone")[column].mean().round(2).to_dict()
        if "zone" in df.columns
        else {}
    )
    return {
        "column": column,
        "count": int(s.shape[0]),
        "start": str(df["date"].min().date()),
        "end": str(df["date"].max().date()),
        "mean": round(float(s.mean()), 2),
        "median": round(float(s.median()), 2),
        "min": round(float(s.min()), 2),
        "max": round(float(s.max()), 2),
        "std": round(float(s.std()), 2),
        "mean_by_zone": by_zone,
    }


def detect_outliers(column: str = "kwh", z: float = 2.5, limit: int = 10, per_zone: bool = True) -> dict:
    """按 z 分数抓异常点。默认在每个区域内部算 z，避免不同区域基准不同导致漏检。"""
    df = _load()
    if column not in df.columns:
        return {"error": f"列 {column} 不存在"}
    df = df.copy()
    if per_zone and "zone" in df.columns:
        grp = df.groupby("zone")[column]
        df["z"] = (df[column] - grp.transform("mean")) / grp.transform("std")
    else:
        df["z"] = (df[column] - df[column].mean()) / df[column].std(ddof=0)
    df["z"] = df["z"].replace([np.inf, -np.inf], np.nan)
    hit = df[df["z"].abs() >= float(z)].copy()
    hit = hit.reindex(hit["z"].abs().sort_values(ascending=False).index).head(int(limit))
    rows = [
        {
            "date": str(r["date"].date()),
            "zone": r.get("zone", ""),
            column: round(float(r[column]), 2),
            "z": round(float(r["z"]), 2),
        }
        for _, r in hit.iterrows()
    ]
    return {
        "column": column,
        "z_threshold": float(z),
        "per_zone": bool(per_zone),
        "outlier_count": int(len(hit)),
        "top_outliers": rows,
    }


def compare_period(period_days: int = 30, column: str = "kwh") -> dict:
    """最近 N 天 vs 前 N 天，按区域环比。"""
    df = _load()
    if column not in df.columns:
        return {"error": f"列 {column} 不存在"}
    end = df["date"].max()
    split = end - pd.Timedelta(days=int(period_days))
    last = df[df["date"] > split]
    prev = df[df["date"] <= split]
    if prev.empty:
        return {"error": "历史区间为空，把 period_days 调小一点"}
    cur = last.groupby("zone")[column].mean()
    old = prev.groupby("zone")[column].mean()
    change = ((cur - old) / old * 100).round(1)
    return {
        "column": column,
        "period_days": int(period_days),
        "last_period_mean": cur.round(2).to_dict(),
        "previous_period_mean": old.round(2).to_dict(),
        "change_pct": change.to_dict(),
    }


def trend_forecast(column: str = "kwh", days: int = 7, window: int = 7) -> dict:
    """用最近 window 天的移动平均 + 线性斜率，外推未来 days 天的分区域用电。"""
    df = _load()
    if column not in df.columns:
        return {"error": f"列 {column} 不存在"}
    window = max(int(window), 2)
    days = max(int(days), 1)
    out = {}
    for zone, g in df.groupby("zone"):
        s = pd.to_numeric(g[column], errors="coerce").dropna().tail(window)
        if s.empty:
            continue
        recent = float(s.mean())
        if len(s) >= 3:
            slope = float(np.polyfit(np.arange(len(s)), s.to_numpy(), 1)[0])
        else:
            slope = 0.0
        out[zone] = {
            "recent_mean": round(recent, 2),
            "daily_slope": round(slope, 2),
            "forecast_next_days": [round(recent + slope * (i + 1), 2) for i in range(days)],
        }
    if not out:
        return {"error": "数据不足，无法预测"}
    return {"column": column, "window_days": window, "forecast_days": days, "by_zone": out}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "describe_stats",
            "description": "查看数据概况：样本量、时间区间、均值中位数、各区域均值。分析前先调用它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string", "description": "要统计的列名，默认 kwh"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_outliers",
            "description": "用 z 分数找出异常读数，返回最极端的若干条记录。默认在每个区域内部计算 z。",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string", "description": "列名，默认 kwh"},
                    "z": {"type": "number", "description": "阈值，默认 2.5，越大越严格"},
                    "limit": {"type": "integer", "description": "最多返回多少条，默认 10"},
                    "per_zone": {"type": "boolean", "description": "是否按区域分别计算 z，默认 true"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_period",
            "description": "比较最近 N 天与之前 N 天各区域均值的环比变化，用于判断趋势。",
            "parameters": {
                "type": "object",
                "properties": {
                    "period_days": {"type": "integer", "description": "对比窗口天数，默认 30"},
                    "column": {"type": "string", "description": "列名，默认 kwh"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trend_forecast",
            "description": "用最近 window 天的移动平均加线性斜率，外推未来 days 天各区域的用电量。",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string", "description": "列名，默认 kwh"},
                    "days": {"type": "integer", "description": "预测未来多少天，默认 7"},
                    "window": {"type": "integer", "description": "用最近多少天做基准，默认 7"},
                },
            },
        },
    },
]

TOOL_FUNCS = {
    "describe_stats": describe_stats,
    "detect_outliers": detect_outliers,
    "compare_period": compare_period,
    "trend_forecast": trend_forecast,
}
