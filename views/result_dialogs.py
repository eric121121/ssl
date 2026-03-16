"""结果展示相关的对话框。"""
import numbers
from PyQt5 import QtWidgets, QtCore, QtGui


def _format_redundancy_value(val):
    """将冗余度数值转换成 x/3 的分数字符串。"""
    if not isinstance(val, numbers.Real):
        return str(val)
    numeric = float(val)
    if abs(numeric) < 1e-9 or abs(numeric - 1.0) < 1e-9:
        return str(int(round(numeric)))
    numerator = int(round(numeric * 3))
    numerator = max(0, min(3, numerator))  # 冗余度只会在0-1之间，限制分子范围
    return f"{numerator}/3"


def _create_table_from_matrix(parent, headers, rows):
    """根据二维数组快速创建一个只读表格控件。"""
    table = QtWidgets.QTableWidget(parent)
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            item = QtWidgets.QTableWidgetItem(str(val))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            table.setItem(r_idx, c_idx, item)
    table.resizeColumnsToContents()
    table.resizeRowsToContents()
    table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    return table


def show_detailed_results(parent, result, node_names):
    """
    单目标算法详细结果窗口。

    包含以下分页：
        * 评估表（支持点击高亮/双击弹窗）
        * 可达性矩阵
        * 冗余度矩阵
    """
    if result is None:
        return
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(f"{result['method_name']} - 详细结果")
    dlg.resize(800, 500)
    vbox = QtWidgets.QVBoxLayout(dlg)
    tabs = QtWidgets.QTabWidget()
    vbox.addWidget(tabs)

    eval_widget = QtWidgets.QWidget()
    eval_layout = QtWidgets.QVBoxLayout(eval_widget)
    df_eval = result['evaluation']
    if not df_eval.empty:
        headers2 = list(df_eval.columns)
        table2 = QtWidgets.QTableWidget()
        table2.setColumnCount(len(headers2))
        table2.setHorizontalHeaderLabels(headers2)
        table2.setRowCount(len(df_eval))
        for r, (_, row) in enumerate(df_eval.iterrows()):
            for c, column in enumerate(headers2):
                val = row[column]
                if isinstance(val, numbers.Real) and not isinstance(val, numbers.Integral):
                    display = f"{val:.2f}"
                else:
                    display = val
                item = QtWidgets.QTableWidgetItem(str(display))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                table2.setItem(r, c, item)
        table2.resizeColumnsToContents()
        table2.resizeRowsToContents()
        table2.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table2.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table2.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        def _emit_preview():
            if not hasattr(parent, 'preview_single_chain'):
                return
            row_idx = table2.currentRow()
            if row_idx >= 0:
                parent.preview_single_chain(row_idx)

        def _emit_detail(row, _col):
            if hasattr(parent, 'show_single_chain_details'):
                parent.show_single_chain_details(row)

        table2.itemSelectionChanged.connect(_emit_preview)
        table2.cellDoubleClicked.connect(_emit_detail)
        if table2.rowCount() > 0:
            table2.selectRow(0)
            _emit_preview()
        eval_layout.addWidget(table2)
    else:
        eval_layout.addWidget(QtWidgets.QLabel("无数据"))
    tabs.addTab(eval_widget, "评估结果")

    matrix_widget = QtWidgets.QWidget()
    matrix_layout = QtWidgets.QVBoxLayout(matrix_widget)
    matrix_data = result['reachability_matrix']
    # 按原始顺序展示矩阵，1 高亮为灰底
    table = QtWidgets.QTableWidget(matrix_widget)
    table.setColumnCount(len(node_names) + 1)
    table.setRowCount(len(node_names))
    table.setHorizontalHeaderLabels([''] + node_names)
    table.verticalHeader().setVisible(False)

    for r, row_name in enumerate(node_names):
        row_item = QtWidgets.QTableWidgetItem(row_name)
        row_item.setTextAlignment(QtCore.Qt.AlignCenter)
        table.setItem(r, 0, row_item)
        for c, col_name in enumerate(node_names, start=1):
            val = matrix_data[r][c - 1]
            item = QtWidgets.QTableWidgetItem(str(val))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            if val == 1:
                item.setBackground(QtGui.QColor(180, 180, 180))
            table.setItem(r, c, item)

    table.resizeColumnsToContents()
    table.resizeRowsToContents()
    table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    matrix_layout.addWidget(table)
    tabs.addTab(matrix_widget, "可达性矩阵")

    red_widget = QtWidgets.QWidget()
    red_layout = QtWidgets.QVBoxLayout(red_widget)
    df_red = result['redundancy_matrix']
    if df_red is not None:
        headers3 = [''] + list(df_red.columns)
        table3 = QtWidgets.QTableWidget()
        table3.setColumnCount(len(headers3))
        table3.setHorizontalHeaderLabels(headers3)
        table3.setRowCount(len(df_red))
        for r, (idx, row) in enumerate(df_red.iterrows()):
            row_vals = [idx] + [_format_redundancy_value(val) for val in row]
            for c, val in enumerate(row_vals):
                item = QtWidgets.QTableWidgetItem(str(val))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                table3.setItem(r, c, item)
        table3.resizeColumnsToContents()
        table3.resizeRowsToContents()
        table3.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        red_layout.addWidget(table3)
    else:
        red_layout.addWidget(QtWidgets.QLabel("无数据"))
    tabs.addTab(red_widget, "冗余度矩阵")

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.addStretch()
    highlight_btn = QtWidgets.QPushButton("指标优选链")

    def _trigger_highlight():
        if hasattr(parent, 'show_indicator_optimal_chain'):
            parent.show_indicator_optimal_chain()

    highlight_btn.clicked.connect(_trigger_highlight)
    btn_row.addWidget(highlight_btn)
    vbox.addLayout(btn_row)

    if hasattr(parent, "_dock_secondary_dialog_left"):
        try:
            parent._dock_secondary_dialog_left(dlg)
        except Exception:
            pass
    dlg.exec_()


def show_multi_target_results(parent, result):
    """多目标算法结果窗口，展示生成的 DataFrame 报告（若可用）。"""
    if result is None:
        return
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(f"{result['method_name']} - 多目标SSL构建结果")
    dlg.resize(1200, 800)
    layout = QtWidgets.QVBoxLayout(dlg)
    tabs = QtWidgets.QTabWidget()
    layout.addWidget(tabs)

    def _add_dataframe_tab(df, title, formatter=None):
        widget = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(widget)
        if df is None or df.empty:
            vbox.addWidget(QtWidgets.QLabel("无数据"))
        else:
            table = QtWidgets.QTableWidget()
            table.setColumnCount(len(df.columns))
            table.setHorizontalHeaderLabels(df.columns.tolist())
            table.setRowCount(len(df))
            for r, (_, row) in enumerate(df.iterrows()):
                for c, val in enumerate(row):
                    display = formatter(val) if formatter else val
                    item = QtWidgets.QTableWidgetItem(str(display))
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    table.setItem(r, c, item)
            table.resizeColumnsToContents()
            table.resizeRowsToContents()
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            vbox.addWidget(table)
        tabs.addTab(widget, title)

    _add_dataframe_tab(result.get('multi_target_kill_chains'), "杀伤链组合")
    _add_dataframe_tab(result.get('multi_target_evaluation'), "评估结果")
    _add_dataframe_tab(result.get('multi_target_redundancy'), "冗余度矩阵", formatter=_format_redundancy_value)

    if hasattr(parent, "_dock_secondary_dialog_left"):
        try:
            parent._dock_secondary_dialog_left(dlg)
        except Exception:
            pass
    dlg.exec_()
