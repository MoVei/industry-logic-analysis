#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
readability-check.py — 面向外行的可读性体检

用法:
    python readability-check.py <正文.md> [<正文.md> ...]
    python readability-check.py 产出/碳酸锂/02-展开-*/正文.md
    python readability-check.py --dir 产出/宠物医疗
    python readability-check.py --json <正文.md>

门槛定义见 references/research/08-readability-laypeople.md §7（R1—R11）。

统计口径（与规范文件一致，改动须同步两处）:
    1. 正文起点：文件里第一个以 "## " 开头的行；之前的内容不计。
    2. 段落：空行分隔的文本块，排除以 | # > - * 数字. 开头的行（表格、标题、旁白、列表）。
    3. 句子：按 。！？ 切分，长度 ≤8 字的碎片丢弃。
    4. 字数：去掉所有空白字符后的字符数。
    5. 括注：成对的中英文括号，内容 1—200 字。
    6. 编号：正文里出现的 D123 / C45 形态（≥2 位数字）。
    7. 四类标签：【事实】【推演】【披露】【管理层口径】等方括号标记。
    8. 旁白：正文里以 "> " 开头的行。
    9. 数字：连续数字串（含小数、千分位），每个串计 1 次。

退出码:
    0  通过（一票否决项全过，且超线条数 ≤3）
    1  未通过
    2  用法错误
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 门槛定义
# (键, 显示名, 门槛值, 比较方向, 是否一票否决, 依据)
THRESHOLDS = [
    ("para_median",  "段落长度中位数(字)",        90,  "<=", False, "常识 40—69"),
    ("single_para",  "单句成段占比(%)",           30,  ">=", False, "常识 47—63"),
    ("sent_mean",    "平均句长(字)",              55,  "<=", False, "常识 37—46"),
    ("sent_long",    "超60字句占比(%)",           35,  "<=", False, "常识 17—25"),
    ("paren_multi",  "多括注段落占比(%)",         25,  "<=", False, "常识 8—22"),
    ("body_code",    "正文底稿编号(处)",           0,  "==", True,  "常识 0"),
    ("body_tag",     "四类内容标签(处)",           0,  "==", True,  "常识 0"),
    ("aside_per_1k", "旁白密度(处/千字)",        0.6,  ">=", False, "常识 0.7—1.4"),
    ("ask",          "设问个数(个)",               2,  ">=", False, "常识 2—11"),
    ("lead_digits",  "开篇前700字数字个数",        24,  "<=", False, "常识 16—24"),
    ("first_table",  "第一张表位置(字)",          600,  ">=", False, "常识 776+"),
]

CODE_RE = re.compile(r"(?<![A-Za-z0-9])[DC]\d{2,}")
TAG_RE = re.compile(r"【[^】]{1,12}】")
NUM_RE = re.compile(r"\d+(?:[,，]\d{3})*(?:\.\d+)?")
PAREN_RE = re.compile(r"[（(][^（()）]{1,200}[）)]")


def split_body(text):
    m = re.search(r"^## ", text, flags=re.M)
    return text[m.start():] if m else text


def iter_paragraphs(body):
    blocks = re.split(r"\n\s*\n", body)
    for b in blocks:
        lines = [ln.strip() for ln in b.strip().split("\n") if ln.strip()]
        if not lines:
            continue
        if any(ln.startswith(("|", "#", ">", "- ", "* ", "---")) for ln in lines):
            continue
        if re.match(r"^\d+[.、]", lines[0]):
            continue
        yield " ".join(lines)


def sentences(para):
    return [s.strip() for s in re.split(r"(?<=[。！？])", para) if len(s.strip()) > 8]


def char_len(s):
    return len(re.sub(r"\s", "", s))


def analyze(path):
    text = Path(path).read_text(encoding="utf-8")
    body = split_body(text)
    body_chars = max(char_len(body), 1)

    paras = list(iter_paragraphs(body))
    para_lens = [char_len(p) for p in paras]
    para_lens_sorted = sorted(para_lens)
    n_para = len(para_lens_sorted) or 1
    median = (para_lens_sorted[n_para // 2] if n_para % 2
              else (para_lens_sorted[n_para // 2 - 1] + para_lens_sorted[n_para // 2]) / 2)

    single = 0
    multi_paren = 0
    all_sents = []
    for p in paras:
        ss = sentences(p)
        if len(ss) == 1:
            single += 1
        all_sents.extend(ss)
        if len(PAREN_RE.findall(p)) >= 2:
            multi_paren += 1

    sent_lens = [char_len(s) for s in all_sents]
    sent_mean = sum(sent_lens) / max(len(sent_lens), 1)
    sent_long = 100.0 * sum(1 for x in sent_lens if x > 60) / max(len(sent_lens), 1)

    lines = body.split("\n")
    aside_lines = [ln for ln in lines if ln.strip().startswith(">")]
    # 引用块里的连续行按 1 处计
    aside_blocks = 0
    prev_aside = False
    for ln in lines:
        cur = ln.strip().startswith(">")
        if cur and not prev_aside:
            aside_blocks += 1
        prev_aside = cur

    sections = [s for s in re.split(r"^## ", body, flags=re.M)[1:]]
    asks_total = sum(s.count("？") for s in sections) or body.count("？")
    asks_per_section = min((s.count("？") for s in sections), default=0)

    head700 = "\n".join(ln for ln in lines if not ln.strip().startswith("|"))[:700]
    lead_digits = len(NUM_RE.findall(head700))

    # 第一张表：跳过篇首元信息表（正文第一段散文之前的表），取散文开始后的第一张表
    table_pos = None
    seen_prose = False
    consumed = 0
    for ln in lines:
        s = ln.strip()
        if s.startswith("|"):
            if seen_prose:
                table_pos = consumed
                break
        elif s and not s.startswith(("#", ">")):
            seen_prose = True
        consumed += char_len(ln)

    codes = CODE_RE.findall(body)
    tags = TAG_RE.findall(body)

    m = {
        "file": str(path),
        "chars": body_chars,
        "paras": len(paras),
        "para_median": int(median),
        "single_para": round(100.0 * single / max(len(paras), 1), 1),
        "sent_mean": round(sent_mean, 1),
        "sent_long": round(sent_long, 1),
        "paren_multi": round(100.0 * multi_paren / max(len(paras), 1), 1),
        "body_code": len(codes),
        "body_code_samples": codes[:6],
        "body_tag": len(tags),
        "body_tag_samples": tags[:6],
        "aside": aside_blocks,
        "aside_per_1k": round(1000.0 * aside_blocks / body_chars, 2),
        "ask": asks_total,
        "ask_min_section": asks_per_section,
        "sections": len(sections),
        "lead_digits": lead_digits,
        "first_table": table_pos if table_pos is not None else 99999,
    }
    return m


def judge(m):
    rows = []
    hard_fail = 0
    soft_fail = 0
    for key, name, limit, op, hard, basis in THRESHOLDS:
        val = m[key]
        if key == "first_table" and m["first_table"] == 99999:
            ok = True
            shown = "无表格"
        else:
            shown = val
            ok = {"<=": val <= limit, ">=": val >= limit, "==": val == limit}[op]
        if not ok:
            if hard:
                hard_fail += 1
            else:
                soft_fail += 1
        rows.append({
            "key": key, "name": name, "value": shown, "limit": f"{op} {limit}",
            "ok": ok, "hard": hard, "basis": basis,
        })
    return rows, hard_fail, soft_fail


def render(m, rows, hard_fail, soft_fail):
    title = Path(m["file"]).name
    print(f"\n== {title} ==")
    print(f"   正文 {m['chars']} 字 · 段落 {m['paras']} 个 · 章节 {m['sections']} 节 · 旁白 {m['aside']} 处")
    print(f"   {'指标':<22}{'实测':>10}{'门槛':>12}{'依据':>12}  判定")
    for r in rows:
        mark = "PASS" if r["ok"] else ("FAIL*" if r["hard"] else "FAIL")
        print(f"   {r['name']:<22}{str(r['value']):>10}{r['limit']:>12}{r['basis']:>12}  {mark}")
    if m["body_code_samples"]:
        print(f"   编号样例：{'、'.join(m['body_code_samples'])}")
    if m["body_tag_samples"]:
        print(f"   标签样例：{'、'.join(m['body_tag_samples'])}")

    verdict = "通过" if (hard_fail == 0 and soft_fail <= 3) else "未通过"
    print(f"\n   结论：{verdict}（一票否决失败 {hard_fail} 项，超线 {soft_fail} 项；超线 ≤3 项视为可接受）")
    return verdict == "通过"


def collect(target):
    p = Path(target)
    if p.is_dir():
        return sorted(p.rglob("正文.md"))
    return [p]


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}
    if not args:
        print(__doc__)
        return 2

    files = []
    for a in args:
        files.extend(collect(a))
    if not files:
        print("未找到正文.md")
        return 2

    all_ok = True
    report = []
    for f in files:
        m = analyze(f)
        rows, hard, soft = judge(m)
        ok = (hard == 0 and soft <= 3)
        all_ok = all_ok and ok
        if "--json" in flags:
            report.append({"metrics": m, "rows": rows, "pass": ok})
        else:
            render(m, rows, hard, soft)

    if "--json" in flags:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
