"""Application entry point for transfer-orbit-design v2 GUI."""


def main() -> None:
    import sys

    from PyQt6.QtWidgets import QApplication

    from src.commons.font_config import apply_cjk_font_fallback

    apply_cjk_font_fallback()

    app = QApplication(sys.argv)

    from src.app.main_window import MainWindow

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
