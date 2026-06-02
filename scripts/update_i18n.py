# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
#!/usr/bin/env python
"""翻译文件更新脚本。

用法：
    python scripts/update_i18n.py          # 提取 + 编译
    python scripts/update_i18n.py --extract # 仅提取
    python scripts/update_i18n.py --compile # 仅编译
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

I18N_DIR = Path(__file__).resolve().parent.parent / "tod" / "gui" / "i18n"
GUI_DIR = I18N_DIR.parent


def extract_ts() -> None:
    """使用 pylupdate6 从 tod/gui/ 提取待翻译字符串到 .ts 文件。

    注意：pylupdate6 会保留已有翻译，仅标记新增条目为 unfinished。
    对于使用 QCoreApplication.translate("Context", ...) 的 Mixin 类，
    pylupdate6 可能丢失旧翻译。此函数在提取后检查并报告未翻译条目。
    """
    ts_path = I18N_DIR / "gui.en.ts"
    print(f"提取翻译字符串 → {ts_path}")

    py_files = [str(p) for p in GUI_DIR.rglob("*.py") if "__pycache__" not in str(p)]
    result = subprocess.run(
        ["pylupdate6", *py_files, "--ts", str(ts_path), "--no-obsolete"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"pylupdate6 错误:\n{result.stderr}")
        sys.exit(1)

    # Check for unfinished translations
    import xml.etree.ElementTree as ET
    tree = ET.parse(ts_path)
    root = tree.getroot()
    unfinished = 0
    for ctx in root.findall("context"):
        ctx_name = ctx.find("name").text
        for msg in ctx.findall("message"):
            trans = msg.find("translation")
            if trans.get("type") == "unfinished":
                unfinished += 1
                src = msg.find("source").text or ""
                print(f"  未翻译: [{ctx_name}] {src[:60]}")

    if unfinished > 0:
        print(f"  共 {unfinished} 条未翻译，请编辑 {ts_path}")
    else:
        print("  全部翻译已完成")

    print(f"  完成: {ts_path}")


def compile_qm() -> None:
    """使用 lrelease6 编译 .ts → .qm。"""
    for ts_file in I18N_DIR.glob("gui.*.ts"):
        qm_file = ts_file.with_suffix(".qm")
        print(f"编译 {ts_file.name} → {qm_file.name}")
        result = subprocess.run(
            ["lrelease6", str(ts_file), "-qm", str(qm_file)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"lrelease6 错误:\n{result.stderr}")
            sys.exit(1)
        print(f"  完成: {qm_file}")


def validate_json() -> None:
    """校验 JSON 翻译表格式。"""
    for json_file in I18N_DIR.glob("scripts.*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            entries = len([k for k in data if not k.startswith("_")])
            print(f"校验 {json_file.name}: {entries} 条翻译")
        except json.JSONDecodeError as e:
            print(f"JSON 错误 {json_file.name}: {e}")
            sys.exit(1)


def main() -> None:
    do_extract = "--extract" in sys.argv or len(sys.argv) == 1
    do_compile = "--compile" in sys.argv or len(sys.argv) == 1

    I18N_DIR.mkdir(parents=True, exist_ok=True)

    if do_extract:
        extract_ts()
    if do_compile:
        compile_qm()
    validate_json()
    print("\n完成。")


if __name__ == "__main__":
    main()
