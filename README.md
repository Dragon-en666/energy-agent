# Energy Diagnostic Agent · 能耗异常诊断 Agent

> 给一份分区域用电数据表，Agent 会自己调用统计工具查异常、比对环比，
> 最后输出「结论 / 证据 / 建议」三段式报告。
> 重点不在调 API，而在于**把数据分析拆成模型可以安全调用的工具**。

## 架构

```
数据层    data/energy.csv（90 天 × 3 区域：date, zone, kwh）
             ↓  pandas 读入、校验列名
工具层    describe_stats / detect_outliers / compare_period   ← 纯函数、可单测
             ↓  每个函数配 JSON Schema
决策层    LLM + function calling 循环（最多 8 轮，异常回传给模型而不是崩溃）
             ↓
展示层    report.md（轨迹 + 结论）／ 命令行输出
```

## 快速开始

```bash
pip install -r requirements.txt

# 1) 离线验证整条链路（不需要 API key）
python -m src.main --dry-run --out report.md

# 2) 真实模型运行
cp .env.example .env      # 填入 OPENAI_API_KEY / OPENAI_BASE_URL
python -m src.main --out report.md
```

## 它跑出来是什么样

真实一次运行的结论（`report.md`）：

> 最近一个月没有真正意义上的「用电异常升高」。三个区域环比全部下降：
> 宿舍A -8.3%、教学楼B -3.3%、机房C -7.2%。
>
> 唯一需要核查的是数据异常：宿舍 A 在 10-25、10-26 连续两天只有 1.2 kWh（z = -4.0），
> 更像计量故障或抄表失败。机房 C 均值 133.21 kWh，占三个区域总均值的 53%，
> 节能优先投到机房 C。

## 三个工具

| 工具 | 作用 | 关键参数 |
| --- | --- | --- |
| `describe_stats` | 数据画像：样本量、时间范围、均值/中位数/极值、分区域均值 | `column` |
| `detect_outliers` | z 分数抓异常，**默认在区域内部算 z** | `column`, `z=2.5`, `limit`, `per_zone` |
| `compare_period` | 最近 N 天 vs 前 N 天的环比 | `period_days=30`, `column` |

> `per_zone=True` 的重要性：不同区域用电基准差 3 倍（宿舍 ~42 / 机房 ~150），
> 全局算 z 会把机房的高值误判成异常、也会把宿舍的低值掩盖掉。

## 示例数据

`make_demo_data.py` 用固定随机种子生成可复现数据，并**注入两段异常**：

- 机房 C 第 52–55 天 ×1.85（模拟空调故障连续漂移）
- 宿舍 A 第 66–67 天降到 1.2（模拟计量故障 / 空置）

```bash
python make_demo_data.py     # → data/energy.csv（270 行）
```

已知限制：连续 4 天的缓慢漂移在 `z=2.5` 的阈值法下**不一定被抓出来**（它介于日间噪声与
单点尖峰之间）。这正是下一步要换成滑动窗口 / EWMA 的原因，也是面试时最好的「我发现了
方法的边界」的素材。

## 目录

```
src/tools.py   工具函数 + TOOL_SCHEMAS（OpenAI function schema）
src/agent.py   SYSTEM_PROMPT + run_agent 循环
src/llm.py     client 构造 / DryRunClient / 模型名
src/report.py  轨迹落盘为 Markdown
src/main.py    argparse CLI
```

## 下一步

- [ ] 第 4 个工具 `trend_forecast`（移动平均 / 线性拟合）
- [ ] pytest：正常、缺列、空数据、极端值
- [ ] Streamlit 单页：上传 CSV → 提问 → 看轨迹
- [ ] 对比实验：z=2.5 vs 3.0、per_zone 开 vs 关

> 数据为模拟生成，不含任何真实单位信息。
