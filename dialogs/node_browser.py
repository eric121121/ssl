"""全局节点浏览对话框"""
from PyQt5 import QtWidgets, QtCore


def open_global_node_browser(parent, node_service, current_scheme_id, config,
                             load_fn, table_widget, scheme_id,
                             apply_scheme_mode=None, refresh_plot=None):
    """
    查看全部节点并批量添加到当前方案。

    设计思路：
    - 通过 NodeService `fetch_all_raw_nodes` 一次性列出所有方案的节点；
    - 用户可多选行并点击“添加”，函数会自动复制行数据并替换为当前 scheme_id；
    - 添加完成后调用 load_fn/apply_scheme_mode/refresh_plot 等回调，保持 UI 与画布一致。
    """
    dlg_all = QtWidgets.QDialog(parent)
    dlg_all.setWindowTitle(f"查看{config['name']} - 全部数据")
    dlg_all.resize(1000, 600)

    layout = QtWidgets.QVBoxLayout(dlg_all)
    tbl_all = QtWidgets.QTableWidget()
    tbl_all.setColumnCount(len(config['columns']))
    tbl_all.setHorizontalHeaderLabels(config['headers'])
    tbl_all.horizontalHeader().setStretchLastSection(True)
    tbl_all.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    tbl_all.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
    layout.addWidget(tbl_all)

    try:
        rows_all = node_service.fetch_all_raw_nodes(config['table'], config['columns'])
        tbl_all.setRowCount(len(rows_all))
        for i_row, row_data in enumerate(rows_all):
            for j_col, value in enumerate(row_data):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                tbl_all.setItem(i_row, j_col, item)
    except Exception as e:
        QtWidgets.QMessageBox.critical(dlg_all, "错误", f"加载全部数据失败: {e}")

    def add_selected():
        if current_scheme_id is None:
            QtWidgets.QMessageBox.warning(dlg_all, "警告", "请先选择方案并点击放置/编辑")
            return
        selected_ranges = tbl_all.selectedRanges()
        selected_rows = set()
        for selected_range in selected_ranges:
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                selected_rows.add(row)
        if not selected_rows:
            QtWidgets.QMessageBox.warning(dlg_all, "警告", "请先选择要添加的行")
            return
        try:
            cols_without_id = [c for c in config['columns'] if c != 'node_id']
            rows_to_insert = []
            for row_idx in sorted(selected_rows):
                row_values = []
                for col_name in config['columns']:
                    if col_name == 'node_id':
                        continue
                    if col_name == 'scheme_id':
                        row_values.append(current_scheme_id)
                    else:
                        col_index = config['columns'].index(col_name)
                        item = tbl_all.item(row_idx, col_index)
                        row_values.append(item.text().strip() if item and item.text() else None)
                rows_to_insert.append(row_values)
            node_service.insert_nodes(config['table'], cols_without_id, rows_to_insert)
            load_fn(table_widget, config, scheme_id)
            if config.get('name') == '目标节点' and apply_scheme_mode:
                apply_scheme_mode(scheme_id)
            if refresh_plot:
                refresh_plot()
        except Exception as e:
            QtWidgets.QMessageBox.critical(dlg_all, "错误", f"添加到方案失败: {e}")

    btn_add = QtWidgets.QPushButton("添加到当前方案")
    btn_add.clicked.connect(add_selected)
    btn_close = QtWidgets.QPushButton("关闭")
    btn_close.clicked.connect(dlg_all.accept)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.addStretch()
    btn_row.addWidget(btn_add)
    btn_row.addWidget(btn_close)
    layout.addLayout(btn_row)

    dlg_all.exec_()
