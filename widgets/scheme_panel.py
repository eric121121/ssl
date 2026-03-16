"""方案管理面板组件。"""
from __future__ import annotations

from typing import Optional

from PyQt5 import QtWidgets, QtCore


class SchemePanel(QtWidgets.QWidget):
    """
    简易的方案管理面板，负责展示方案列表并把增删改查动作委托给 Service。

    主窗口只需监听两个信号：
    - `schemeSelected`: 用户在表格中切换行时触发，用于加载节点。
    - `editRequested`: 点击“杀伤链基础数据设置”时触发，打开节点编辑器。
    """
    schemeSelected = QtCore.pyqtSignal(str, str)
    editRequested = QtCore.pyqtSignal(str, str)

    def __init__(self, scheme_service, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.scheme_service = scheme_service
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        # 抬头保持简单文字标签，便于用户识别当前区域功能。
        header = QtWidgets.QLabel("方案管理")
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(header)

        self.table = QtWidgets.QTableWidget()
        # 只允许单行选择，方便同步主窗口状态。
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(['方案名称', '拟制时间', '拟制人'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 150)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        btn_row = QtWidgets.QHBoxLayout()
        # 按钮顺序依照“新增 -> 编辑 -> 删除”，符合一般操作习惯。
        self.btn_add = QtWidgets.QPushButton("新建杀伤链方案")
        self.btn_edit = QtWidgets.QPushButton("杀伤链基础数据设置")
        self.btn_delete = QtWidgets.QPushButton("删除")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_delete)
        layout.addLayout(btn_row)

        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemChanged.connect(self._on_item_changed)
        self.btn_add.clicked.connect(self._add_scheme)
        self.btn_edit.clicked.connect(self._emit_edit_request)
        self.btn_delete.clicked.connect(self._delete_scheme)

    def refresh(self):
        rows = self.scheme_service.fetch_all_for_panel()
        # blockSignals 避免刷新期间触发 selection changed，导致主窗口重复加载数据。
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for i, (scheme_id, scheme_name, created_time, creator) in enumerate(rows):
            item0 = QtWidgets.QTableWidgetItem(scheme_name)
            item0.setData(QtCore.Qt.UserRole, scheme_id)
            self.table.setItem(i, 0, item0)

            item1 = QtWidgets.QTableWidgetItem(str(created_time))
            item1.setFlags(item1.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(i, 1, item1)

            item2 = QtWidgets.QTableWidgetItem(creator)
            self.table.setItem(i, 2, item2)
        self.table.blockSignals(False)

    def select_scheme(self, scheme_id: str):
        """外部调用，用于定位到特定方案行。"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == scheme_id:
                self.table.setCurrentItem(item)
                return

    def current_scheme(self):
        """返回当前选中行的 (scheme_id, scheme_name)。"""
        items = self.table.selectedItems()
        if not items:
            return None, None
        row = items[0].row()
        scheme_id = self.table.item(row, 0).data(QtCore.Qt.UserRole)
        scheme_name = self.table.item(row, 0).text()
        return scheme_id, scheme_name

    def _on_selection_changed(self):
        scheme_id, scheme_name = self.current_scheme()
        if scheme_id:
            self.schemeSelected.emit(scheme_id, scheme_name)

    def _on_item_changed(self, item: QtWidgets.QTableWidgetItem):
        row = item.row()
        scheme_id = self.table.item(row, 0).data(QtCore.Qt.UserRole)
        if item.column() == 0:
            self.scheme_service.update_scheme_name(scheme_id, item.text())
        elif item.column() == 2:
            self.scheme_service.update_scheme_creator(scheme_id, item.text())

    def _add_scheme(self):
        """生成一个简单的占位方案，调用 Service 插入数据库。"""
        from datetime import datetime
        scheme_name = f"新方案{self.table.rowCount() + 1}"
        creator = "管理员"
        import uuid
        new_scheme_id = str(uuid.uuid4())
        self.scheme_service.create_scheme(new_scheme_id, scheme_name, creator)
        self.refresh()
        self.select_scheme(new_scheme_id)

    def _emit_edit_request(self):
        scheme_id, scheme_name = self.current_scheme()
        if scheme_id:
            self.editRequested.emit(scheme_id, scheme_name)


    def _delete_scheme(self):
        """删除方案及其节点，需要用户确认以避免误删。"""
        scheme_id, scheme_name = self.current_scheme()
        if not scheme_id:
            QtWidgets.QMessageBox.warning(self, "警告", "请先选择一个方案")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "确认删除",
            f"确定要删除方案 '{scheme_name}' 吗？\n这将同时删除该方案下的所有节点数据！",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self.scheme_service.delete_scheme_and_nodes(scheme_id)
                self.refresh()
                self.schemeSelected.emit("", "")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"删除失败: {e}")
