#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""防重复台账查重、选题建议与文章集组织判定。

用法:
    python check-ledger.py --suggest                # 输出未覆盖且间隔达标的候选 + 间隔核查
    python check-ledger.py --check "生猪养殖"          # 检查某个标的能否写（返回退出码）
    python check-ledger.py --series "宠物医疗"         # 三源检索 + 索引收口检查，输出已覆盖清单与 S4 分支
    python check-ledger.py --dump                   # 打印台账全部记录

退出码:
    0 = 可写 / 检测通过
    1 = 不可写（--check：重复或间隔未到）
    2 = 索引收口检查不通过（--series：S1—S5 任一失败）

三源检索（--series，对应 P0 的 S2）:
    ① 文章集总台账  references/ledger-analysis-topics.md   §文章集注册表
    ② 本集索引     产出/<行业>/_系列索引.md                  §篇目表 / §已覆盖清单
    ③ 实际产出目录  产出/<行业>/NN-<阶段>-<标题>／

索引收口检查（--series 附带，对应 S6 的「索引未回写视为未完成」）:
    S1 三节（子方向 / 视角 / 生活入口）内容不得两两相同
    S2 任一节内不得出现重复条目
    S3 篇目表与已覆盖清单不得残留「待回填」等占位或 <模板> 占位
    S4 索引须存在且篇目表非空（磁盘已有篇目目录时）
    S5 篇目表登记的目录须存在于磁盘，磁盘上的篇目目录须已入表
    说明：钩子类型是分布表（A/B/C 计数），不参与 S1 比对；
          S3 只扫篇目表单元格与四节条目，不扫正文叙述与维护记录里的历史引用。
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


ROOT_OVERRIDE = None  # 由 --root 设置为 Path；None 表示用脚本所在位置


def skill_root() -> Path:
    """默认取本脚本所在 skill 根目录；--root 可指向测试夹具，便于回归。"""
    if ROOT_OVERRIDE is not None:
        return ROOT_OVERRIDE
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


# ---------------------------- 索引收口检查（S1—S5） ---------------------------

INDEX_SECTIONS = ("子方向", "视角", "生活入口")
INDEX_ALL_SECTIONS = ("子方向", "视角", "生活入口", "钩子类型")
SECTION_LABEL = {
    "子方向": "已覆盖子方向",
    "视角": "已用切入视角",
    "生活入口": "已用生活入口",
    "钩子类型": "钩子类型分布",
}
# 占位词：S6 收口时不应留在篇目表或已覆盖清单里
PLACEHOLDER_RE = re.compile(r"待回填|待成稿|待补|TBD|TODO|<[\u4e00-\u9fa5A-Za-z_]{1,12}>")


def _norm_item(text: str) -> str:
    """条目归一：压缩空白，用于判定重复。"""
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_dir(cell: str) -> bool:
    """篇目表第 2 列是否是一个目录名（而非「—」「待定」这类自由文本）。"""
    c = cell.strip().strip("`").rstrip("/")
    return bool(c) and (c.startswith("存档-") or re.match(r"^\d+-", c) is not None)


def _clip(text: str, width: int = 26) -> str:
    t = _norm_item(text)
    return t if len(t) <= width else t[:width] + "…"


def index_checks(industry: str, index: dict, dirs: list[str]) -> list[dict]:
    """S1—S5：索引本身的收口质量与三源一致性。返回 [{code, name, ok, detail}]。"""
    results: list[dict] = []

    def add(code: str, name: str, ok: bool, detail: str) -> None:
        results.append({"code": code, "name": name, "ok": ok, "detail": detail})

    base = skill_root() / OUTPUT_REL / industry
    covered = index.get("covered", {})
    articles = index.get("articles", [])

    if not index["exists"]:
        skip = "索引缺失，跳过"
        add("S1", "三节内容不得两两相同", True, skip)
        add("S2", "节内不得重复条目", True, skip)
        add("S3", "不得残留占位", True, skip)
        if dirs:
            add("S4", "索引存在且篇目表非空", False,
                f"索引缺失，但磁盘已有 {len(dirs)} 个篇目目录 → 须在 S1 补建并从目录回填")
        else:
            add("S4", "索引存在且篇目表非空", True, "无索引且无篇目目录：冷启动，由 S1 建骨架")
        add("S5", "篇目表目录与磁盘一致", True, skip)
        return results

    # S1 三节两两相同
    sets = {k: {_norm_item(x) for x in covered.get(k, []) if _norm_item(x)} for k in INDEX_SECTIONS}
    same = [f"{a}＝{b}" for i, a in enumerate(INDEX_SECTIONS)
            for b in INDEX_SECTIONS[i + 1:] if sets[a] and sets[a] == sets[b]]
    add("S1", "三节内容不得两两相同", not same,
        "；".join(same) + "（三节被填成同一串）" if same else "三节各自独立")

    # S2 节内重复
    dup_detail = []
    for k in INDEX_ALL_SECTIONS:
        items = [_norm_item(x) for x in covered.get(k, []) if _norm_item(x)]
        seen, dup = set(), []
        for it in items:
            if it in seen and it not in dup:
                dup.append(it)
            seen.add(it)
        if dup:
            dup_detail.append(f"{SECTION_LABEL[k]} 重复 {len(dup)} 条：" + "／".join(_clip(d) for d in dup))
    add("S2", "节内不得重复条目", not dup_detail, "；".join(dup_detail) or "无重复")

    # S3 占位残留（只扫篇目表单元格与四节条目）
    scope: list[str] = []
    for cells in articles:
        scope.extend(cells)
    for k in INDEX_ALL_SECTIONS:
        scope.extend(covered.get(k, []))
    hits = [t for t in scope if PLACEHOLDER_RE.search(t)]
    add("S3", "不得残留占位", not hits,
        f"{len(hits)} 处：" + "／".join(_clip(h, 22) for h in hits[:3]) if hits else "无占位")

    # S4 索引与篇目表非空
    if not articles and dirs:
        add("S4", "索引存在且篇目表非空", False,
            f"篇目表 0 行，但磁盘已有 {len(dirs)} 个篇目目录")
    elif not articles:
        add("S4", "索引存在且篇目表非空", True, "空文章集（尚未登记篇目）")
    else:
        add("S4", "索引存在且篇目表非空", True, f"篇目表 {len(articles)} 行")

    # S5 篇目表 ↔ 磁盘
    listed = [cells[1].strip().strip("`").rstrip("/") for cells in articles
              if len(cells) > 1 and _looks_like_dir(cells[1])]
    missing = [x for x in listed if not (base / x).is_dir()]
    unlisted = [x for x in dirs if x not in listed]
    if missing or unlisted:
        parts = []
        if missing:
            parts.append("表中有、盘上无：" + "／".join(missing))
        if unlisted:
            parts.append("盘上有、表中无：" + "／".join(unlisted))
        add("S5", "篇目表目录与磁盘一致", False, "；".join(parts))
    else:
        add("S5", "篇目表目录与磁盘一致", True, f"{len(listed)} 个目录双向对得上")

    return results


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

    checks = index_checks(industry, index, dirs)
    failed = [c for c in checks if not c["ok"]]
    print("【索引收口检查】")
    for c in checks:
        print(f"  {c['code']} {c['name']}：{'✅' if c['ok'] else '❌'} {c['detail']}")
    print(f"  → {'通过' if not failed else f'不通过（{len(failed)} 项），S6 判未完成，不得进入 P1'}")
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
    print("【S6】完成后三处回写：① 本集索引 _系列索引.md ② 总台账注册表 ③ README 产出直达。")
    print("     收尾须两个检查同时为 0：check-readme.py（C1—C4）与本命令（S1—S5）。")
    return 2 if failed else 0


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
    parser.add_argument("--root", metavar="DIR", help="skill 根目录（默认取脚本位置；测试夹具用）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--suggest", action="store_true", help="给出选题建议")
    group.add_argument("--check", metavar="TARGET", help="检查某标的可否写")
    group.add_argument("--series", metavar="INDUSTRY",
                       help="三源检索 + 索引收口检查（S1—S5），输出已覆盖清单与 S4 分支；不通过退出码 2")
    group.add_argument("--dump", action="store_true", help="打印台账记录")
    args = parser.parse_args()

    global ROOT_OVERRIDE
    if args.root:
        ROOT_OVERRIDE = Path(args.root).expanduser().resolve()

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
