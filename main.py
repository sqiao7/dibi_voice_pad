import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from src.ui.main_window import MainWindow
from src.utils.logger import Logger


def exception_hook(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(error_msg)
    # Logger will capture print, so crash.log is redundant if logging is active, 
    # but keeping it as backup is fine.
    try:
        with open("crash.log", "w", encoding='utf-8') as f:
            f.write(error_msg)
    except:
        pass

    # Try to show a message box if QApplication is alive
    if QApplication.instance():
        QMessageBox.critical(None, "Error", f"发生意外错误:\n{value}")

    sys.exit(1)


def main():
    # 初始化日志
    Logger.setup()
    
    sys.excepthook = exception_hook

    app = QApplication(sys.argv)

    # 确保最小化到托盘时不会退出程序
    app.setQuitOnLastWindowClosed(False)

    # Initialize MainWindow
    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        # Manually call hook if exception happens inside main loop wrapper (though excepthook usually catches unhandled)
        exception_hook(type(e), e, e.__traceback__)


if __name__ == "__main__":
    main()
