"""生成一份 90 天 × 3 区域的模拟用电数据（含注入的异常段）。"""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(20251118)
start = pd.Timestamp("2025-08-20")
days = 90
zones = {"宿舍A": (42, 6), "教学楼B": (88, 9), "机房C": (150, 14)}

rows = []
for i in range(days):
    d = start + pd.Timedelta(days=i)
    weekend = d.weekday() >= 5
    seasonal = 1 + 0.18 * np.sin(i / 12)          # 缓慢的季节波动
    for zone, (base, sd) in zones.items():
        factor = seasonal
        if zone in ("教学楼B", "机房C") and weekend:
            factor *= 0.45                         # 周末人少
        kwh = base * factor + rng.normal(0, sd)
        rows.append({"date": d.date().isoformat(), "zone": zone, "kwh": round(max(kwh, 1.0), 2)})

df = pd.DataFrame(rows)

# 注入两段异常：机房C 空调故障连续 4 天偏高；宿舍A 某周末几乎归零
mask = (df["zone"] == "机房C") & (df["date"].isin([(start + pd.Timedelta(days=k)).date().isoformat() for k in range(52, 56)]))
df.loc[mask, "kwh"] = (df.loc[mask, "kwh"] * 1.85).round(2)
mask2 = (df["zone"] == "宿舍A") & (df["date"].isin([(start + pd.Timedelta(days=k)).date().isoformat() for k in (66, 67)]))
df.loc[mask2, "kwh"] = 1.2

out = Path(__file__).resolve().parent / "data" / "energy.csv"
out.parent.mkdir(exist_ok=True)
df.to_csv(out, index=False, encoding="utf-8")
print(f"written {out} rows={len(df)}")
