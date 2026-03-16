"""应用入口：负责启动 Qt 应用与主窗口。"""
import matplotlib
from PyQt5 import QtWidgets
from app import SSLApp


def main():
    # PyQt5 + Matplotlib 组合需要显式指定后端，否则某些平台会启用非交互后端导致空白窗口。
    matplotlib.use('Qt5Agg')
    # QApplication 必须在进程生命周期内保持单例，因此直接在入口函数中初始化。
    app = QtWidgets.QApplication([])
    window = SSLApp()
    window.show()
    # Qt 主循环会阻塞直至窗口关闭，是 UI 应用的最后一步。
    app.exec_()


if __name__ == "__main__":
    main()
