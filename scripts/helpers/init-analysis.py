#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化本期分析工作目录。

用法:
    python init-analysis.py --target "生猪养殖" --issue 02
    python init-analysis.py --target "生猪养殖" --issue 02 --form report

产出:
    <skill_root>/产出/<sanitized_target>/第NN期/
        ├─ 数据表.md        占位（引用 data-sheet-template）
        ├─ 证据索引.md       占位
        ├─ 领域分析.md       含七阶段检查点
        ├─ 正文.md           占位
        └─ 审校意见.md        占位
    并在当前期目录写出 0-frame.md 骨架
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

WINDOWS_FORBIDDEN = r'[\\/:*?"<>|]'


def skill_root() -> Path:
    """scripts/helpers/ -> skill root"""
    return Path(__file__).resolve().parent.parent.parent


def sanitize(name: str) -> str:
    cleaned = re.sub(WINDOWS_FORBIDDEN, "_", name).strip()
    return cleaned or "unnamed"


FRAME = """# 0-frame: {target}

> 生成日期：{today}　期号：第 {issue:02d} 期　形态：{form}

## 标的卡
- 所属大类：<A—G，见 research/01-industry-taxonomy.md>
- 主链条假设（待实证）：<抄自分类表，Phase 2 必须校验>

## 边界
- 覆盖：<具体环节>
- 不覆盖：<明确排除项>
- 时间范围：<...> / 地理范围：<...>

## 钩子
<一句话矛盾：「按常识应该 A，实际却是 B」；找不到就换标的>

## 五维打分（自动选题时填写）
| 维度 | 得分 | 依据 |
|---|---|---|
| 数据可查性 | ✓/✗ | <检索结果与来源> |
| 生活可感性 | <1-5> | <生活场景> |
| 机制独特性 | <1-5> | <预期杠杆> |
| 新颖性 | <1-5> | <台账查重结果> |
| 当期性 | +<n> | <当期矛盾> |
"""

PHASES_CHECKPOINT = """# 领域分析：{target}（第 {issue:02d} 期）

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
- 准入三问（独有性/可量化/当期性）：
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
    parser = argparse.ArgumentParser(description="初始化本期分析工作目录")
    parser.add_argument("--target", required=True, help="行业标的，边界须可界定")
    parser.add_argument("--issue", type=int, default=1, help="期号，默认 1")
    parser.add_argument(
        "--form", choices=["longform", "report", "brief"], default="longform"
    )
    parser.add_argument(
        "--output-root", default=None, help="产出根目录，默认 <skill_root>/产出"
    )
    args = parser.parse_args()

    root = skill_root()
    out_root = Path(args.output_root).resolve() if args.output_root else root / "产出"
    issue_dir = out_root / sanitize(args.target) / f"第{args.issue:02d}期"

    if issue_dir.exists():
        print(f"[skip] 目录已存在：{issue_dir}")
        print("若为续写，直接编辑该目录内文件；若为新一期，请更换 issue。")
        return 1

    issue_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    (issue_dir / "0-frame.md").write_text(
        FRAME.format(target=args.target, today=today, issue=args.issue, form=args.form),
        encoding="utf-8",
    )
    (issue_dir / "领域分析.md").write_text(
        PHASES_CHECKPOINT.format(target=args.target, issue=args.issue),
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

    print(f"[ok] 已初始化：{issue_dir}")
    print("产出顺序：数据表 → 证据索引 → 领域分析 → 审校意见 → 正文")
    print("提醒：正文禁止出现数据表里没有的数字。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
