#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""防重复台账查重、选题建议与文章集组织判定。

用法:
    python check-ledger.py --suggest                # 输出未覆盖且间隔达标的候选 + 间隔核查
    python check-ledger.py --check "生猪养殖"          # 检查某个标的能否写（返回退出码）
    python check-ledger.py --series "宠物医疗"         # 三源检索，输出已覆盖清单与 S4 分支判定
    python check-ledger.py --dump                   # 打印台账全部记录

退出码:
    0 = 可写 / 检测正常完成 / 1 = 不可写（重复或间隔未到）

三源检索（--series，对应 P0 的 S2）:
    ① 文章集总台账  references/ledger-analysis-topics.md   §文章集注册表
    ② 本集索引     产出/<行业>/_系列索引.md                  §篇目表 / §已覆盖清单
    ③ 实际产出目录  产出/<行业>/NN-<阶段>-<标题>／
"""

import argparse
import re
import sys
from pathlib import Path

LEDGER_REL = Path("references") / "ledger-analysis-topics.md"
TAXONOMY_REL = Path("references") / "research" / "01-industry-taxonomy.md"
OUTPUT_REL = Path("产出")
SERIES_INDEX_NAME = "_系列索引.md"

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


def _table_rows(text: str, section: str) -> list[list[str]]:
    """取某个 ## 段落下的表格数据行（跳过表头与分隔行）。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == section or line.strip().startswith(section):
            start = i + 1
            break
    if start is None:
        return []
    rows = []
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("## "):
            break
        if not s.startswith("|") or "---" in s:
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or cells[0] in ("序号", "大类", "行业（文章集）", "候选子方向 / 视角", "篇号", "日期", ""):
            continue
        rows.append(cells)
    return rows


def _bullet_items(text: str, section: str) -> list[str]:
    """取某个 ### 段落下的 '- ' 列表项（跳过模板占位）。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith(section):
            start = i + 1
            break
    if start is None:
        return []
    items = []
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("#"):
            break
        if s.startswith("- ") and "<" not in s:
            items.append(s[2:].strip())
    return items


def read_registry(industry: str) -> dict:
    """① 文章集总台账 §文章集注册表"""
    ledger = skill_root() / LEDGER_REL
    if not ledger.exists():
        return {"registered": False, "row": None}
    rows = _table_rows(ledger.read_text(encoding="utf-8"), "## 文章集注册表")
    for cells in rows:
        if cells and industry in cells[0]:
            return {"registered": True, "row": cells}
    return {"registered": False, "row": None}


def read_series_index(industry: str) -> dict:
    """② 本集索引 §篇目表 / §已覆盖清单"""
    idx = skill_root() / OUTPUT_REL / industry / SERIES_INDEX_NAME
    if not idx.exists():
        return {"exists": False, "articles": [], "covered": {}}
    text = idx.read_text(encoding="utf-8")
    articles = _table_rows(text, "## 篇目表")
    covered = {
        "子方向": _bullet_items(text, "### 已覆盖子方向"),
        "视角": _bullet_items(text, "### 已用切入视角"),
        "生活入口": _bullet_items(text, "### 已用生活入口"),
        "钩子类型": _bullet_items(text, "### 钩子类型分布"),
    }
    return {"exists": True, "articles": articles, "covered": covered}


def scan_output_dirs(industry: str) -> list[str]:
    """③ 实际产出目录"""
    base = skill_root() / OUTPUT_REL / industry
    if not base.exists():
        return []
    return sorted(
        p.name for p in base.iterdir()
        if p.is_dir() and re.match(r"[0-9]+-", p.name) and not p.name.startswith("存档")
    )


def cmd_series(industry: str) -> int:
    registry = read_registry(industry)
    index = read_series_index(industry)
    dirs = scan_output_dirs(industry)

    article_count = len(dirs) or len(index["articles"])
    has_research = registry["registered"] or index["exists"] or bool(dirs)

    print(f"【文章集组织判定】行业：{industry}")
    print(f"  ① 总台账注册表：{'已登记' if registry['registered'] else '未登记'}"
          + (f"（已收录 {registry['row'][3]} 篇）" if registry["row"] and len(registry["row"]) > 3 else ""))
    print(f"  ② 本集索引：{'存在' if index['exists'] else '不存在'}"
          + (f"（篇目表 {len(index['articles'])} 行）" if index["exists"] else ""))
    print(f"  ③ 实际产出目录：{len(dirs)} 个 → {' / '.join(dirs) if dirs else '无'}")
    print()

    if index["exists"]:
        covered = index["covered"]
        print("【已覆盖清单】")
        print(f"  子方向：{'；'.join(covered['子方向']) or '（索引未登记）'}")
        print(f"  视角 / 杠杆：{'；'.join(covered['视角']) or '（索引未登记）'}")
        print(f"  生活入口：{'；'.join(covered['生活入口']) or '（索引未登记）'}")
        print(f"  钩子类型：{'；'.join(covered['钩子类型']) or '（索引未登记）'}")
        print()
        if index["articles"]:
            print("【篇目与关系】")
            for cells in index["articles"]:
                no = cells[0] if cells else "?"
                sub = cells[2] if len(cells) > 2 else ""
                rel = cells[7] if len(cells) > 7 else ""
                print(f"  第 {no} 篇 | {sub} | 关系：{rel}")
            print()
    else:
        print("【已覆盖清单】索引缺失，须在 S1 补建并从产出目录回填。")
        print()

    print(f"【S2 判定】集内已收录篇数：{article_count} → {'已有研究' if has_research else '冷启动'}")
    print("【S4 分支】按 S3 的目标具体度二选一：")
    print("  目标具体     → S4-A 独立性检查（该子方向/视角是否在已覆盖清单里）")
    if has_research:
        print("  目标不具体   → S4-B 去重换视角：从已覆盖清单空白处选新子方向，并说明与已有篇的关系")
        print("                 已有研究，不走 S4-C，不重复开篇")
    else:
        print("  目标不具体   → S4-C 基础逻辑开篇：选最易理解且最关键的基础逻辑作为第 01 篇")
    print()
    print("【S5】默认由浅入深，内容价值优先；若递进会带偏方向，调整顺序或换主题。")
    print("【S6】完成后回写本集索引与本台账注册表。")
    return 0


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
    print("  1. 台账中完全未出现的二级标的（新建文章集，走 S4-C 冷启动）")
    print("  2. 已覆盖行业但换三级角度（集内以 _系列索引.md 已覆盖清单为准）")
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
    parser = argparse.ArgumentParser(description="防重复台账查重与文章集组织判定")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--suggest", action="store_true", help="给出选题建议")
    group.add_argument("--check", metavar="TARGET", help="检查某标的可否写")
    group.add_argument("--series", metavar="INDUSTRY", help="三源检索，输出文章集已覆盖清单与 S4 分支")
    group.add_argument("--dump", action="store_true", help="打印台账记录")
    args = parser.parse_args()

    if args.series:
        return cmd_series(args.series)
    rows = read_ledger()
    if args.suggest:
        return cmd_suggest(rows)
    if args.dump:
        return cmd_dump(rows)
    return cmd_check(args.check, rows)


if __name__ == "__main__":
    sys.exit(main())
