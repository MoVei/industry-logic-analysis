#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""防重复台账查重与选题建议。

用法:
    python check-ledger.py --suggest           # 输出未覆盖且间隔达标的候选 + 间隔核查
    python check-ledger.py --check "生猪养殖"    # 检查某个标的能否写（返回退出码）
    python check-ledger.py --dump              # 打印台账全部记录

退出码:
    0 = 可写 / 1 = 不可写（重复或间隔未到）
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

LEDGER_REL = Path("references") / "ledger-analysis-topics.md"
TAXONOMY_REL = Path("references") / "research" / "01-industry-taxonomy.md"

# 与大类的映射仅用于给建议；真实判定以 Phase 0 现场归类为准
CLASS_KEYWORDS = {
    "A 资源/大宗": ["油", "煤", "气", "铜", "铝", "锂", "大豆", "玉米", "生猪", "小麦", "棉", "糖",
                    "铁矿", "稀土", "镍", "锌", "金", "银"],
    "B 中游材料": ["PTA", "乙二醇", "PVC", "钢铁", "水泥", "造纸", "化纤", "纯碱", "烧碱", "甲醇"],
    "C 消费品/零售": ["茶饮", "家电", "服装", "白酒", "餐饮", "啤酒", "乳品", "零食", "美妆", "家居"],
    "D 装备制造": ["工程机械", "挖掘机", "锂电设备", "光伏设备", "船舶", "轨交", "机器人", "机床"],
    "E 平台/服务": ["本地生活", "外卖", "OTA", "SaaS", "物流", "快递", "招聘", "网约车", "短剧"],
    "F 金融/地产": ["银行", "保险", "券商", "地产", "REITs", "信托", "租赁"],
    "G 科技/半导体": ["晶圆", "代工", "存储", "面板", "EDA", "芯片", "封测", "功率半导体", "MLCC"],
}


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def read_ledger() -> list[dict]:
    ledger = skill_root() / LEDGER_REL
    if not ledger.exists():
        return []
    rows = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 10 or cells[0] in ("大类", ""):
            continue
        try:
            issue = int(re.sub(r"\D", "", cells[2]) or 0)
        except ValueError:
            issue = 0
        rows.append(
            {
                "大类": cells[0],
                "标的": cells[1],
                "期号": issue,
                "生活入口": cells[3],
                "杠杆": cells[4],
            }
        )
    return rows


def suggest_class(name: str) -> str:
    for cls, kws in CLASS_KEYWORDS.items():
        if any(k in name for k in kws):
            return cls
    return "未识别（需人工归类）"


def cmd_suggest(rows: list[dict]) -> int:
    if not rows:
        print("台账为空，任何标的均可写。按下述五维逐项打分自选：")
        print("  数据可查性 → 生活可感性 → 机制独特性 → 新颖性 → 当期性")
        print("\n未覆盖大类（可作冷启动方向）：")
        for cls in CLASS_KEYWORDS:
            print(f"  - {cls}：{CLASS_KEYWORDS[cls][:5]}")
        return 0

    latest = max(r["期号"] for r in rows)
    print(f"台账已有 {len(rows)} 条，最新期号：第 {latest:02d} 期")
    print("\n【已覆盖标的与间隔核查】")
    for r in rows:
        gap = latest - r["期号"]
        l2_ok = gap >= 6
        flag = "✓ 二级可再分析" if l2_ok else f"✗ 还需 {6 - gap} 期"
        print(f"  {r['大类']:<12} {r['标的']:<16} 第{r['期号']:02d}期 间隔{gap:>2} {flag}")
        print(f"      杠杆：{r['杠杆']}")

    print("\n【建议】优先选择：")
    print("  1. 台账中完全未出现的二级标的")
    print("  2. 已覆盖行业但换三级角度（间隔 ≥12 期）")
    print("  3. 每篇的生活入口场景不得与历史记录重复")
    return 0


def cmd_check(target: str, rows: list[dict]) -> int:
    cls = suggest_class(target)
    print(f"标的：{target}\n推测大类：{cls}")

    exact = [r for r in rows if r["标的"] == target]
    if not exact:
        print("✓ 台账中未出现过该标的，可写（二级间隔检查通过）")
        print("提醒：若分析其同一根杠杆，需满足三级间隔 ≥12 期。")
        return 0

    latest = max(r["期号"] for r in rows)
    issues = "; ".join(f"第{r['期号']:02d}期（{r['杠杆']}）" for r in exact)
    print(f"✗ 该标的已有记录：{issues}")
    for r in exact:
        gap = latest - r["期号"]
        if gap < 6:
            print(f"  二级间隔不足：当前间隔 {gap} 期，需 ≥6，还需 {6 - gap} 期")
        elif gap < 12:
            print(f"  二级可写（间隔 {gap} 期），但三级角度需 ≥12 期，当前不足")
        else:
            print(f"  可再分析（间隔 {gap} 期），须换三级角度与生活入口")
    return 1


def cmd_dump(rows: list[dict]) -> int:
    if not rows:
        print("台账为空。")
        return 0
    for r in rows:
        print(f"第{r['期号']:02d}期 | {r['大类']} | {r['标的']} | {r['杠杆']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="防重复台账查重与选题建议")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--suggest", action="store_true", help="给出选题建议")
    group.add_argument("--check", metavar="TARGET", help="检查某标的可否写")
    group.add_argument("--dump", action="store_true", help="打印台账记录")
    args = parser.parse_args()

    rows = read_ledger()
    if args.suggest:
        return cmd_suggest(rows)
    if args.dump:
        return cmd_dump(rows)
    return cmd_check(args.check, rows)


if __name__ == "__main__":
    sys.exit(main())
