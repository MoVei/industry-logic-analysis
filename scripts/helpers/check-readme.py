#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check-readme.py — README 与产出目录的一致性检查

用法:
    python scripts/helpers/check-readme.py            # 在 skill 根目录外也能跑，自动定位根
    python scripts/helpers/check-readme.py --json
    python scripts/helpers/check-readme.py --root <skill 根>

检查项（任一失败即退出码 1）:
    C1  产出/<行业>/ 存在，但 README 没有任何链接指向该集（集未登记）
    C2  README 里出现指向 产出/ 的链接，但路径不存在（断链）
    C3  README 中某集的「已收录 N 篇」与目录实际篇数不符（篇数不符）
    C4  某集有正文类文件（正文.md / 切片 / 报告.md），但 README 未给出该篇的直达链接

口径:
    - 篇数只数 `NN-*` 形态的篇目目录，`存档-*` 不计入篇数（D24）
    - 正文类文件：正文.md、*切片*.md、*报告*.md
    - 集小节：README 中含该集「_系列索引.md」链接的一行标题（`###` 级）
"""

import json
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\]\((产出/[^)\s]+)\)")
COUNT_RE = re.compile(r"已收录\s*(\d+)\s*篇")
TITLE_RE = re.compile(r"^###\s+(.+)$", re.M)
BODY_NAMES = ("正文.md",)


def skill_root(explicit=None):
    if explicit:
        return Path(explicit).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "SKILL.md").exists() and (parent / "产出").exists():
            return parent
    return here.parents[2]


def body_file(entry_dir):
    for name in BODY_NAMES:
        p = entry_dir / name
        if p.exists():
            return p
    for p in sorted(entry_dir.glob("*.md")):
        if "切片" in p.name or "报告" in p.name:
            return p
    return None


def collect_series(root):
    out = []
    produce = root / "产出"
    if not produce.exists():
        return out
    for series in sorted(p for p in produce.iterdir() if p.is_dir()):
        entries = []
        archived = []
        for d in sorted(series.iterdir()):
            if not d.is_dir():
                continue
            if d.name.startswith("存档-"):
                archived.append(d)
            elif re.match(r"^\d{2}-", d.name):
                entries.append(d)
        out.append({"name": series.name, "dir": series, "entries": entries, "archived": archived})
    return out


def analyze(root):
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    links = LINK_RE.findall(readme)
    link_set = set(links)

    series_list = collect_series(root)
    problems = []
    summary = []

    # C2 断链
    for link in sorted(link_set):
        if not (root / link).exists():
            problems.append({"code": "C2", "msg": f"README 链接指向不存在的路径：{link}"})

    # C3 篇数
    counts = COUNT_RE.findall(readme)
    for s in series_list:
        idx = f"产出/{s['name']}/_系列索引.md"
        # 找到该集小节，取其中第一条「已收录 N 篇」
        if idx in readme:
            pos = readme.find(idx)
            line_start = readme.rfind("\n", 0, pos)
            line_end = readme.find("\n", pos)
            head = readme[line_start:line_end]
            m = COUNT_RE.search(head)
            declared = int(m.group(1)) if m else None
            actual = len(s["entries"])
            if declared is not None and declared != actual:
                problems.append({"code": "C3", "msg": f"{s['name']}：README 写「已收录 {declared} 篇」，目录实际 {actual} 篇"})
            summary.append({"series": s["name"], "declared": declared, "actual": actual})
        else:
            # C1 集未登记
            problems.append({"code": "C1", "msg": f"{s['name']}：产出目录存在，README 无该集小节（缺 _系列索引.md 链接）"})

    # C4 篇目直达
    for s in series_list:
        for d in s["entries"] + s["archived"]:
            bf = body_file(d)
            if not bf:
                continue
            rel = bf.relative_to(root).as_posix()
            if rel not in link_set:
                problems.append({"code": "C4", "msg": f"{s['name']}/{d.name}：正文文件未在 README 给出直达链接（{rel}）"})

    if counts and not series_list:
        problems.append({"code": "C1", "msg": "README 声明了已收录篇数，但 产出/ 下没有任何文章集目录"})

    return {"readme": str(readme_path), "series": summary, "problems": problems}


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}
    root = skill_root(args[0] if args else None)
    res = analyze(root)

    if "--json" in flags:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if not res["problems"] else 1

    print(f"\n== README 一致性检查：{root.name} ==")
    if res["series"]:
        print(f"   {'文章集':<12}{'README 声明':>10}{'目录实际':>10}")
        for s in res["series"]:
            print(f"   {s['series']:<12}{str(s['declared']):>10}{s['actual']:>10}")
    if not res["problems"]:
        print("\n   结论：一致（C1—C4 全部通过）\n")
        return 0

    print("\n   发现问题：")
    for p in res["problems"]:
        print(f"   [{p['code']}] {p['msg']}")
    print(f"\n   结论：不一致，共 {len(res['problems'])} 处。按 SKILL.md S6 第③项回写 README 后重跑。\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
