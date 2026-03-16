"""节点录入相关的对话框及工具。"""
from typing import Dict, List

from PyQt5 import QtWidgets


def open_node_form(parent, title, fields):
    """
    通用节点录入对话框。

    参数中的字段定义采用 declarative 格式，使得增加新节点属性时只需扩展配置即可，
    而无需修改 UI 代码。返回 dict 直接传给 NodeService 进行 upsert。
    """
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(400, 320)
    layout = QtWidgets.QGridLayout(dlg)

    widgets = {}
    for idx, field in enumerate(fields):
        label = QtWidgets.QLabel(field['label'])
        layout.addWidget(label, idx, 0)
        field_type = field.get('type', 'text')
        widget = None
        if field_type == 'text':
            widget = QtWidgets.QLineEdit()
            widget.setText(str(field.get('default', '')))
        elif field_type == 'combo':
            widget = QtWidgets.QComboBox()
            widget.setEditable(field.get('editable', False))
            widget.addItems(field.get('options', []))
            default = field.get('default')
            if default is not None:
                idx_default = widget.findText(str(default))
                if idx_default >= 0:
                    widget.setCurrentIndex(idx_default)
        elif field_type == 'int':
            widget = QtWidgets.QSpinBox()
            widget.setRange(field.get('min', -999999), field.get('max', 999999))
            widget.setValue(field.get('default', 0))
        else:  # double
            widget = QtWidgets.QDoubleSpinBox()
            widget.setRange(field.get('min', -999999.0), field.get('max', 999999.0))
            widget.setDecimals(field.get('decimals', 2))
            widget.setValue(field.get('default', 0.0))
        widgets[field['name']] = widget
        layout.addWidget(widget, idx, 1)

    button_row = QtWidgets.QHBoxLayout()
    ok_btn = QtWidgets.QPushButton("确定")
    cancel_btn = QtWidgets.QPushButton("取消")
    button_row.addStretch()
    button_row.addWidget(ok_btn)
    button_row.addWidget(cancel_btn)
    layout.addLayout(button_row, len(fields), 0, 1, 2)

    result = {}

    def accept_dialog():
        for field in fields:
            widget = widgets[field['name']]
            field_type = field.get('type', 'text')
            if field_type == 'combo':
                result[field['name']] = widget.currentText().strip()
            elif field_type in ('int', 'double'):
                result[field['name']] = float(widget.value())
            else:
                result[field['name']] = widget.text().strip()
        dlg.accept()

    ok_btn.clicked.connect(accept_dialog)
    cancel_btn.clicked.connect(dlg.reject)

    if dlg.exec_() == QtWidgets.QDialog.Accepted:
        return result
    return None


NODE_FIELD_CONFIG: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    'recon': {
        'title': "添加新侦察节点",
        'fields': [
            {'label': "节点名称:", 'name': "node_name", 'type': 'text'},
            {'label': "侦察类型:", 'name': "model", 'type': 'text'},
            {'label': "并行上限:", 'name': "parallel_limit", 'type': 'double', 'default': 1},
            {'label': "侦察距离:", 'name': "recon_range", 'type': 'double', 'default': 5.0},
            {'label': "精度:", 'name': "recon_precision", 'type': 'double', 'default': 0.1},
            {'label': "处理时间:", 'name': "processing_time", 'type': 'double', 'default': 5.0},
            {'label': "X坐标:", 'name': "x", 'type': 'double'},
            {'label': "Y坐标:", 'name': "y", 'type': 'double'},
            {'label': "高程:", 'name': "h", 'type': 'double'},
            {'label': "速度X:", 'name': "vx", 'type': 'double'},
            {'label': "速度Y:", 'name': "vy", 'type': 'double'},
            {'label': "速度H:", 'name': "vh", 'type': 'double'},
        ],
        'success': "新侦察节点已添加到数据库",
    },
    'command': {
        'title': "添加新指挥节点",
        'fields': [
            {'label': "节点名称:", 'name': "node_name", 'type': 'text'},
            {'label': "指挥容量:", 'name': "command_capacity", 'type': 'double', 'default': 1},
            {'label': "通信距离:", 'name': "comm_distance", 'type': 'double', 'default': 5.0},
            {'label': "处理时间:", 'name': "processing_time", 'type': 'double', 'default': 5.0},
            {'label': "X坐标:", 'name': "x", 'type': 'double'},
            {'label': "Y坐标:", 'name': "y", 'type': 'double'},
            {'label': "高程:", 'name': "h", 'type': 'double'},
            {'label': "速度X:", 'name': "vx", 'type': 'double'},
            {'label': "速度Y:", 'name': "vy", 'type': 'double'},
            {'label': "速度H:", 'name': "vh", 'type': 'double'},
        ],
        'success': "新指挥节点已添加到数据库",
    },
    'fire': {
        'title': "添加新火力节点",
        'fields': [
            {'label': "节点名称:", 'name': "node_name", 'type': 'text'},
            {'label': "火力类型:", 'name': "firepower_type", 'type': 'text'},
            {'label': "弹药类型:", 'name': "ammo_type", 'type': 'text'},
            {'label': "通信距离:", 'name': "comm_distance", 'type': 'double', 'default': 5.0},
            {'label': "处理时间:", 'name': "processing_time", 'type': 'double', 'default': 5.0},
            {'label': "X坐标:", 'name': "x", 'type': 'double'},
            {'label': "Y坐标:", 'name': "y", 'type': 'double'},
            {'label': "高程:", 'name': "h", 'type': 'double'},
            {'label': "速度X:", 'name': "vx", 'type': 'double'},
            {'label': "速度Y:", 'name': "vy", 'type': 'double'},
            {'label': "速度H:", 'name': "vh", 'type': 'double'},
        ],
        'success': "新火力节点已添加到数据库",
    },
    'target': {
        'title': "添加新目标",
        'fields': [
            {'label': "目标名称:", 'name': "node_name", 'type': 'text'},
            {'label': "目标类型:", 'name': "target_type", 'type': 'text'},
            {'label': "威胁度:", 'name': "threat_level", 'type': 'double', 'default': 1.0},
            {'label': "X坐标:", 'name': "x", 'type': 'double'},
            {'label': "Y坐标:", 'name': "y", 'type': 'double'},
            {'label': "高程:", 'name': "h", 'type': 'double'},
            {'label': "速度X:", 'name': "vx", 'type': 'double'},
            {'label': "速度Y:", 'name': "vy", 'type': 'double'},
            {'label': "速度H:", 'name': "vh", 'type': 'double'},
        ],
        'success': "新目标节点已添加到数据库",
    },
}


class NodeEditor:
    """节点 CRUD 入口，封装对 NodeService 的调用。"""

    def __init__(self, parent, node_service):
        self.parent = parent
        self.node_service = node_service

    def add_node(self, node_type: str, scheme_id: str, refresh_callback=None) -> bool:
        """
        打开对应节点表单并写入数据库。

        refresh_callback 通常是 SchemeNodesEditor 内部的 `load_nodes`，用来确保 UI 同步。
        """
        if not scheme_id:
            QtWidgets.QMessageBox.warning(self.parent, "警告", "请先选择一个方案")
            return False

        config = NODE_FIELD_CONFIG.get(node_type)
        if not config:
            QtWidgets.QMessageBox.warning(self.parent, "错误", f"暂不支持的节点类型: {node_type}")
            return False

        data = open_node_form(self.parent, config['title'], config['fields'])
        if not data:
            return False

        try:
            self.node_service.upsert_node(node_type, scheme_id, data)
            QtWidgets.QMessageBox.information(self.parent, "成功", config['success'])
            if refresh_callback:
                refresh_callback()
            return True
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self.parent, "错误", f"添加节点失败: {exc}")
            return False
