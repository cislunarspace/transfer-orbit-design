"""加载或计算轨道族"""

import os

from e2m2e.core import OrbitFamily


def load_or_compute(
    args, system, compute_func, output_dir, family_filename="family.json"
):
    """加载或计算轨道族

    参数:
        args: 命令行参数
        system: CR3BP_System对象
        compute_func: 计算轨道族的函数，接受system参数
        output_dir: 输出目录
        family_filename: 轨道族文件名

    返回:
        system: CR3BP_System对象
        family_result: OrbitFamily对象或None
    """
    # 加载模式
    if args.load:
        if args.load == True:
            # 未指定具体文件，查找最新的
            from .get_latest_family_file import get_latest_family_file

            family_path = get_latest_family_file(output_dir, family_filename)
        else:
            # 指定了文件名（可能是完整路径或相对路径）
            if os.path.isabs(args.load):
                family_path = args.load
            else:
                # 可能是 output/phase1_dro/xxx 或直接文件名
                if os.path.exists(args.load):
                    family_path = args.load
                else:
                    family_path = os.path.join(output_dir, args.load, family_filename)

        if family_path and os.path.exists(family_path):
            print(f"加载轨道族数据: {family_path}")
            family_result = OrbitFamily.load_from_file(family_path, system)
            print(f"已加载 {len(family_result)} 条轨道")
            return system, family_result
        else:
            print(f"未找到数据文件: {family_path}")
            print("将重新计算...")

    return system, None
