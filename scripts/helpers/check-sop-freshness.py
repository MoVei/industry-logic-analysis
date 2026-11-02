#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SOP 时效与反例检查。

复用已沉淀 SOP 前必须执行（Phase 6 的强制检查）。

用法:
    python check-sop-freshness.py --all              # 检查全部 SOP
    python check-sop-freshness.py --file xxx.md      # 检查单个文件

退出码:
    0 = 全部可用 / 1 = 存在超期或未决反例
"""

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

PLAYBOOKS_REL = Path("references") / "domain-playbooks"

# 超过阈值必须重新取数，不许沿用旧读数
FRESHNESS_LIMIT_DAYS = {"月": 45, "季": 105, "年": 400, "week": 7}
DEFAULT_LIMIT_DAYS = 45

REVERSE_FLAG = "新反例"


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def parse_meta(text: str) -> dict:
    meta = {"last_verified": None, "定级": None}
    m = re.search(r"last_verified\s*\|\s*([0-9\-]{8,10})", text)
    if m:
        meta["last_verified"] = m.group(1)
    m = re.search(r"定级\s*\|\s*(Draft|Verified|Authoritative)", text, re.I)
    if m:
        meta["定级"] = m.group(1)
    return meta


def has_open_counterexample(text: str) -> bool:
    """检查验证履历表是否存在未决反例。"""
    for line in text.splitlines():
        if line.startswith("|") and REVERSE_FLAG in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[0].count("-") >= 2:
                verdict = cells[3]
                if verdict and verdict not in ("无", "—", "-", ""):
                    return True
    return False


def infer_frequency(text: str) -> tuple[str, int]:
    """从数据清单的频率列推断主导更新频率，取出现最多的一种。"""
    freqs = re.findall(r"\|\s*(周|月|季|年)\s*\|", text)
    if not freqs:
        return "未识别", DEFAULT_LIMIT_DAYS
    top = max(set(freqs), key=freqs.count)
    return top, FRESHNESS_LIMIT_DAYS.get(top, DEFAULT_LIMIT_DAYS)


def check_file(path: Path) -> tuple[bool, list[str]]:
    text = path.read_text(encoding="utf-8")
    meta = parse_meta(text)
    msgs = []
    ok = True

    if not meta["last_verified"]:
        msgs.append("未找到 last_verified，按不合格处理")
        ok = False
    else:
        try:
            lv = datetime.strptime(meta["last_verified"][:10], "%Y-%m-%d").date()
        except ValueError:
            msgs.append(f"last_verified 格式异常：{meta['last_verified']}")
            return False, msgs
        age = (date.today() - lv).days
        freq, limit = infer_frequency(text)
        if age > limit:
            msgs.append(
                f"超期：距上次核验 {age} 天，主导频率「{freq}」阈值 {limit} 天 → 必须重新取数"
            )
            ok = False
        else:
            msgs.append(f"时效通过：{age} 天（阈值 {limit} 天，频率 {freq}）")

    if has_open_counterexample(text):
        msgs.append("存在未决反例 → 降为 Draft，产出中须明示该 SOP 当前不可靠")
        ok = False

    level = meta["定级"] or "未标注"
    msgs.append(f"当前定级：{level}")
    if level and level.lower() == "draft":
        msgs.append("Draft 使用时必须标注「未经滚动验证」")

    return ok, msgs


def main() -> int:
    parser = argparse.ArgumentParser(description="SOP 时效与反例检查")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="检查全部 SOP")
    group.add_argument("--file", help="检查单个 SOP 文件")
    args = parser.parse_args()

    pb = skill_root() / PLAYBOOKS_REL
    if not pb.exists():
        print(f"[error] 未找到目录：{pb}")
        return 1

    targets = []
    if args.all:
        targets = sorted(
            p for p in pb.glob("*.md") if p.name not in ("README.md", "_template.md")
        )
        if not targets:
            print("尚无已沉淀的 SOP。每份 SOP 均须现场取证后方可沉淀。")
            return 0
    else:
        p = pb / args.file
        if not p.exists():
            print(f"[error] 文件不存在：{p}")
            return 1
        targets = [p]

    all_ok = True
    for p in targets:
        ok, msgs = check_file(p)
        all_ok &= ok
        print(f"\n=== {p.name} ===")
        print("  " + ("✓ 可复用" if ok else "✗ 不可直接复用"))
        for m in msgs:
            print(f"  - {m}")

    print("\n" + ("全部通过。" if all_ok else "存在不可直接复用的 SOP，须按上述处理。"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
