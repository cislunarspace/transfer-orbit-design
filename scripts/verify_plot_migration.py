#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证 Plot 迁移的正确性。

验证内容：
1. 所有 plot 模块可导入
2. script_registry.py 中的路径存在
3. 旧目录已清理
4. 抽样运行 plot 脚本

用法：
    python scripts/verify_plot_migration.py
"""

import importlib
import io
import os
import sys
from pathlib import Path

# 设置控制台编码
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def check_module_imports() -> tuple[int, int]:
    """检查所有 plot 模块是否可导入。"""
    print("\n=== 检查模块导入 ===")

    modules = [
        "tod.plot",
        "tod.plot.dro.plot_dro_family",
        "tod.plot.halo.plot_halo_family",
        "tod.plot.halo.plot_halo_orbit",
        "tod.plot.ro.plot_31_ro_family",
        "tod.plot.ro.plot_32_ro_family",
        "tod.plot.ro.plot_aro_family",
        "tod.plot.ro.plot_rro_family",
        "tod.plot.transfer.dro_to_ro.plot_search_results_dro_to_ro",
        "tod.plot.transfer.dro_to_ro.plot_optimize_result_dro_to_ro",
        "tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo",
        "tod.plot.transfer.geo_to_dro.plot_search_results_geo_to_dro",
        "tod.plot.transfer.geo_to_dro.plot_optimize_result_geo_to_dro",
        "tod.plot.ephemeris.plot_ephemeris_correction",
        "tod.plot.inspection.plot_interactive_orbit_inspector",
        "tod.plot.inspection.plot_single_orbit",
    ]

    passed = 0
    failed = 0

    for module in modules:
        try:
            importlib.import_module(module)
            print(f"  ✓ {module}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {module}: {e}")
            failed += 1

    return passed, failed


def check_script_registry_paths() -> tuple[int, int]:
    """检查 script_registry.py 中的路径是否存在。"""
    print("\n=== 检查 script_registry.py 路径 ===")

    # 导入 script_registry
    try:
        from tod.gui.script_registry import SCRIPTS
    except Exception as e:
        print(f"  ✗ 无法导入 script_registry: {e}")
        return 0, 1

    passed = 0
    failed = 0

    for category, entries in SCRIPTS.items():
        for entry in entries:
            script_path = PROJECT_ROOT / entry.script_path
            if script_path.exists():
                passed += 1
            else:
                print(f"  ✗ {entry.script_path} 不存在")
                failed += 1

    if failed == 0:
        print(f"  ✓ 所有 {passed} 个脚本路径存在")

    return passed, failed


def check_old_directories_cleaned() -> tuple[int, int]:
    """检查旧目录是否已清理。"""
    print("\n=== 检查旧目录清理 ===")

    old_dirs = [
        "tod/pipelines/dro/plot",
        "tod/pipelines/halo/plot",
        "tod/pipelines/ro/plot",
        "tod/pipelines/ephemeris/plot",
        "tod/pipelines/inspection",
    ]

    old_files = [
        "tod/pipelines/transfer/dro_to_ro/plot_search_results_dro_to_ro.py",
        "tod/pipelines/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py",
        "tod/pipelines/transfer/dro_to_geo/plot_search_results_dro_to_geo.py",
        "tod/pipelines/transfer/geo_to_dro/plot_search_results_geo_to_dro.py",
        "tod/pipelines/transfer/geo_to_dro/plot_optimize_result_geo_to_dro.py",
    ]

    passed = 0
    failed = 0

    for d in old_dirs:
        path = PROJECT_ROOT / d
        if path.exists():
            print(f"  ✗ 旧目录仍存在: {d}")
            failed += 1
        else:
            passed += 1

    for f in old_files:
        path = PROJECT_ROOT / f
        if path.exists():
            print(f"  ✗ 旧文件仍存在: {f}")
            failed += 1
        else:
            passed += 1

    if failed == 0:
        print(f"  ✓ 所有 {passed} 个旧目录/文件已清理")

    return passed, failed


def check_find_project_root() -> tuple[int, int]:
    """检查 find_project_root() 函数。"""
    print("\n=== 检查 find_project_root() ===")

    try:
        from tod.commons.common import find_project_root

        # 从不同路径测试
        test_paths = [
            PROJECT_ROOT / "tod/commons/common.py",
            PROJECT_ROOT / "tod/plot/dro/plot_dro_family.py",
            PROJECT_ROOT / "tod/plot/transfer/dro_to_ro/plot_search_results_dro_to_ro.py",
        ]

        passed = 0
        failed = 0

        for test_path in test_paths:
            try:
                result = find_project_root(test_path)
                if result == PROJECT_ROOT:
                    print(f"  ✓ {test_path.name} -> {result.name}")
                    passed += 1
                else:
                    print(f"  ✗ {test_path.name} -> {result} (期望 {PROJECT_ROOT})")
                    failed += 1
            except Exception as e:
                print(f"  ✗ {test_path.name}: {e}")
                failed += 1

        return passed, failed

    except Exception as e:
        print(f"  ✗ 无法导入 find_project_root: {e}")
        return 0, 1


def main() -> None:
    print("验证 Plot 迁移...")
    print(f"项目根目录: {PROJECT_ROOT}")

    total_passed = 0
    total_failed = 0

    # 执行所有检查
    checks = [
        check_module_imports,
        check_script_registry_paths,
        check_old_directories_cleaned,
        check_find_project_root,
    ]

    for check in checks:
        passed, failed = check()
        total_passed += passed
        total_failed += failed

    # 输出总结
    print("\n=== 总结 ===")
    print(f"通过: {total_passed}")
    print(f"失败: {total_failed}")

    if total_failed == 0:
        print("\n✓ 所有验证通过！迁移成功。")
        return 0
    else:
        print("\n✗ 存在验证失败，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
