"""Application entry point for transfer-orbit-design v2 GUI."""


def main() -> None:
    import os
    import sys

    from PyQt6.QtWidgets import QApplication

    from src.commons.font_config import apply_cjk_font_fallback

    apply_cjk_font_fallback()

    app = QApplication(sys.argv)

    # e2m2e pip 安装后闰秒内核自动搜索路径失效（见 detect_kernel_dir），
    # 必须在任何 import e2m2e 之前写入 SPICE_KERNEL_DIR，否则轨道设计报
    # SPICE(NOLEAPSECONDS)。缺失可用内核时弹窗引导：下载（带进度）或指定
    # 已有目录；用户跳过则本次不设置，功能用时再报错。
    from src.app.kernel_setup import ensure_kernels
    from src.commons.kernels import kernel_dir_usable
    from src.commons.paths import detect_kernel_dir

    kernel_dir = detect_kernel_dir()
    if not kernel_dir or not kernel_dir_usable(kernel_dir):
        kernel_dir = ensure_kernels()
    if kernel_dir:
        os.environ.setdefault("SPICE_KERNEL_DIR", kernel_dir)

    from src.app.main_window import MainWindow

    # 产物清单由 MainWindow 经轨道库 catalog_query 恢复（issue #375），
    # 启动预扫描 output/ 已随 discovery 文件名分类退役。
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
