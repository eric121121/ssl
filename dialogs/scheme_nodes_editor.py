
"""节点编辑器对话框"""
from __future__ import annotations

from PyQt5 import QtWidgets, QtCore

from .node_browser import open_global_node_browser


def create_scheme_nodes_editor(app, scheme_id, scheme_name):
    """
    打开节点编辑器（四个节点表 + 弹药类型表的 Tab 页面）。

    editor 与主窗口共享 NodeService/AmmoService 实例，通过回调 `refresh_scheme_plot`
    来保证地图上的节点状态同步更新。所有表格采用“自动保存”策略：修改即写库。
    """
    scheme_is_multi = app._apply_scheme_mode(scheme_id)
    dlg = QtWidgets.QDialog(app)
    dlg.setWindowTitle(f"编辑方案节点 - {scheme_name}")
    dlg.resize(1400, 800)  # 更均衡的初始大小
    # 记录当前激活的节点编辑器，便于主窗体控制结果弹窗位置
    app._active_editor_dialog = dlg

    layout = QtWidgets.QVBoxLayout(dlg)

    # 左半面：节点与弹药Tab；右半面：坐标系 + 四个按钮
    splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
    left_container = QtWidgets.QWidget()
    left_layout = QtWidgets.QVBoxLayout(left_container)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(6)

    # 创建 Tab Widget（放在左半面）
    tabs = QtWidgets.QTabWidget()

    def refresh_scheme_plot():
        """在当前激活画布上展示最新节点。"""
        # 如果正在动画中，直接从内存刷新，避免从数据库重新加载覆盖动画更新的坐标
        if getattr(app, 'is_animating', False):
            # 直接从内存中的节点数据刷新显示
            node_lists = {
                'target': app.target_nodes,
                'recon': app.recon_nodes,
                'command': app.command_nodes,
                'fire': app.fire_nodes,
            }
            app.plot_view.render_nodes(node_lists, app.multi_target_mode)
            # 如果有当前结果，也显示链路
            if app.current_result:
                try:
                    nodes = app.get_nodes_dict()
                    app.plot_view.render_result(nodes, app.current_result, show_optimal=False)
                except Exception:
                    pass
        elif scheme_id:
            app.place_scheme_nodes(scheme_id, scheme_name)

    # 四个节点表的配置
    node_configs = [
        {
            'name': '目标节点',
            'table': 'target_nodes',
            'columns': ['scheme_id', 'node_id', 'node_name', 'target_type', 'threat_level', 'x', 'y', 'h', 'vx', 'vy', 'vh'],
            'headers': ['方案ID', '节点ID', '节点名称', '目标类型', '威胁度', 'X坐标', 'Y坐标', '高程', '速度X', '速度Y', '速度H'],
            'editable_cols': [2, 3, 4, 5, 6, 7, 8, 9, 10]  # 除了 scheme_id 和 node_id
        },
        {
            'name': '侦察节点',
            'table': 'reconnaissance_nodes',
            'columns': ['scheme_id', 'node_id', 'node_name', 'model', 'parallel_limit', 'recon_range', 'recon_precision', 'processing_time', 'x', 'y', 'h', 'vx', 'vy', 'vh'],
            'headers': ['方案ID', '节点ID', '节点名称', '侦察类型', '并行上限', '侦察范围', '侦察精度', '处理时间', 'X坐标', 'Y坐标', '高程', '速度X', '速度Y', '速度H'],
            'editable_cols': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
        },
        {
            'name': '火力节点',
            'table': 'firepower_nodes',
            'columns': ['scheme_id', 'node_id', 'node_name', 'firepower_type', 'ammo_type', 'comm_distance', 'processing_time', 'x', 'y', 'h', 'vx', 'vy', 'vh'],
            'headers': ['方案ID', '节点ID', '节点名称', '火力类型', '弹药类型', '通信距离', '处理时间', 'X坐标', 'Y坐标', '高程', '速度X', '速度Y', '速度H'],
            'editable_cols': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        },
        {
            'name': '指挥节点',
            'table': 'command_nodes',
            'columns': ['scheme_id', 'node_id', 'node_name', 'command_capacity', 'comm_distance', 'processing_time', 'x', 'y', 'h', 'vx', 'vy', 'vh'],
            'headers': ['方案ID', '节点ID', '节点名称', '指挥容量', '通信距离', '处理时间', 'X坐标', 'Y坐标', '高程', '速度X', '速度Y', '速度H'],
            'editable_cols': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        }
    ]

    # 为每个节点类型创建 Tab
    for config in node_configs:
        tab_widget = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab_widget)

        # 创建表格
        table = QtWidgets.QTableWidget()
        table.setColumnCount(len(config['columns']))
        table.setHorizontalHeaderLabels(config['headers'])
        table.horizontalHeader().setStretchLastSection(True)

        # 加载该方案的节点数据
        def load_nodes(tbl, cfg, sid, tab_wgt=tab_widget):
            try:
                # 阻止信号，避免加载时触发自动保存
                tbl.blockSignals(True)

                rows = app.node_service.fetch_raw_nodes(cfg['table'], cfg['columns'], sid)

                tbl.setRowCount(len(rows))
                for i, row_data in enumerate(rows):
                    for j, value in enumerate(row_data):
                        item = QtWidgets.QTableWidgetItem(str(value))
                        # 设置是否可编辑（不设置背景颜色，保持颜色一致）
                        if j not in cfg['editable_cols']:
                            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                        tbl.setItem(i, j, item)

                # 恢复信号
                tbl.blockSignals(False)
            except Exception as e:
                QtWidgets.QMessageBox.critical(tab_wgt, "错误", f"加载{cfg['name']}失败: {e}")

        load_nodes(table, config, scheme_id)
        tab_layout.addWidget(table)

        # 按钮区域
        btn_layout = QtWidgets.QHBoxLayout()

        # 新增行按钮
        add_row_btn = QtWidgets.QPushButton("新增行")
        def add_row(_checked=False, tbl=table, cfg=config, sid=scheme_id):
            # 阻止信号，避免在添加行时触发自动保存
            tbl.blockSignals(True)

            row = tbl.rowCount()
            tbl.insertRow(row)

            # 设置默认值
            for j, col in enumerate(cfg['columns']):
                if col == 'scheme_id':
                    item = QtWidgets.QTableWidgetItem(sid)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                elif col == 'node_id':
                    item = QtWidgets.QTableWidgetItem("")  # 自动生成
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                else:
                    item = QtWidgets.QTableWidgetItem("")
                    if j not in cfg['editable_cols']:
                        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                tbl.setItem(row, j, item)

            # 恢复信号
            tbl.blockSignals(False)

        add_row_btn.clicked.connect(add_row)
        btn_layout.addWidget(add_row_btn)

        # 添加新节点按钮（通过对话框添加，带完整字段）
        add_new_node_btn = QtWidgets.QPushButton("添加新节点")
        def add_new_node(_checked=False, tbl=table, cfg=config, sid=scheme_id, load_fn=load_nodes):
            # 创建刷新回调函数
            def refresh_callback():
                load_fn(tbl, cfg, sid)
                refresh_scheme_plot()

            name_type_map = {
                '侦察节点': 'recon',
                '指挥节点': 'command',
                '火力节点': 'fire',
                '目标节点': 'target',
            }
            node_type = name_type_map.get(cfg['name'])
            if node_type:
                app.node_editor.add_node(node_type, sid, refresh_callback)

        add_new_node_btn.clicked.connect(add_new_node)
        btn_layout.addWidget(add_new_node_btn)

        # 删除行按钮
        delete_row_btn = QtWidgets.QPushButton("删除选中行")
        def delete_row(_checked=False, tbl=table, cfg=config, sid=scheme_id, load_fn=load_nodes, tab_wgt=tab_widget):
            # 获取所有选中的行（支持多行选择）
            selected_rows = sorted({it.row() for it in tbl.selectedItems()}, reverse=True)
            if not selected_rows:
                QtWidgets.QMessageBox.warning(tab_wgt, "提示", "请先选择要删除的行")
                return

            # 收集要删除的 node_id 值
            node_id_col_idx = cfg['columns'].index('node_id') if 'node_id' in cfg['columns'] else None
            node_ids_to_delete = []
            rows_without_id = []

            for row_idx in selected_rows:
                if node_id_col_idx is not None:
                    node_id_item = tbl.item(row_idx, node_id_col_idx)
                    node_id_val = node_id_item.text().strip() if node_id_item else None
                    if node_id_val:
                        node_ids_to_delete.append(node_id_val)
                    else:
                        rows_without_id.append(row_idx)
                else:
                    rows_without_id.append(row_idx)

            try:
                # 如果有有效 node_id，从数据库删除
                if node_ids_to_delete:
                    app.node_service.delete_nodes(cfg['table'], sid, node_ids_to_delete)

                # 对于没有 node_id 的行（新加未保存的行），直接从UI移除
                tbl.blockSignals(True)
                for row_idx in rows_without_id:
                    tbl.removeRow(row_idx)
                tbl.blockSignals(False)

                # 清除选中状态
                tbl.clearSelection()

                # 如果有数据库操作，刷新UI
                if node_ids_to_delete:
                    load_fn(tbl, cfg, sid)
                    if cfg.get('name') == '目标节点':
                        app._apply_scheme_mode(sid)
                    # 刷新后再次清除选中状态
                    tbl.clearSelection()
                elif cfg.get('name') == '目标节点':
                    # 无数据库操作但删除了未保存的目标行，也需要更新模式
                    app._apply_scheme_mode(sid)
                refresh_scheme_plot()
            except Exception as e:
                QtWidgets.QMessageBox.critical(tab_wgt, "错误", f"删除失败: {e}")

        delete_row_btn.clicked.connect(delete_row)
        btn_layout.addWidget(delete_row_btn)

        # 全部数据按钮（按节点类型显示全部数据，跨方案查看）
        if config['name'] == '目标节点':
            view_all_btn_text = "全部目标数据"
        elif config['name'] == '侦察节点':
            view_all_btn_text = "全部侦察数据"
        elif config['name'] == '指挥节点':
            view_all_btn_text = "全部指挥数据"
        elif config['name'] == '火力节点':
            view_all_btn_text = "全部火力数据"
        else:
            view_all_btn_text = "全部数据"

        view_all_btn = QtWidgets.QPushButton(view_all_btn_text)

        def view_all_data(_checked=False, cfg=config, tbl_target=table, load_fn=load_nodes, sid=scheme_id):
            """打开全局浏览器，把其它方案的节点复制到当前方案。"""
            open_global_node_browser(
                parent=dlg,
                node_service=app.node_service,
                current_scheme_id=app.current_scheme_id,
                config=cfg,
                load_fn=load_fn,
                table_widget=tbl_target,
                scheme_id=sid,
                apply_scheme_mode=app._apply_scheme_mode,
                refresh_plot=refresh_scheme_plot,
            )

        view_all_btn.clicked.connect(view_all_data)
        btn_layout.addWidget(view_all_btn)

        btn_layout.addStretch()
        tab_layout.addLayout(btn_layout)

        # 自动保存功能：当表格数据改变时自动保存整个表
        def auto_save_nodes(item, tbl=table, cfg=config, tab_wgt=tab_widget, sid=scheme_id):
            # 控件内所有变更都直接写回数据库，减少“保存按钮”的心智负担。
            # 只处理可编辑的列，其余列（例如 scheme_id/node_id）由系统维护。
            if item.column() in cfg['editable_cols']:
                try:
                    cols_without_id = [c for c in cfg['columns'] if c != 'node_id']
                    rows_payload = []
                    for row_idx in range(tbl.rowCount()):
                        row_values = []
                        for col_name in cfg['columns']:
                            if col_name == 'node_id':
                                continue
                            col_index = cfg['columns'].index(col_name)
                            cell = tbl.item(row_idx, col_index)
                            text_val = cell.text().strip() if cell and cell.text() else None
                            row_values.append(text_val)
                        rows_payload.append(row_values)

                    app.node_service.replace_nodes(cfg['table'], cols_without_id, sid, rows_payload)

                    load_nodes(tbl, cfg, sid)
                    if cfg.get('name') == '目标节点':
                        app._apply_scheme_mode(sid)
                    refresh_scheme_plot()

                except Exception as e:
                    QtWidgets.QMessageBox.critical(tab_wgt, "错误", f"自动保存失败: {e}")

        table.itemChanged.connect(auto_save_nodes)

        tabs.addTab(tab_widget, config['name'])

    # ========== 添加弹药类型表 Tab ==========
    ammo_tab_widget = QtWidgets.QWidget()
    ammo_tab_layout = QtWidgets.QVBoxLayout(ammo_tab_widget)

    # 创建弹药类型表格
    ammo_table = QtWidgets.QTableWidget()
    ammo_table.setColumnCount(9)
    ammo_table.setHorizontalHeaderLabels([
        'ID', '弹药类型', '精度', '弹药数量', '最大射程', 
        '毁伤半径', '折算系数', '飞行时间', '成本'
    ])
    ammo_table.horizontalHeader().setStretchLastSection(True)

    # 加载弹药数据（不受方案限制，全局数据）
    def load_ammo_data():
        try:
            ammo_table.blockSignals(True)
            rows = app.ammo_service.fetch_all()
            ammo_table.setRowCount(len(rows))
            for i, row_data in enumerate(rows):
                for j, value in enumerate(row_data):
                    item = QtWidgets.QTableWidgetItem(str(value))
                    if j == 0:
                        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                        item.setBackground(QtCore.Qt.lightGray)
                    ammo_table.setItem(i, j, item)
            ammo_table.blockSignals(False)
        except Exception as e:
            QtWidgets.QMessageBox.critical(ammo_tab_widget, "错误", f"加载弹药数据失败: {e}")

    load_ammo_data()
    ammo_tab_layout.addWidget(ammo_table)

    # 弹药表按钮区域
    ammo_btn_layout = QtWidgets.QHBoxLayout()

    # 新增弹药行
    add_ammo_btn = QtWidgets.QPushButton("新增行")
    def add_ammo_row():
        # 阻止信号，避免在添加行时触发自动保存
        ammo_table.blockSignals(True)

        row = ammo_table.rowCount()
        ammo_table.insertRow(row)
        # ID列留空（自动生成）
        for j in range(9):
            item = QtWidgets.QTableWidgetItem("")
            if j == 0:  # ID列
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                item.setBackground(QtCore.Qt.lightGray)
            ammo_table.setItem(row, j, item)

        # 恢复信号
        ammo_table.blockSignals(False)

    add_ammo_btn.clicked.connect(add_ammo_row)
    ammo_btn_layout.addWidget(add_ammo_btn)

    # 删除弹药行
    delete_ammo_btn = QtWidgets.QPushButton("删除选中行")
    def delete_ammo_row():
        # 获取所有选中的行（支持多行选择）
        selected_rows = sorted({it.row() for it in ammo_table.selectedItems()}, reverse=True)
        if not selected_rows:
            QtWidgets.QMessageBox.warning(ammo_tab_widget, "提示", "请先选择要删除的行")
            return

        # 收集要删除的 ammo_type 值（第二列是 ammo_type）
        ammo_types_to_delete = []
        rows_without_key = []

        for row_idx in selected_rows:
            ammo_type_item = ammo_table.item(row_idx, 1)  # ammo_type 在第二列（索引1）
            if ammo_type_item and ammo_type_item.text().strip():
                ammo_types_to_delete.append(ammo_type_item.text().strip())
            else:
                rows_without_key.append(row_idx)

        try:
            if ammo_types_to_delete:
                app.ammo_service.delete_by_types(ammo_types_to_delete)

            # 对于没有主键的空行，直接从表格移除
            ammo_table.blockSignals(True)
            for row_idx in rows_without_key:
                ammo_table.removeRow(row_idx)
            ammo_table.blockSignals(False)

            # 清除选中状态
            ammo_table.clearSelection()

            # 如果有数据库操作，刷新UI以同步ID列
            if ammo_types_to_delete:
                load_ammo_data()
                # 刷新后再次清除选中状态
                ammo_table.clearSelection()
        except Exception as e:
            QtWidgets.QMessageBox.critical(ammo_tab_widget, "错误", f"删除失败: {e}")

    delete_ammo_btn.clicked.connect(delete_ammo_row)
    ammo_btn_layout.addWidget(delete_ammo_btn)

    ammo_btn_layout.addStretch()
    ammo_tab_layout.addLayout(ammo_btn_layout)

    # 自动保存功能：当表格数据改变时自动保存
    def auto_save_ammo_data(item):
        # 只处理可编辑的列（ID列不可编辑）
        # 该函数与节点表一样，采用“删表重建”方式保持数据一致性。
        if item.column() > 0:
            try:
                rows_payload = []
                for row_idx in range(ammo_table.rowCount()):
                    row_values = []
                    for col_idx in range(1, 9):
                        cell = ammo_table.item(row_idx, col_idx)
                        text_val = cell.text().strip() if cell and cell.text() else None
                        row_values.append(text_val)
                    rows_payload.append(row_values)

                app.ammo_service.replace_all(rows_payload)
                load_ammo_data()
            except Exception as e:
                QtWidgets.QMessageBox.critical(ammo_tab_widget, "错误", f"自动保存失败: {e}")

    ammo_table.itemChanged.connect(auto_save_ammo_data)

    # 添加弹药类型表 Tab
    tabs.addTab(ammo_tab_widget, "弹药类型表")

    # 左侧完成，装入splitter
    left_layout.addWidget(tabs, 1)

    # 底部控制区域（7个按钮移动到左侧底部）
    left_footer = QtWidgets.QWidget()
    left_footer_layout = QtWidgets.QVBoxLayout(left_footer)
    left_footer_layout.setContentsMargins(0, 0, 0, 0)
    left_footer_layout.setSpacing(8)

    splitter.addWidget(left_container)

    # 右侧：坐标系 + 动画控制按钮
    right_container = QtWidgets.QWidget()
    right_layout = QtWidgets.QVBoxLayout(right_container)
    right_layout.setContentsMargins(6, 0, 0, 0)
    right_layout.setSpacing(6)

    # 添加动画控制区域（在坐标系上方）
    animate_control_widget = QtWidgets.QWidget()
    animate_control_layout = QtWidgets.QVBoxLayout(animate_control_widget)
    animate_control_layout.setContentsMargins(0, 0, 0, 0)
    animate_control_layout.setSpacing(5)
    
    # 时间步长滑动条
    time_step_layout = QtWidgets.QHBoxLayout()
    time_step_label = QtWidgets.QLabel("时间步长:")
    time_step_value_label = QtWidgets.QLabel("1.0秒")
    time_step_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
    time_step_slider.setMinimum(1)  # 0.1秒
    time_step_slider.setMaximum(50)  # 5.0秒
    time_step_slider.setValue(10)  # 默认1.0秒
    time_step_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
    time_step_slider.setTickInterval(10)
    
    def on_time_step_changed(value):
        app.animation_time_step = value / 10.0
        time_step_value_label.setText(f"{app.animation_time_step:.1f}秒")
    
    time_step_slider.valueChanged.connect(on_time_step_changed)
    
    time_step_layout.addWidget(time_step_label)
    time_step_layout.addWidget(time_step_slider, 1)
    time_step_layout.addWidget(time_step_value_label)
    animate_control_layout.addLayout(time_step_layout)
    
    # 动画时长滑动条
    duration_layout = QtWidgets.QHBoxLayout()
    duration_label = QtWidgets.QLabel("动画时长:")
    duration_value_label = QtWidgets.QLabel("60秒")
    duration_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
    duration_slider.setMinimum(10)  # 10秒
    duration_slider.setMaximum(300)  # 300秒
    duration_slider.setValue(60)  # 默认60秒
    duration_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
    duration_slider.setTickInterval(30)
    
    def on_duration_changed(value):
        app.animation_duration = float(value)
        duration_value_label.setText(f"{app.animation_duration:.0f}秒")
    
    duration_slider.valueChanged.connect(on_duration_changed)
    
    duration_layout.addWidget(duration_label)
    duration_layout.addWidget(duration_slider, 1)
    duration_layout.addWidget(duration_value_label)
    animate_control_layout.addLayout(duration_layout)
    
    # 动画按钮行
    animate_btn_layout = QtWidgets.QHBoxLayout()
    
    # 启动动画按钮
    btn_start_animate = QtWidgets.QPushButton("▶ 启动动目标动画")
    btn_start_animate.setStyleSheet("""
        QPushButton {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            padding: 5px 15px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
    """)
    
    # 停止动画按钮
    btn_stop_animate = QtWidgets.QPushButton("⏹ 停止动画")
    btn_stop_animate.setStyleSheet("""
        QPushButton {
            background-color: #f44336;
            color: white;
            font-weight: bold;
            padding: 5px 15px;
        }
        QPushButton:hover {
            background-color: #da190b;
        }
    """)
    btn_stop_animate.setEnabled(False)  # 初始状态禁用
    
    # 重置位置按钮
    btn_reset_animate = QtWidgets.QPushButton("↺ 重置位置")
    btn_reset_animate.setStyleSheet("""
        QPushButton {
            background-color: #2196F3;
            color: white;
            font-weight: bold;
            padding: 5px 15px;
        }
        QPushButton:hover {
            background-color: #0b7dda;
        }
    """)
    
    # 连接按钮信号
    btn_start_animate.clicked.connect(lambda: _start_animation_in_editor(btn_start_animate, btn_stop_animate, btn_reset_animate))
    btn_stop_animate.clicked.connect(lambda: _stop_animation_in_editor(btn_start_animate, btn_stop_animate, btn_reset_animate))
    btn_reset_animate.clicked.connect(lambda: _reset_animation_in_editor())
    
    animate_btn_layout.addWidget(btn_start_animate)
    animate_btn_layout.addWidget(btn_stop_animate)
    animate_btn_layout.addWidget(btn_reset_animate)
    animate_btn_layout.addStretch()
    animate_control_layout.addLayout(animate_btn_layout)
    
    # 动画状态标签
    animation_status_label = QtWidgets.QLabel("状态: 就绪")
    animation_status_label.setStyleSheet("color: #666; font-size: 12px;")
    animate_control_layout.addWidget(animation_status_label)
    
    right_layout.addWidget(animate_control_widget)

    # 在对话框内创建独立画布，并将绘图上下文切换到该画布
    from widgets.plot_panel import MplCanvas
    from views import PlotView
    dlg_canvas = MplCanvas(dlg)
    dlg_ax = dlg_canvas.ax
    app.setup_coordinate_axes(dlg_ax, '节点分布图')
    dlg_canvas.draw()

    # 创建绘图视图
    plot_view = PlotView(dlg_canvas, app.xlim, app.ylim)

    # 备份主窗体画布上下文并切换到对话框上下文
    _backup_canvas = getattr(app, '_backup_canvas', None)
    _backup_ax = getattr(app, '_backup_ax', None)
    app._backup_canvas = app.canvas
    app._backup_ax = getattr(app, 'ax', None)
    app.canvas = dlg_canvas
    app.ax = dlg_ax
    app.plot_view = plot_view
    refresh_scheme_plot()

    right_layout.addWidget(dlg_canvas, 1)
    
    # 动画控制函数
    def _start_animation_in_editor(start_btn, stop_btn, reset_btn):
        """在编辑器中启动动目标动画"""
        from algorithms import has_movable_targets
        
        # 获取所有目标
        all_targets = app.get_all_targets() if app.multi_target_mode else None
        if not all_targets and not app.target_nodes:
            QtWidgets.QMessageBox.warning(dlg, "提示", "没有目标节点")
            return
        
        targets_to_check = all_targets if all_targets else {
            t['id']: t for t in app.target_nodes
        }
        
        # 检查是否有可动目标（有速度的目标）
        has_movable = False
        for tid, target in targets_to_check.items():
            vx = target.get('vx', 0) or 0
            vy = target.get('vy', 0) or 0
            vh = target.get('vh', 0) or 0
            if vx != 0 or vy != 0 or vh != 0:
                has_movable = True
                break
        
        if not has_movable:
            QtWidgets.QMessageBox.information(dlg, "提示", "没有可动目标（vx/vy/vh均为0）")
            return
        
        # 保存初始位置（如果还没有保存）
        if not hasattr(app, 'original_target_positions') or not app.original_target_positions:
            app.original_target_positions = {}
            for tid, target in targets_to_check.items():
                app.original_target_positions[tid] = target['coord']
        
        # 创建动画定时器
        app.animation_timer = QtCore.QTimer(dlg)
        app.animation_timer.timeout.connect(lambda: _animation_step_in_editor(start_btn, stop_btn, reset_btn))
        
        # 初始化动画状态
        app.animation_start_time = 0.0
        app.is_animating = True
        
        # 更新按钮状态
        start_btn.setEnabled(False)
        stop_btn.setEnabled(True)
        reset_btn.setEnabled(False)
        animation_status_label.setText(f"状态: 运行中 (0.0/{app.animation_duration:.0f}秒)")
        
        # 启动动画
        app.animation_timer.start(int(app.animation_time_step * 1000))
        
        QtWidgets.QMessageBox.information(
            dlg, "动画启动", 
            f"动目标动画已启动\n时长: {app.animation_duration:.0f}秒\n时间步长: {app.animation_time_step:.1f}秒"
        )
    
    def _animation_step_in_editor(start_btn, stop_btn, reset_btn):
        """动画单步执行"""
        from algorithms import update_all_positions
        
        # 检查是否结束
        if app.animation_start_time >= app.animation_duration:
            _stop_animation_in_editor(start_btn, stop_btn, reset_btn)
            return
        
        # 获取当前目标
        if app.multi_target_mode:
            all_targets = app.get_all_targets()
        else:
            all_targets = {t['id']: t for t in app.target_nodes}
        
        # 获取节点配置（用于update_all_positions的nodes参数）
        try:
            nodes = app.get_nodes_dict()
        except ValueError:
            nodes = {'recon': {}, 'command': {}, 'fire': {}}
        
        # 更新目标位置（正确传入参数：targets, nodes, time_elapsed）
        updated_targets, _ = update_all_positions(all_targets, nodes, app.animation_time_step, update_nodes=False)
        
        # 更新时间
        app.animation_start_time += app.animation_time_step
        
        # 更新UI中的目标位置
        _update_target_positions_in_editor(updated_targets)
        
        # 重新运行算法
        _rebuild_ssl_in_editor(updated_targets)
        
        # 刷新显示
        refresh_scheme_plot()
        
        # 更新状态标签
        animation_status_label.setText(f"状态: 运行中 ({app.animation_start_time:.1f}/{app.animation_duration:.0f}秒)")
    
    def _update_target_positions_in_editor(updated_targets):
        """更新UI中的目标位置"""
        if app.multi_target_mode:
            for tid, target in updated_targets.items():
                if tid in app._last_multi_targets:
                    app._last_multi_targets[tid]['coord'] = target['coord']
        else:
            for node in app.target_nodes:
                tid = node['id']
                if tid in updated_targets:
                    node['coord'] = updated_targets[tid]['coord']
    
    def _rebuild_ssl_in_editor(updated_targets):
        """使用更新后的目标位置重新构建SSL"""
        try:
            nodes = app.get_nodes_dict()
            preference_table = app.get_fire_target_preference_table()
            
            if app.multi_target_mode:
                app.current_result = app.algorithm_service.build_multi_target_ssl(
                    updated_targets, nodes, preference_table
                )
            else:
                all_nodes = app.get_all_nodes_list()
                app.current_result = app.algorithm_service.run_loop(all_nodes, nodes)
        except Exception as e:
            print(f"重建SSL失败: {e}")
    
    def _stop_animation_in_editor(start_btn, stop_btn, reset_btn):
        """停止动目标动画"""
        if app.animation_timer:
            app.animation_timer.stop()
            app.animation_timer = None
        
        app.is_animating = False
        
        # 更新按钮状态
        start_btn.setEnabled(True)
        stop_btn.setEnabled(False)
        reset_btn.setEnabled(True)
        animation_status_label.setText(f"状态: 已停止 ({app.animation_start_time:.1f}/{app.animation_duration:.0f}秒)")
        
        # 恢复初始位置
        _restore_original_positions_in_editor()
        
        QtWidgets.QMessageBox.information(dlg, "动画结束", "动目标动画已结束，目标位置已恢复")
    
    def _reset_animation_in_editor():
        """重置动画状态"""
        # 停止动画（如果正在运行）
        if app.is_animating and app.animation_timer:
            app.animation_timer.stop()
            app.animation_timer = None
            app.is_animating = False
        
        # 恢复初始位置
        _restore_original_positions_in_editor()
        
        # 重置时间
        app.animation_start_time = 0.0
        
        # 更新状态
        animation_status_label.setText("状态: 就绪")
        
        # 清除保存的初始位置（下次启动时会重新保存）
        app.original_target_positions = {}
    
    def _restore_original_positions_in_editor():
        """恢复目标初始位置"""
        if not hasattr(app, 'original_target_positions') or not app.original_target_positions:
            return
        
        if app.multi_target_mode:
            for tid, coord in app.original_target_positions.items():
                if tid in app._last_multi_targets:
                    app._last_multi_targets[tid]['coord'] = coord
        else:
            for node in app.target_nodes:
                tid = node['id']
                if tid in app.original_target_positions:
                    node['coord'] = app.original_target_positions[tid]
        
        refresh_scheme_plot()

    buttons_row = QtWidgets.QHBoxLayout()
    # 四个按钮（使用与主页面相同的行为）
    btn_loop = QtWidgets.QPushButton("遍历搜索")
    def _run_loop_only_display():
        # 单目标遍历后需要立即在左侧展示详细结果
        app._suppress_next_details = False
        app.run_loop_search()
    btn_loop.clicked.connect(_run_loop_only_display)
    buttons_row.addWidget(btn_loop)

    btn_pso = QtWidgets.QPushButton("粒子群算法")
    def _run_pso_only_display():
        # 单目标粒子群运行后也自动弹出详情
        app._suppress_next_details = False
        app.run_pso_search()
    btn_pso.clicked.connect(_run_pso_only_display)
    buttons_row.addWidget(btn_pso)

    btn_multi = QtWidgets.QPushButton("多目标SSL构建")
    def _run_multi_only_display():
        app._suppress_next_details = True
        app.run_multi_target_ssl()
    btn_multi.clicked.connect(_run_multi_only_display)
    buttons_row.addWidget(btn_multi)

    btn_mopso = QtWidgets.QPushButton("多目标MOPSO优化")
    def _run_mopso_only_display():
        app._suppress_next_details = True
        app.run_mopso_multi_target()
    btn_mopso.clicked.connect(_run_mopso_only_display)
    buttons_row.addWidget(btn_mopso)

    app._editor_buttons = {
        'loop': btn_loop,
        'pso': btn_pso,
        'multi': btn_multi,
        'mopso': btn_mopso
    }
    app._update_editor_buttons()

    left_footer_layout.addLayout(buttons_row)
    buttons_row.setSpacing(10)

    splitter.addWidget(right_container)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 1)
    # 初始等分左右面板
    splitter.setSizes([700, 700])

    layout.addWidget(splitter)

    # 底部按钮区：关闭
    footer_button_row = QtWidgets.QHBoxLayout()
    footer_button_row.addStretch()

    close_btn = QtWidgets.QPushButton("关闭")

    def _cleanup_editor_buttons():
        app._editor_buttons = None
        if getattr(app, '_active_editor_dialog', None) is dlg:
            app._active_editor_dialog = None

    def on_close():
        # 关闭时恢复主窗体画布上下文
        if hasattr(app, '_backup_canvas') and hasattr(app, '_backup_ax'):
            app.activate_canvas(app._backup_canvas)
            # 不调用 refresh_scheme_plot()，保持主页面不变
            # 只刷新方案列表，不显示控制面板和画布
            app.scheme_panel_widget.refresh()
        _cleanup_editor_buttons()
        dlg.accept()

    close_btn.clicked.connect(on_close)
    dlg.finished.connect(lambda _status: _cleanup_editor_buttons())

    # 统一设置按钮大小
    for _b in (btn_loop, btn_pso, btn_multi, btn_mopso,
               close_btn):
        _b.setFixedHeight(32)
        _b.setMinimumWidth(90)

    footer_button_row.addWidget(close_btn)
    left_footer_layout.addLayout(footer_button_row)

    left_layout.addWidget(left_footer, 0)

    return dlg
