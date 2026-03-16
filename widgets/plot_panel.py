"""封装 Matplotlib 画布，供 Qt 界面复用。"""
from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

plt.rcParams["font.family"] = ["SimHei"]
plt.rcParams['axes.unicode_minus'] = False


class MplCanvas(FigureCanvasQTAgg):
    """
    统一的 Matplotlib 画布封装。

    PlotView 只依赖该类暴露的 `ax` 属性和 FigureCanvas 行为，从而与具体 Qt 控件解耦。
    """

    def __init__(self, parent=None):
        # 统一配置画布尺寸/分辨率，让主界面与对话框的视觉效果保持一致。
        self.figure = plt.Figure(figsize=(10, 6), dpi=100)
        # 主应用始终只有一个子图，提前创建方便 PlotView 直接绘制。
        self.ax = self.figure.add_subplot(111)
        super().__init__(self.figure)
        if parent is not None:
            # FigureCanvas 仍是 QWidget，设置父控件即可融入 Qt 布局。
            self.setParent(parent)
