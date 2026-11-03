#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化文章集内某一篇的工作目录。

用法:
    python init-analysis.py --target "宠物医疗"                          # 集内序号自动取下一篇
    python init-analysis.py --target "宠物医疗" --stage 展开 --title "矿端面对的不是一个价"
    python init-analysis.py --target "宠物医疗" --issue 3 --stage 深挖 --title "仓单与基差"
    python init-analysis.py --target "宠物医疗" --form report

产出:
    <skill_root>/产出/<行业>/                      ← 文章集（Series）
        ├─ _系列索引.md                           ← 若不存在则从模板建骨架（不改写已有索引）
        └─ NN-<阶段>-<标题>/                    ← 集内第 NN 篇（阶段取 开篇／展开／深挖／反例／边界）
             ├─ 0-frame.md
             ├─ 数据表.md
             ├─ 证据索引.md
             ├─ 领域分析.md
             ├─ 正文.md
             └─ 审校意见.md

NN 为集内序号，不是全局流水号。
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

WINDOWS_FORBIDDEN = r'[\\/:*?"<>|]'
SERIES_INDEX_NAME = "_系列索引.md"


def skill_root() -> Path:
    """scripts/helpers/ -> skill root"""
    return Path(__file__).resolve().parent.parent.parent


def sanitize(name: str) -> str:
    cleaned = re.sub(WINDOWS_FORBIDDEN, "_", name).strip()
    return cleaned or "unnamed"


def next_issue(series_dir: Path) -> int:
    """集内下一序号：扫描已有 `NN-<阶段>-<标题>` 目录，取最大 NN + 1；冷启动为 1。

    以 `存档-` 开头的目录是被替换的旧稿，不占序号，跳过。
    """
    if not series_dir.exists():
        return 1
    nums = []
    for p in series_dir.iterdir():
        if not p.is_dir() or p.name.startswith("存档"):
            continue
        m = re.match(r"(\d+)-", p.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1


STAGES = ("开篇", "展开", "深挖", "反例", "边界")


def series_dir_name(issue: int, stage: str, title: str) -> str:
    """目录名 = NN-<阶段>-<正文标题缩略>。"""
    return f"{issue:02d}-{stage}-{sanitize(title)}" if title else f"{issue:02d}-{stage}"


def ensure_series_index(series_dir: Path, industry: str, today: str) -> bool:
    """确保文章集索引存在。已存在时返回 False，不改写其内容（由 P0 的 S6 维护）。"""
    idx = series_dir / SERIES_INDEX_NAME
    if idx.exists():
        return False
    tpl = skill_root() / "assets" / "templates" / "series-index-template.md"
    if tpl.exists():
        content = tpl.read_text(encoding="utf-8")
        content = content.replace("<行业名>", industry).replace("YYYY-MM-DD", today)
    else:
        content = (
            f"# 文章集索引：{industry}\n\n"
            f"> 本目录即该行业的文章集。动笔前必读，每篇完成后必追加。\n"
            f"> 创建日期：{today}\n\n"
            "## 篇目表\n\n| 序号 | 目录 | 子方向 | 切入视角 | 钩子类型 | 那根杠杆 | 生活入口 | 与已有篇的关系 | 状态 |\n"
            "|---|---|---|---|---|---|---|---|---|\n\n"
            "## 已覆盖清单\n\n### 已覆盖子方向\n\n### 已用切入视角 / 那根杠杆\n\n"
            "### 已用生活入口（不得复用）\n\n### 钩子类型分布\n\n"
            "## 待覆盖方向\n\n## 排序说明\n\n## 维护记录\n"
        )
    idx.write_text(content, encoding="utf-8")
    return True


FRAME = """# 0-frame: {target} · 第 {issue:02d} 篇

> 生成日期：{today}　集内序号：第 {issue:02d} 篇　形态：{form}

## 文章集与组织（S1—S6 留痕）
- 所属文章集：`产出/{target}/`
- 索引路径：`产出/{target}/_系列索引.md`
- 集内序号：第 {issue:02d} 篇（集内计数，非全局流水号）
- S2 已覆盖清单摘要：<子方向 / 视角 / 生活入口 / 钩子类型分布>
- S2 判定：<已有研究 / 冷启动>
- S3 目标具体度：<具体 / 不具体>
- S4 分支：<S4-A 独立性 / S4-B 去重换视角 / S4-C 基础逻辑开篇>；理由：<...>
- 本篇子方向：<...>
- 本篇切入视角：<...>
- 与已有篇的关系：<承接 / 并列 / 递进 / 补反例，第 NN 篇>
- S5 排序位次与理由：<...>（若调整默认递进顺序，写明原因）
- S6 索引已回写：<✓ / 待回写>

## 标的卡
- 所属大类：<A—G，见 research/01-industry-taxonomy.md>
- 主链条假设（待实证）：<抄自分类表，Phase 2 必须校验>

## 边界
- 覆盖：<具体环节>
- 不覆盖：<明确排除项>
- 时间范围：<...> / 地理范围：<...>

## 钩子
- 类型：<A 方向翻转 / B 理论反例 / C 被算错的流行数>
- 一句话：<按常识应该 A，实际却是 B；找不到就换标的>
- 层级自检：<属于「性质翻转」还是「量的分解」？后者必须换题>

## 答得圆满预检
- 钩子翻译成算式：<...>
- 每一项的来源层级：<L0/L1/...>
- 预判结论：<能闭合 / 不能闭合 → 换角度>

## 五维打分
| 维度 | 得分 | 依据 |
|---|---|---|
| 数据可查性 | ✓/✗ | <检索结果与来源> |
| 生活可感性 | <1-5> | <生活场景> |
| 机制独特性 | <1-5> | <预期杠杆> |
| 新颖性 | <1-5> | <索引 + 台账查重结果> |
| 当期性 | +<n> | <当期矛盾> |
"""

PHASES_CHECKPOINT = """# 领域分析：{target}（第 {issue:02d} 篇）

> Phase 1—4 的完整推导记录。**正文最后一个写。**

## 口径提示登记
| 混淆类型 | 涉及数据 | 处理方式 |
|---|---|---|

## P1 需求端
- 四问答案：
- 替代效应量价对照：
- 三因子分解：
- 需求端是否为当期主要变量：

## P2 链条与利润池
- 环节画像：
- 主链条假设校验（与假设的差异在哪）：
- 成本曲线分位：
- 利润池判定：
- 进出口是否泄压阀：

## P3 那根杠杆
- 杠杆：
- 准入四问（独有性 / 可量化 / 当期性 / 必要性反事实）：
- 双层结构（机制层 + 不响应层）：
- 传导时长与敏感性：
- 对冲变量清单：
- 多层乘法分解 + 反向验证：
- 历史实证区间：
- 反例与失灵条件：

## P4 校验
| 内容 | 事实性 | 相关性 | 可操作性 | 结论 |
|---|---|---|---|---|

## 数据缺口
| 缺口项 | 缺失原因 | 尝试来源 | 影响 |
|---|---|---|---|
"""

STUB = """<!--占位：依Asset模板填写-->

未完成。

- 模板：`assets/templates/{tpl}`
- 写作指引：`references/research/05-writing-dna.md`
- 完成条件见 `phases/{phase}`
"""

STUBS = {
    "数据表.md": ("data-sheet-template.md", "04-data-verification.md"),
    "证据索引.md": ("evidence-index-template.md", "04-data-verification.md"),
    "正文.md": ("longform-template.md", "05-write-and-review.md"),
    "审校意见.md": (None, "05-write-and-review.md"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化文章集内某一篇的工作目录")
    parser.add_argument("--target", required=True, help="行业标的，边界须可界定；同时作为文章集名")
    parser.add_argument("--issue", type=int, default=None, help="集内序号，默认自动取下一篇")
    parser.add_argument(
        "--stage",
        default=None,
        help=f"抽象阶段名，取 {'／'.join(STAGES)}；默认按集内序号推断（01→开篇，其余→展开）",
    )
    parser.add_argument(
        "--title",
        default="",
        help="正文标题（可缩略），用于目录名 NN-<阶段>-<标题>；缺省时只编号与阶段",
    )
    parser.add_argument(
        "--form", choices=["longform", "report", "brief"], default="longform"
    )
    parser.add_argument(
        "--output-root", default=None, help="产出根目录，默认 <skill_root>/产出"
    )
    args = parser.parse_args()

    root = skill_root()
    out_root = Path(args.output_root).resolve() if args.output_root else root / "产出"
    safe_target = sanitize(args.target)
    series_dir = out_root / safe_target
    issue = args.issue if args.issue is not None else next_issue(series_dir)
    stage = args.stage or ("开篇" if issue == 1 else "展开")
    if stage not in STAGES:
        print(f"[skip] 阶段名须取 {'／'.join(STAGES)}，当前为：{stage}")
        return 1
    issue_dir = series_dir / series_dir_name(issue, stage, args.title)

    if issue_dir.exists():
        print(f"[skip] 目录已存在：{issue_dir}")
        print("若为续写，直接编辑该目录内文件；若为新一篇，请更换 --issue。")
        return 1

    issue_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    created_index = ensure_series_index(series_dir, safe_target, today)

    (issue_dir / "0-frame.md").write_text(
        FRAME.format(target=args.target, today=today, issue=issue, form=args.form),
        encoding="utf-8",
    )
    (issue_dir / "领域分析.md").write_text(
        PHASES_CHECKPOINT.format(target=args.target, issue=issue),
        encoding="utf-8",
    )

    tpl_map = {
        "数据表.md": "data-sheet-template.md",
        "证据索引.md": "evidence-index-template.md",
        "正文.md": f"{args.form}-template.md",
        "审校意见.md": "tracking-signal-table.md",
    }
    for fname, tpl in tpl_map.items():
        (issue_dir / fname).write_text(
            STUB.format(tpl=tpl, phase=STUBS[fname][1]), encoding="utf-8"
        )

    print(f"[ok] 文章集：{series_dir}")
    print(f"[ok] 集内序号：第 {issue:02d} 篇 → {issue_dir}")
    if created_index:
        print(f"[ok] 已建索引骨架：{series_dir / SERIES_INDEX_NAME}")
        print("    若该集已有历史产出，须在 P0 的 S1 回填篇目表；S6 回写本篇。")
    else:
        print(f"[i]  索引已存在，未改写：{series_dir / SERIES_INDEX_NAME}（由 S6 回写）")
    print("产出顺序：数据表 → 证据索引 → 领域分析 → 审校意见 → 正文")
    print("提醒：正文禁止出现数据表里没有的数字。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
