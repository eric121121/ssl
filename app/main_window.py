"""PyQt5 版主界面，实现方案管理与算法展示。"""
import pandas as pd
from PyQt5 import QtWidgets, QtCore, QtGui
from config import DATABASE_CONFIG, NODE_TYPES
from repositories.mysql_repository import MySQLRepository
from services.scheme_service import SchemeService
from services.node_service import NodeService
from services.ammo_service import AmmoService
from services.algorithm_service import AlgorithmService
from widgets.plot_panel import MplCanvas
from widgets.scheme_panel import SchemePanel
from dialogs.scheme_nodes_editor import create_scheme_nodes_editor
from dialogs.node_editor import NodeEditor
from views import PlotView, result_dialogs


class SSLApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("杀伤链构建与评估系统")
        self.resize(1280, 800)
        
        # 使用统一配置
        # 将数据库配置与 Repository 层集中在主窗口内，避免子组件重新建立连接。
        self.db_config = DATABASE_CONFIG
        self.repository = MySQLRepository(self.db_config)
        self.scheme_service = SchemeService(self.repository)
        self.node_service = NodeService(self.repository)
        self.ammo_service = AmmoService(self.repository)
        self.algorithm_service = AlgorithmService()
        self.node_editor = NodeEditor(self, self.node_service)
        
        # 当前方案管理
        # `schemes` 保存下拉面板所需的所有方案元数据，切换方案时不会重复查询数据库。
        self.current_scheme_id = None
        self.schemes = []  # 存储所有方案 [(scheme_id, scheme_name, creator)]
        
        # 坐标范围配置
        self.xlim = (-20, 0)
        self.ylim = (30, 40)

        central = QtWidgets.QWidget()
        # QMainWindow 需要一个中央控件，这里用 QWidget + QVBoxLayout 包裹所有 UI 元素。
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(10)

        # 创建主布局：顶部控制面板（水平） + 下方水平布局（左侧方案管理面板 + 右侧画布）
        main_vbox = QtWidgets.QVBoxLayout()
        
        # 顶部控制面板（水平布局）
        # 所有算法按钮集中放这里，便于统一控制启用/禁用状态。
        self.control_panel = QtWidgets.QWidget()
        self.control_panel_layout = QtWidgets.QHBoxLayout(self.control_panel)
        self.control_panel_layout.setContentsMargins(10, 10, 10, 10)
        self.control_panel_layout.setSpacing(10)
        
        # 添加按钮控件（水平排列）- 去除了"方案管理"按钮和分隔线
        self.loop_button = QtWidgets.QPushButton("\"遍历搜索\"")
        # 每个按钮直接连接一个算法触发槽函数，方便根据模式动态启用。
        self.loop_button.clicked.connect(self.run_loop_search)
        self.control_panel_layout.addWidget(self.loop_button)

        self.pso_button = QtWidgets.QPushButton("\"粒子群算法\"")
        self.pso_button.clicked.connect(self.run_pso_search)
        self.control_panel_layout.addWidget(self.pso_button)

        self.multi_target_button = QtWidgets.QPushButton("\"多目标SSL构建\"")
        self.multi_target_button.clicked.connect(self.run_multi_target_ssl)
        self.control_panel_layout.addWidget(self.multi_target_button)

        self.mopso_button = QtWidgets.QPushButton("\"多目标MOPSO优化\"")
        self.mopso_button.clicked.connect(self.run_mopso_multi_target)
        self.control_panel_layout.addWidget(self.mopso_button)
        
        # 下方水平布局：左侧方案管理面板 + 右侧画布
        bottom_hbox = QtWidgets.QHBoxLayout()
        
        # 左侧方案管理面板
        # SchemePanel 通过信号把“选中方案”和“编辑方案”事件回传给主窗口。
        self.scheme_panel_widget = SchemePanel(self.scheme_service)
        self.scheme_panel_widget.schemeSelected.connect(self.on_scheme_selected)
        self.scheme_panel_widget.editRequested.connect(self.open_scheme_nodes_editor)

        # Matplotlib 画布
        self.canvas = MplCanvas(self)
        self.plot_view = PlotView(self.canvas, self.xlim, self.ylim)
        self.activate_canvas(self.canvas)
        
        # 将方案管理面板和画布添加到水平布局中
        bottom_hbox.addWidget(self.scheme_panel_widget, 1)  # 方案管理面板（左侧）
        bottom_hbox.addWidget(self.canvas, 1)  # 画布占剩余空间（右侧）
        
        # 将控制面板和底部布局添加到垂直布局中
        # 控制面板高度固定，底部区域为 1 份伸缩系数，保证画布拥有最大空间。
        main_vbox.addWidget(self.control_panel, 0)  # 控制面板（顶部）
        main_vbox.addLayout(bottom_hbox, 1)  # 底部布局（方案管理 + 画布）

        # 主页面仅显示方案管理区域，隐藏顶部控制面板与右侧画布
        self.control_panel.setVisible(False)
        self.canvas.setVisible(False)
        
        # 将主布局添加到垂直布局中
        vbox.addLayout(main_vbox)

        # 数据
        # 这些列表作为 UI 的“临时缓存”，当用户点击“放置”后存储当前方案中的全部节点。
        self.recon_nodes = []
        self.command_nodes = []
        self.fire_nodes = []
        # 支持多个目标节点
        self.target_nodes = []
        # 弹目偏好表（来自数据库），用于匹配度指标
        self.preference_table = {}
        self.current_result = None
        		
        # 目标节点模式：True为多目标模式，False为单目标模式
        # 多目标模式下会限制某些算法按钮，并启用多目标功能。
        self.multi_target_mode = False
        self._last_multi_targets = {}

        # 控制是否自动弹出详细结果对话框（用于二级页面抑制弹窗）
        self._suppress_next_details = False
        self._editor_buttons = None

        # 交互功能已移除

        # 更新按钮状态
        self.update_buttons_based_on_mode()

        self.show_initial_nodes()

    

    def update_buttons_based_on_mode(self):
        """根据模式更新按钮状态"""
        if self.multi_target_mode:
            # 多目标模式：禁用单目标按钮，启用多目标按钮
            self.loop_button.setEnabled(False)
            self.pso_button.setEnabled(False)
            self.multi_target_button.setEnabled(True)
            self.mopso_button.setEnabled(True)
            
            # 更新提示信息
            self.loop_button.setToolTip("多目标模式下不可用，请使用'多目标SSL构建'或'多目标MOPSO优化'")
            self.pso_button.setToolTip("多目标模式下不可用，请使用'多目标SSL构建'或'多目标MOPSO优化'")
            self.multi_target_button.setToolTip("为所有目标构建杀伤链")
            self.mopso_button.setToolTip("使用MOPSO算法优化多目标杀伤链")
        else:
            # 单目标模式：启用单目标按钮，禁用多目标按钮
            self.loop_button.setEnabled(True)
            self.pso_button.setEnabled(True)
            self.multi_target_button.setEnabled(False)
            self.mopso_button.setEnabled(False)
            
            # 更新提示信息
            self.loop_button.setToolTip("使用'遍历搜索'方法寻找最优杀伤链")
            self.pso_button.setToolTip("使用'粒子群算法'寻找最优杀伤链")
            self.multi_target_button.setToolTip("单目标模式下不可用，请先添加多个目标节点")
            self.mopso_button.setToolTip("单目标模式下不可用，请先添加多个目标节点")


    def show_initial_nodes(self):
        node_lists = {
            'target': self.target_nodes,
            'recon': self.recon_nodes,
            'command': self.command_nodes,
            'fire': self.fire_nodes,
        }
        self.plot_view.render_nodes(node_lists, self.multi_target_mode)

    def setup_coordinate_axes(self, ax, title="节点分布图"):
        """兼容旧模块的坐标轴设置方法（供对话框等场景调用）。"""
        ax.set_xlim(*self.xlim)
        ax.set_ylim(*self.ylim)
        ax.set_xlabel('X坐标(km)')
        ax.set_ylabel('Y坐标(km)')
        ax.grid(True, linestyle='--', alpha=0.7)
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        if by_label:  # 避免空图例占位小方块
            ax.legend(by_label.values(), by_label.keys(), loc='best', fontsize=8)
        ax.set_title(title)

    def activate_canvas(self, canvas):
        """将内部绘图上下文切换到指定画布。"""
        self.canvas = canvas
        self.ax = canvas.ax
        if hasattr(self, 'plot_view'):
            self.plot_view.attach_canvas(canvas)

    def get_nodes_dict(self):
        """把 UI 缓存的节点列表转换为算法输入格式。"""
        if not self.target_nodes:
            raise ValueError("未设置目标节点")
        # 使用第一个目标节点作为主要目标（单目标模式下只使用第一个）
        main_target = self.target_nodes[0]
        nodes = {
            'target': main_target['coord'],
            'target_info': main_target,
            'recon': {f'o{i+1}': node for i, node in enumerate(self.recon_nodes)},
            'command': {f'c{i+1}': node for i, node in enumerate(self.command_nodes)},
            'fire': {f'w{i+1}': node for i, node in enumerate(self.fire_nodes)}
        }
        if self.preference_table:
            nodes['preference_table'] = self.preference_table
        return nodes

    def get_all_nodes_list(self):
        """返回算法模块所需的节点 key 列表（决定矩阵的索引顺序）。"""
        return (
            [f'o{i+1}' for i in range(len(self.recon_nodes))] +
            [f'c{i+1}' for i in range(len(self.command_nodes))] +
            [f'w{i+1}' for i in range(len(self.fire_nodes))] +
            ['t1']
        )

    def run_loop_search(self):
        """单目标模式下执行穷举遍历法，找到组合最优的杀伤链。"""
        try:
            # 检查是否为单目标模式
            if self.multi_target_mode:
                QtWidgets.QMessageBox.warning(self, "错误", '多目标模式下请使用"多目标SSL构建"或"多目标MOPSO优化"按钮')
                return
            
            nodes = self.get_nodes_dict()
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "提示", '请先设置目标节点（选择方案并点击"放置"）')
            return
        all_nodes = self.get_all_nodes_list()
        self.current_result = self.algorithm_service.run_loop(all_nodes, nodes)
        self.update_display()

    def run_pso_search(self):
        """单目标模式下执行粒子群优化算法。"""
        try:
            # 检查是否为单目标模式
            if self.multi_target_mode:
                QtWidgets.QMessageBox.warning(self, "错误", '多目标模式下请使用"多目标SSL构建"或"多目标MOPSO优化"按钮')
                return
            
            nodes = self.get_nodes_dict()
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "提示", '请先设置目标节点（选择方案并点击"放置"）')
            return
        all_nodes = self.get_all_nodes_list()
        self.current_result = self.algorithm_service.run_pso(all_nodes, nodes)
        self.update_display()

    def run_multi_target_ssl(self):
        """运行多目标SSL构建"""
        try:
            # 检查是否为多目标模式
            if not self.multi_target_mode:
                QtWidgets.QMessageBox.warning(self, "错误", '单目标模式下请使用"遍历搜索"或"粒子群算法"按钮')
                return
            
            # 获取所有目标节点
            all_targets = self.get_all_targets()
            if not all_targets:
                QtWidgets.QMessageBox.warning(self, "提示", '请先选择包含多个目标节点的方案并点击"放置"')
                return
            # 缓存当前的目标集，后续二级窗口可复用数据而无需再次查询数据库。
            self._last_multi_targets = all_targets
            
            # 获取节点配置
            nodes = self.get_nodes_dict()
            
            # 获取弹目偏好表
            preference_table = self.get_fire_target_preference_table()
            
            # 运行增强版"多目标SSL构建"
            self.current_result = self.algorithm_service.build_multi_target_ssl(all_targets, nodes, preference_table)
            self._render_multi_target_allocation_on_canvas()
            
            # 复用MOPSO详细结果页面
            self._prepare_multi_target_detail_view(self.current_result)
            self.show_mopso_results(row_idx=0)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"多目标SSL构建失败: {e}")
            import traceback
            traceback.print_exc()

    def _filter_successful_allocation_rows(self, report_rows):
        """仅保留'成功分配'分组下的链路明细，其余状态全部隐藏。"""
        if not report_rows:
            return []

        filtered_rows = []
        include_current_group = False
        success_group_found = False

        for row in report_rows:
            target_label = str(row.get('目标ID', ''))
            if target_label.startswith('==='):
                include_current_group = '成功分配' in target_label and '统计' not in target_label
                if include_current_group:
                    filtered_rows.append(row)
                    success_group_found = True
                continue

            if include_current_group:
                filtered_rows.append(row)

        return filtered_rows if success_group_found else report_rows

    def _prepare_multi_target_detail_view(self, result):
        """将多目标遍历结果包装成MOPSO详情所需的数据结构"""
        if not result:
            return
        final_allocation = result.get('final_allocation') or {}
        evaluation = result.get('evaluation') or {}
        allocation_report = result.get('allocation_report') or []
        success_only_report = self._filter_successful_allocation_rows(allocation_report)

        total_threat = evaluation.get('total_threat_value', 0) or 0
        total_cost = evaluation.get('total_cost', 0) or 0
        avg_reaction = evaluation.get('avg_reaction_time', 0) or 0
        avg_precision = evaluation.get('avg_precision', 0) or 0
        total_firepower = evaluation.get('total_fire_power', 0) or 0
        allocated = len(final_allocation)

        # MOPSO 详情页期待一个 DataFrame，这里将多目标 SSL 的汇总指标伪装成单条 Pareto 解。
        pareto_report = pd.DataFrame([{
            '方案编号': 'MT1',
            '分配目标数': allocated,
            '威胁度覆盖': round(total_threat, 0),
            '总成本': round(total_cost, 0),
            '平均反应时间(s)': round(avg_reaction, 2),
            '平均精度(σ²)': round(avg_precision, 2),
            '弹目匹配度': 0,
            '总火力能力': round(total_firepower, 0),
            '推荐': '✓ 覆盖/威胁最优' if allocated > 0 else ''
        }])

        # 目标函数向量沿用 MOPSO 的 6 个维度，符号与算法保持一致（越小越优）。
        objectives = [
            -total_threat * 10,
            total_cost,
            avg_reaction,
            avg_precision,
            0,
            -total_firepower,
        ]

        result['pareto_report'] = pareto_report
        result['pareto_archive'] = [(objectives, final_allocation, None)]
        result['pareto_solutions'] = [{
            'allocation_report': success_only_report,
            'evaluation': evaluation,
            'redundancy_matrix': None,
            'final_allocation': final_allocation
        }]

    def update_display(self):
        if self.current_result is None:
            return
        nodes = self.get_nodes_dict()
        self.plot_view.render_result(nodes, self.current_result, show_optimal=False)
        # 仅当未抑制时才弹出详细结果（供主界面/手动触发使用）
        # 部分子对话框会短暂设置 `_suppress_next_details` 来避免重复弹窗。
        if not getattr(self, '_suppress_next_details', False):
            self.show_detailed_results()
        # 重置一次性抑制标记
        self._suppress_next_details = False

    def show_detailed_results(self):
        """供主界面与节点编辑器调用的统一结果弹窗入口。"""
        if self.current_result is None:
            QtWidgets.QMessageBox.information(self, "提示", "暂无可展示的结果，请先运行算法。")
            return
        result_dialogs.show_detailed_results(self, self.current_result, self.get_all_nodes_list())

    def show_indicator_optimal_chain(self):
        """根据当前结果在画布上展示指标优选链。"""
        if self.current_result is None:
            QtWidgets.QMessageBox.information(self, "提示", "暂无结果可展示，请先运行算法。")
            return
        try:
            nodes = self.get_nodes_dict()
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "提示", "缺少目标节点，无法显示链路")
            return
        self.plot_view.render_result(nodes, self.current_result, show_optimal=True)

    def _get_single_chain_by_index(self, row_idx):
        if self.current_result is None or row_idx is None or row_idx < 0:
            return None
        chains = self.current_result.get('kill_chains') or []
        if 0 <= row_idx < len(chains):
            return chains[row_idx]
        return None

    def preview_single_chain(self, row_idx):
        """单击评估表行时在画布上展示对应链条。"""
        chain = self._get_single_chain_by_index(row_idx)
        if not chain:
            return
        try:
            nodes = self.get_nodes_dict()
        except ValueError:
            return
        # 重新绘制节点，再叠加当前链
        self.plot_view.render_result(nodes, self.current_result, show_optimal=False)
        self.plot_view.draw_single_chain(nodes, chain, color='blue', label='当前链')

    def get_single_chain_details(self, row_idx):
        """返回链条详细信息（用于对话框内表格展示）。"""
        chain = self._get_single_chain_by_index(row_idx)
        if not chain:
            return []
        details = []
        try:
            nodes = self.get_nodes_dict()
        except ValueError:
            nodes = None

        def _node_desc(node_dict, default_name):
            if not node_dict:
                return default_name
            name = node_dict.get('name') or node_dict.get('model') or default_name
            coord = node_dict.get('coord')
            if coord:
                return f"{name} (坐标: {coord[0]:.2f}, {coord[1]:.2f})"
            return name

        details.append(('链路', f"t1 -> {chain[0]} -> {chain[1]} -> {chain[2]}"))
        if nodes:
            details.append(('侦察节点', _node_desc(nodes['recon'].get(chain[0]), chain[0])))
            details.append(('指挥节点', _node_desc(nodes['command'].get(chain[1]), chain[1])))
            details.append(('火力节点', _node_desc(nodes['fire'].get(chain[2]), chain[2])))

        df_eval = self.current_result.get('evaluation')
        if df_eval is not None and row_idx is not None and 0 <= row_idx < len(df_eval):
            row = df_eval.iloc[row_idx]
            for col in df_eval.columns:
                details.append((str(col), row[col]))
        return details

    def show_single_chain_details(self, row_idx):
        """双击评估表行时以二级窗口展示链条详细信息。"""
        details = self.get_single_chain_details(row_idx)
        if not details:
            QtWidgets.QMessageBox.information(self, "提示", "未找到链条数据。")
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("链条详情")
        dlg.resize(320, 400)
        layout = QtWidgets.QVBoxLayout(dlg)
        table = QtWidgets.QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(['属性', '值'])
        table.setRowCount(len(details))
        for idx, (label, value) in enumerate(details):
            item_label = QtWidgets.QTableWidgetItem(str(label))
            item_value = QtWidgets.QTableWidgetItem(str(value))
            item_label.setTextAlignment(QtCore.Qt.AlignCenter)
            item_value.setTextAlignment(QtCore.Qt.AlignCenter)
            table.setItem(idx, 0, item_label)
            table.setItem(idx, 1, item_value)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(table)
        if hasattr(self, '_dock_secondary_dialog_left'):
            try:
                self._dock_secondary_dialog_left(dlg)
            except Exception:
                pass
        dlg.exec_()

    def load_schemes_silent(self):
        """静默加载所有方案列表（不更新UI）"""
        try:
            self.schemes = list(self.scheme_service.fetch_all_for_cache())
            
            # 如果有方案且未选择，自动选择第一个
            if len(self.schemes) > 0 and self.current_scheme_id is None:
                self.current_scheme_id = self.schemes[0][0]

            if self.current_scheme_id:
                self._apply_scheme_mode(self.current_scheme_id)

            panel = getattr(self, 'scheme_panel_widget', None)
            if panel:
                panel.refresh()
                if self.current_scheme_id:
                    panel.select_scheme(self.current_scheme_id)
        except Exception:
            pass  # 静默失败，不显示错误
    
    def _apply_scheme_mode(self, scheme_id):
        """根据方案ID设置单/多目标模式"""
        is_multi = False
        if scheme_id:
            is_multi = self._is_multi_target_scheme(scheme_id)
        self.multi_target_mode = is_multi
        self.update_buttons_based_on_mode()
        self._update_editor_buttons()
        return is_multi

    def _set_current_scheme(self, scheme_id):
        """统一设置当前方案ID，供子组件/对话框调用"""
        self.current_scheme_id = scheme_id

    def _update_editor_buttons(self):
        """根据模式更新节点编辑器中的按钮状态"""
        buttons = getattr(self, '_editor_buttons', None)
        if not buttons:
            return
        is_multi = self.multi_target_mode

        btn_loop = buttons.get('loop')
        if btn_loop is not None:
            btn_loop.setEnabled(not is_multi)
            btn_loop.setToolTip(
                "多目标模式下不可用，请使用'多目标SSL构建'或'多目标MOPSO优化'"
                if is_multi else "使用'遍历搜索'方法寻找最优杀伤链"
            )

        btn_pso = buttons.get('pso')
        if btn_pso is not None:
            btn_pso.setEnabled(not is_multi)
            btn_pso.setToolTip(
                "多目标模式下不可用，请使用'多目标SSL构建'或'多目标MOPSO优化'"
                if is_multi else "使用'粒子群算法'寻找最优杀伤链"
            )

        btn_multi = buttons.get('multi')
        if btn_multi is not None:
            btn_multi.setEnabled(is_multi)
            btn_multi.setToolTip(
                "为所有目标构建杀伤链"
                if is_multi else "单目标模式下不可用，请先添加多个目标节点"
            )

        btn_mopso = buttons.get('mopso')
        if btn_mopso is not None:
            btn_mopso.setEnabled(is_multi)
            btn_mopso.setToolTip(
                "使用MOPSO算法优化多目标杀伤链"
                if is_multi else "单目标模式下不可用，请先添加多个目标节点"
            )

    def _dock_secondary_dialog_left(self, dialog: QtWidgets.QDialog):
        """将结果类对话框固定在二级页面左半区，避免遮挡坐标系。"""
        host = getattr(self, '_active_editor_dialog', None)
        target = host if host and host.isVisible() else self
        try:
            geom = target.frameGeometry()
        except Exception:
            geom = QtCore.QRect(target.mapToGlobal(QtCore.QPoint(0, 0)), target.size())
        if geom.isNull():
            geom = QtCore.QRect(target.mapToGlobal(QtCore.QPoint(0, 0)), target.size())
        width = max(600, geom.width() // 2)
        height = geom.height() if geom.height() > 0 else dialog.sizeHint().height()
        if height <= 0:
            height = 700
        dialog.resize(width, height)
        dialog.move(geom.topLeft())

    def _render_multi_target_allocation(self, allocation: dict) -> bool:
        """使用指定分配结果刷新画布。"""
        if not allocation:
            return False
        targets = getattr(self, '_last_multi_targets', None) or self.get_all_targets()
        if not targets:
            return False
        try:
            nodes = self.get_nodes_dict()
        except ValueError:
            return False
        self.plot_view.render_multi_target_result(targets, nodes, allocation)
        self.canvas.setVisible(True)
        return True

    def _render_multi_target_allocation_on_canvas(self):
        """在画布上展示多目标分配链路。"""
        if not self.current_result:
            return
        allocation = None
        if isinstance(self.current_result, dict):
            allocation = self.current_result.get('final_allocation')
            if not allocation:
                pareto_solutions = self.current_result.get('pareto_solutions') or []
                for solution in pareto_solutions:
                    allocation = solution.get('final_allocation')
                    if allocation:
                        break
            if not allocation:
                pareto_archive = self.current_result.get('pareto_archive') or []
                for entry in pareto_archive:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        allocation = entry[1]
                        if allocation:
                            break
        self._render_multi_target_allocation(allocation)

    def _preview_pareto_solution(self, row_idx: int):
        allocation = self._get_pareto_allocation(row_idx)
        if allocation:
            self._render_multi_target_allocation(allocation)

    def _get_pareto_allocation(self, row_idx: int):
        if not self.current_result or row_idx is None or row_idx < 0:
            return None
        pareto_solutions = self.current_result.get('pareto_solutions') or []
        if 0 <= row_idx < len(pareto_solutions):
            allocation = pareto_solutions[row_idx].get('final_allocation')
            if allocation:
                return allocation
        pareto_archive = self.current_result.get('pareto_archive') or []
        if 0 <= row_idx < len(pareto_archive):
            entry = pareto_archive[row_idx]
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                return entry[1]
        return None

    def _is_multi_target_scheme(self, scheme_id):
        """查询方案是否包含多个目标节点"""
        if not scheme_id:
            return False
        try:
            count = self.scheme_service.count_targets(scheme_id)
            return count is not None and count > 1
        except Exception:
            return False
    
    def place_scheme_nodes(self, scheme_id=None, scheme_name=None):
        """放置方案中的节点到坐标系"""
        if not scheme_id:
            scheme_id, scheme_name = self.scheme_panel_widget.current_scheme()
        if not scheme_id:
            QtWidgets.QMessageBox.warning(self, "警告", "请先选择一个方案")
            return
        self.current_scheme_id = scheme_id
        self._apply_scheme_mode(scheme_id)
        
        try:
            nodes = self.node_service.load_scheme_nodes(scheme_id)
            self.target_nodes = nodes['targets']
            self.recon_nodes = nodes['recon']
            self.command_nodes = nodes['command']
            self.fire_nodes = nodes['fire']
            try:
                prefs = self.node_service.fetch_fire_target_preferences()
                self.preference_table = {(fire_type, target_type): preference_rank for fire_type, target_type, preference_rank in prefs}
            except Exception:
                self.preference_table = {}

            # 清空当前结果
            self.current_result = None

            # 根据目标节点数量设置模式
            self.multi_target_mode = len(self.target_nodes) > 1

            # 更新按钮状态
            self.update_buttons_based_on_mode()

            # 显示节点
            self.show_initial_nodes()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"加载节点失败: {e}")
            import traceback
            traceback.print_exc()

    def open_scheme_nodes_editor(self, scheme_id, scheme_name):
        dlg = create_scheme_nodes_editor(self, scheme_id, scheme_name)
        dlg.exec_()


    def _create_node_object(self, node_type, node_id, node_name, local_vars):
        """创建节点对象的通用方法"""
        x, y = local_vars['x'], local_vars['y']
        
        if node_type == 'recon':
            return {
                'coord': (x, y),
                'range': local_vars['recon_distance'],
                't_deal': local_vars['processing_time'],
                'sigma2': local_vars['precision'],
                'comm': 30000,  # 默认通信距离
                'model': local_vars['model'],
                'parallel_limit': local_vars['parallel_limit'],
                'name': f"o{len(self.recon_nodes)+1}"
            }
        elif node_type == 'command':
            return {
                'coord': (x, y),
                'range': local_vars['comm_distance'],
                't_deal': local_vars['processing_time'],
                'sigma2': 0.1,  # 默认精度值
                'command_capacity': local_vars['command_capacity'],  # 指挥容量
                'model': node_name,
                'name': f"c{len(self.command_nodes)+1}"
            } 
        elif node_type == 'fire':
            return {
                'coord': (x, y),
                'range': local_vars.get('effective_range', 50.0),  # 使用弹药的最大射程作为火力范围
                't_deal': local_vars['processing_time'],
                't_flight': local_vars.get('effective_flight_time', 30.0),  # 添加飞行时间
                'sigma2': local_vars.get('effective_precision', 0.1),  # 添加精度
                'comm': local_vars['comm_distance'],
                'firepower_type': local_vars['firepower_type'],
                'ammo_type': local_vars['ammo_type'],
                'ammo': {
                    'count': local_vars.get('effective_ammo_count', 10),
                    'omega': local_vars.get('effective_omega', 1.0),
                    'cost': local_vars.get('effective_cost', 0.0)  # 添加弹药成本
                },
                'model': node_name,
                'name': f"w{len(self.fire_nodes)+1}"
            }
        elif node_type == 'target':
            return {
                'id': f't{node_id}',
                'name': node_name,
                'type': local_vars['target_type'],
                'threat_level': local_vars['threat_level'],
                'coord': (x, y)
            }
        else:
            raise ValueError(f"未知的节点类型: {node_type}")

    def _add_node_to_list(self, node_type, node):
        """将节点添加到对应列表的通用方法"""
        if node_type == 'recon':
            self.recon_nodes.append(node)
        elif node_type == 'command':
            self.command_nodes.append(node)
        elif node_type == 'fire':
            self.fire_nodes.append(node)
        elif node_type == 'target':
            self.target_nodes.append(node)
        else:
            raise ValueError(f"未知的节点类型: {node_type}")

    def _show_message(self, message_type, title, message):
        """显示消息框的通用方法"""
        if message_type == 'info':
            QtWidgets.QMessageBox.information(self, title, message)
        elif message_type == 'warning':
            QtWidgets.QMessageBox.warning(self, title, message)
        elif message_type == 'critical':
            QtWidgets.QMessageBox.critical(self, title, message)
        else:
            QtWidgets.QMessageBox.information(self, title, message)

    def _create_auto_save_handler(self, node_type, table):
        """创建通用的自动保存处理器"""

        def auto_save(item):
            row = item.row()
            try:
                scheme_item = table.item(row, 0)
                scheme_id = scheme_item.text().strip() if scheme_item and scheme_item.text() else self.current_scheme_id
                if not scheme_id:
                    QtWidgets.QMessageBox.warning(self, "警告", "无法确定方案ID，保存终止")
                    return

                node_id_item = table.item(row, 1)
                node_id_text = node_id_item.text().strip() if node_id_item and node_id_item.text() else ''
                node_name = (table.item(row, 2).text() if table.item(row, 2) else '').strip()

                def t(idx):
                    it = table.item(row, idx)
                    return it.text().strip() if it and it.text() else ''

                def f(idx):
                    text_val = t(idx)
                    if text_val == '':
                        return 0.0
                    try:
                        return float(text_val)
                    except ValueError:
                        return 0.0

                if node_type == 'recon':
                    data = {
                        'node_name': node_name,
                        'model': t(3),
                        'parallel_limit': f(4),
                        'recon_range': f(5),
                        'recon_precision': f(6),
                        'processing_time': f(7),
                        'x': f(8), 'y': f(9), 'h': f(10),
                        'vx': f(11), 'vy': f(12), 'vh': f(13)
                    }
                    has_input = any(val not in ('', 0.0) for val in [
                        node_name, t(3), t(4), t(5), t(6), t(7),
                        t(8), t(9), t(10), t(11), t(12), t(13)
                    ])
                elif node_type == 'command':
                    data = {
                        'node_name': node_name,
                        'command_capacity': int(f(3)) if t(3) != '' else 0,
                        'comm_distance': f(4),
                        'processing_time': f(5),
                        'x': f(6), 'y': f(7), 'h': f(8),
                        'vx': f(9), 'vy': f(10), 'vh': f(11)
                    }
                    has_input = any(val not in ('', 0.0) for val in [
                        node_name, t(3), t(4), t(5), t(6), t(7), t(8), t(9), t(10), t(11)
                    ])
                elif node_type == 'fire':
                    data = {
                        'node_name': node_name,
                        'firepower_type': t(3),
                        'ammo_type': t(4),
                        'comm_distance': f(5),
                        'processing_time': f(6),
                        'x': f(7), 'y': f(8), 'h': f(9),
                        'vx': f(10), 'vy': f(11), 'vh': f(12)
                    }
                    has_input = any(val not in ('', 0.0) for val in [
                        node_name, t(3), t(4), t(5), t(6), t(7),
                        t(8), t(9), t(10), t(11), t(12)
                    ])
                elif node_type == 'target':
                    data = {
                        'node_name': node_name,
                        'target_type': t(3),
                        'threat_level': f(4),
                        'x': f(5), 'y': f(6), 'h': f(7),
                        'vx': f(8), 'vy': f(9), 'vh': f(10)
                    }
                    has_input = any(val not in ('', 0.0) for val in [
                        node_name, t(3), t(4), t(5), t(6), t(7), t(8), t(9), t(10)
                    ])
                else:
                    return

                if not has_input:
                    return

                node_id = int(node_id_text) if node_id_text.isdigit() else None
                new_id = self.node_service.upsert_node(node_type, scheme_id, data, node_id=node_id)

                if node_id is None:
                    table.blockSignals(True)
                    id_item = table.item(row, 1) or QtWidgets.QTableWidgetItem()
                    id_item.setText(str(new_id))
                    id_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    table.setItem(row, 1, id_item)
                    table.blockSignals(False)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"自动保存失败: {e}")

        return auto_save

    def _create_delete_handler(self, table, table_name, node_type):
        """创建通用的删除处理器"""
        def delete_selected_rows():
            selected_rows = sorted({it.row() for it in table.selectedItems()}, reverse=True)
            if not selected_rows:
                QtWidgets.QMessageBox.warning(self, "提示", "请先选择要删除的行")
                return
            
            # 收集要删除的 node_id 值（第一列通常是 node_id）
            ids_to_delete = []
            rows_without_id = []
            
            for r in selected_rows:
                it = table.item(r, 1)
                if it and it.text().strip().isdigit():
                    ids_to_delete.append(int(it.text().strip()))
                else:
                    rows_without_id.append(r)
            
            try:
                # 如果有有效 node_id，从数据库删除
                if ids_to_delete:
                    self.node_service.delete_nodes(table_name, self.current_scheme_id, ids_to_delete)
            
                # 对于没有 node_id 的行，直接从UI移除
                table.blockSignals(True)
                for r in rows_without_id:
                    table.removeRow(r)
                table.blockSignals(False)
                
                # 清除选中状态
                table.clearSelection()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"删除失败: {e}")
        return delete_selected_rows

    def _create_add_blank_row_handler(self, table, editable_columns=None, node_type=None):
        """创建通用的添加空白行处理器"""
        def add_blank_row():
            # 检查目标节点的单目标模式限制
            if node_type == 'target' and not self.multi_target_mode and len(self.target_nodes) >= 1:
                self._show_message('warning', "添加限制", "单目标模式下只能添加一个目标节点，请先切换到多目标模式")
                return
            
            r = table.rowCount()
            table.blockSignals(True)
            table.insertRow(r)
            for c in range(table.columnCount()):
                item = QtWidgets.QTableWidgetItem('')
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if node_type == 'ammo' and c == 0:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    item.setBackground(QtCore.Qt.lightGray)
                elif editable_columns is not None:
                    if c in editable_columns:
                        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
                table.setItem(r, c, item)
            table.blockSignals(False)
        return add_blank_row

    def _create_standard_buttons(self, table, node_type, table_name):
        """创建标准的按钮组（新增行、删除行）"""
        buttons = {}
        
        # 新增一行按钮
        buttons['add'] = QtWidgets.QPushButton("新增一行")
        add_blank_row_handler = self._create_add_blank_row_handler(table, node_type=node_type)
        buttons['add'].clicked.connect(add_blank_row_handler)
        
        # 删除选中行按钮
        buttons['delete'] = QtWidgets.QPushButton("删除选中行")
        delete_handler = self._create_delete_handler(table, table_name, node_type)
        buttons['delete'].clicked.connect(delete_handler)
        
        return buttons

    def place_selected_nodes(self, table, node_type):
        """将选中的节点放置到坐标系中"""
        selected_rows = set()
        for item in table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QtWidgets.QMessageBox.warning(self, "警告", "请先选择要放置的节点")
            return
        
        def text_at(row, col):
            item = table.item(row, col)
            return item.text().strip() if item and item.text() else ''

        def float_at(row, col):
            txt = text_at(row, col)
            if txt == '':
                return 0.0
            try:
                return float(txt)
            except ValueError:
                return 0.0

        def int_at(row, col):
            txt = text_at(row, col)
            if txt == '':
                return 0
            try:
                return int(float(txt))
            except ValueError:
                return 0

        ammo_cache = {}

        def get_ammo_info(ammo_type):
            if ammo_type not in ammo_cache:
                ammo_cache[ammo_type] = self.ammo_service.get_by_type(ammo_type) if ammo_type else None
            return ammo_cache[ammo_type]

        placed = 0
        for row in sorted(selected_rows):
            try:
                node_id_text = text_at(row, 1)
                node_id = int(node_id_text) if node_id_text.isdigit() else placed + 1
                node_name = text_at(row, 2) or f"{node_type}_{node_id}"

                if node_type == 'recon':
                    model = text_at(row, 3)
                    parallel_limit = float_at(row, 4)
                    recon_distance = float_at(row, 5)
                    precision = float_at(row, 6)
                    processing_time = float_at(row, 7)
                    x = float_at(row, 8)
                    y = float_at(row, 9)
                    context = {
                        'model': model,
                        'parallel_limit': parallel_limit,
                        'recon_distance': recon_distance,
                        'precision': precision,
                        'processing_time': processing_time,
                        'x': x,
                        'y': y,
                        'h': float_at(row, 10),
                        'vx': float_at(row, 11),
                        'vy': float_at(row, 12),
                        'vh': float_at(row, 13),
                    }
                elif node_type == 'command':
                    command_capacity = float_at(row, 3)
                    comm_distance = float_at(row, 4)
                    processing_time = float_at(row, 5)
                    x = float_at(row, 6)
                    y = float_at(row, 7)
                    context = {
                        'command_capacity': command_capacity,
                        'comm_distance': comm_distance,
                        'processing_time': processing_time,
                        'x': x,
                        'y': y,
                        'h': float_at(row, 8),
                        'vx': float_at(row, 9),
                        'vy': float_at(row, 10),
                        'vh': float_at(row, 11),
                    }
                elif node_type == 'fire':
                    firepower_type = text_at(row, 3)
                    ammo_type = text_at(row, 4)
                    comm_distance = float_at(row, 5)
                    processing_time = float_at(row, 6)
                    x = float_at(row, 7)
                    y = float_at(row, 8)
                    ammo_info = get_ammo_info(ammo_type) or {}
                    context = {
                        'firepower_type': firepower_type,
                        'ammo_type': ammo_type,
                        'comm_distance': comm_distance,
                        'processing_time': processing_time,
                        'x': x,
                        'y': y,
                        'h': float_at(row, 9),
                        'vx': float_at(row, 10),
                        'vy': float_at(row, 11),
                        'vh': float_at(row, 12),
                        'effective_range': ammo_info.get('max_range', 50.0),
                        'effective_precision': ammo_info.get('precision_value', 0.1),
                        'effective_ammo_count': ammo_info.get('ammo_count', 10),
                        'effective_omega': ammo_info.get('conversion_coeff', 1.0),
                        'effective_flight_time': ammo_info.get('flight_time', 30.0),
                        'effective_cost': ammo_info.get('cost', 0.0),
                    }
                elif node_type == 'target':
                    target_type = text_at(row, 3)
                    threat_level = float_at(row, 4)
                    x = float_at(row, 5)
                    y = float_at(row, 6)
                    context = {
                        'target_type': target_type,
                        'threat_level': threat_level,
                        'x': x,
                        'y': y,
                        'h': float_at(row, 7),
                        'vx': float_at(row, 8),
                        'vy': float_at(row, 9),
                        'vh': float_at(row, 10),
                    }
                else:
                    continue

                node = self._create_node_object(node_type, node_id, node_name, context)
                self._add_node_to_list(node_type, node)
                placed += 1
            except Exception as e:
                self._show_message('warning', "警告", f"第{row+1}行节点数据处理失败: {e}")
                continue

        if placed:
            self.show_initial_nodes()
            node_type_names = {'recon': '侦察', 'command': '指挥', 'fire': '火力', 'target': '目标'}
            node_type_name = node_type_names.get(node_type, '未知')
            self._show_message('info', "成功", f"已放置 {placed} 个{node_type_name}节点到坐标系")
        else:
            self._show_message('warning', "提示", "未能放置任何节点，请检查数据。")

    

    def on_scheme_selected(self, scheme_id, scheme_name):
        """响应方案列表的选中事件，保存当前方案并刷新模式"""
        if not scheme_id:
            self.current_scheme_id = None
            return
        self.current_scheme_id = scheme_id
        self._apply_scheme_mode(scheme_id)

    

    

    def place_selected_target(self, table):
        """将选中的目标添加到画布目标节点列表"""
        selected_rows = set()
        for item in table.selectedItems():
            selected_rows.add(item.row())
        if not selected_rows:
            QtWidgets.QMessageBox.warning(self, "警告", "请先选择目标")
            return
        
        # 检查单目标模式限制
        if not self.multi_target_mode and len(self.target_nodes) >= 1:
            # 在单目标模式下，如果已有目标，先清空再添加新的
            self.target_nodes.clear()
        
        try:
            # 在单目标模式下，只处理第一个选中的节点
            rows_to_process = sorted(selected_rows)
            if not self.multi_target_mode:
                rows_to_process = rows_to_process[:1]  # 只取第一个选中的行
            
            for row in rows_to_process:
                node_id = int(table.item(row, 0).text())
                node_name = table.item(row, 1).text()
                target_type = table.item(row, 2).text()
                threat_level = int(table.item(row, 3).text())
                x = float(table.item(row, 4).text())
                y = float(table.item(row, 5).text())
                
                # 检查是否已存在
                target_exists = any(t['id'] == f't{node_id}' for t in self.target_nodes)
                if not target_exists:
                    self.target_nodes.append({
                        'id': f't{node_id}',
                        'name': node_name,
                        'type': target_type,
                        'threat_level': threat_level,
                        'coord': (x, y)
                    })
            
            self.current_result = None
            self.show_initial_nodes()
            
            if self.multi_target_mode:
                QtWidgets.QMessageBox.information(self, "成功", f"已添加 {len(rows_to_process)} 个目标到画布")
            else:
                QtWidgets.QMessageBox.information(self, "成功", f"已设置目标（单目标模式，只显示第一个选中的节点）")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"放置目标失败: {e}")

    

    def get_all_targets(self):
        """获取所有目标节点"""
        if self.current_scheme_id is None:
            return {}

        columns = ['node_id', 'node_name', 'target_type', 'threat_level', 'x', 'y', 'h', 'vx', 'vy', 'vh']
        try:
            rows = self.node_service.fetch_raw_nodes('target_nodes', columns, self.current_scheme_id)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "数据库错误", f"获取目标节点失败: {e}")
            return {}

        targets = {}
        for row in rows:
            node_id, node_name, target_type, threat_level, x, y, h, vx, vy, vh = row
            targets[f't{node_id}'] = {
                'id': f't{node_id}',
                'name': node_name,
                'type': target_type,
                'threat_level': threat_level,
                'coord': (x, y),
                'h': h,
                'vx': vx,
                'vy': vy,
                'vh': vh
            }
        return targets

    def get_fire_target_preference_table(self):
        """获取弹目偏好表"""
        try:
            rows = self.node_service.fetch_fire_target_preferences()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "数据库错误", f"获取弹目偏好表失败: {e}")
            return {}

        preference_table = {}
        for fire_type, target_type, preference_rank in rows:
            preference_table[(fire_type, target_type)] = preference_rank
        return preference_table

    def run_mopso_multi_target(self):
        """运行MOPSO多目标SSL优化（简化版）"""
        try:
            # 检查是否为多目标模式
            if not self.multi_target_mode:
                QtWidgets.QMessageBox.warning(self, "错误", '单目标模式下请使用"遍历搜索"或"粒子群算法"按钮')
                return
            
            # 获取所有目标节点
            all_targets = self.get_all_targets()
            if not all_targets:
                QtWidgets.QMessageBox.warning(self, "提示", '请先选择包含多个目标节点的方案并点击"放置"')
                return
            self._last_multi_targets = all_targets
            
            # 获取节点配置
            nodes = self.get_nodes_dict()
            
            # 获取弹目偏好表
            preference_table = self.get_fire_target_preference_table()
            
            # 运行MOPSO优化（使用预设参数）
            print("\n" + "="*60)
            print("开始MOPSO多目标优化（两层层次化帕累托）...")
            print("="*60)
            
            # 预设参数（根据目标数量自适应调整）
            num_targets = len(all_targets)
            if num_targets <= 20:
                num_particles = 50
                max_iterations = 100
            elif num_targets <= 40:
                num_particles = 60
                max_iterations = 80
            else:
                num_particles = 80
                max_iterations = 60
            
            print(f"目标数量: {num_targets}")
            print(f"粒子数量: {num_particles}")
            print(f"迭代次数: {max_iterations}")
            print(f"优化模式: 两层层次化（第一层优先最大化分配目标数）")
            print("请稍候...\n")
            
            self.current_result = self.algorithm_service.run_mopso_multi_target(
                all_targets,
                nodes,
                preference_table,
                num_particles=num_particles,
                max_iterations=max_iterations,
                archive_size=50,
                random_seed=42,
                use_hierarchical=True,
            )
            self._render_multi_target_allocation_on_canvas()
            
            # 显示结果（简化版）
            self.show_mopso_results_simple()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"MOPSO优化失败: {e}")
            import traceback
            traceback.print_exc()

    def show_mopso_results_simple(self):
        if self.current_result is None:
            return
        pareto_archive = self.current_result.get('pareto_archive', [])
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"{self.current_result['method_name']} - 结果")
        dlg.resize(1200, 700)
        layout = QtWidgets.QVBoxLayout(dlg)
        pareto_report = self.current_result.get('pareto_report')
        if pareto_report is not None and not pareto_report.empty:
            # 统计第一层方案数量
            first_layer_count = 0
            if '层级' in pareto_report.columns:
                first_layer_count = len(pareto_report[pareto_report['层级'].str.contains('第一层', na=False)])
            title_text = f"<h2>找到 {len(pareto_archive)} 个帕累托最优解</h2>"
            if first_layer_count > 0:
                title_text += f"<p style='color: #d4af37;'><b>第一层（分配目标数最优）方案：{first_layer_count} 个（已用黄色背景标识）</b></p>"
            title_label = QtWidgets.QLabel(title_text)
            title_label.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(title_label)
            table = self._create_dataframe_table(pareto_report)
            layout.addWidget(table)

            def on_selection_changed():
                row = table.currentRow()
                if row >= 0:
                    self._preview_pareto_solution(row)

            table.itemSelectionChanged.connect(on_selection_changed)

            def on_cell_double_clicked(row, col):
                self.show_mopso_results(row)

            table.cellDoubleClicked.connect(on_cell_double_clicked)

            if table.rowCount() > 0:
                table.selectRow(0)
                self._preview_pareto_solution(0)
        else:
            title_label = QtWidgets.QLabel(f"<h2>找到 {len(pareto_archive)} 个帕累托最优解</h2>")
            title_label.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(title_label)
            layout.addWidget(QtWidgets.QLabel("无帕累托解"))
        button_layout = QtWidgets.QHBoxLayout()
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        self._dock_secondary_dialog_left(dlg)
        dlg.exec_()

    def show_mopso_results(self, row_idx=None):
        if self.current_result is None:
            return
        pareto_solutions = self.current_result.get('pareto_solutions', None)  # solution结构
        pareto_report = self.current_result.get('pareto_report')
        pareto_archive = self.current_result.get('pareto_archive', [])  # 提前获取pareto_archive
        if row_idx is None or pareto_report is None or row_idx >= len(pareto_report):
            QtWidgets.QMessageBox.warning(self, "提示", "未选中帕累托解")
            return
        # 方法1：直接用pareto_solutions[row_idx]
        # 方法2：如果pareto_solutions没有，对应evaluation/redundancy等按行号查找或用self.current_result["pareto_eval_list"][row_idx]这样类似结构，具体按算法返回契约
        solution_detail = None
        selected_allocation = None
        if pareto_solutions and row_idx < len(pareto_solutions):
            solution_detail = pareto_solutions[row_idx]
            selected_allocation = solution_detail.get('final_allocation')
        else:
            # fallback, 容错
            solution_detail = None
        
        # 如果solution_detail中没有allocation_report，尝试从pareto_archive中获取并生成
        report = solution_detail.get('allocation_report', []) if solution_detail else []
        report = self._filter_successful_allocation_rows(report)
        if not report:
            # 尝试从pareto_archive中获取allocation并重新生成报告
            pareto_archive = self.current_result.get('pareto_archive', [])
            if pareto_archive and row_idx < len(pareto_archive):
                try:
                    entry = pareto_archive[row_idx]
                    # 结构 (objectives, allocation, position)
                    if len(entry) >= 2:
                        _, final_allocation, _ = entry[:3] if len(entry) >= 3 else (None, entry[1] if len(entry) >= 2 else None, None)
                        if final_allocation:
                            selected_allocation = final_allocation
                            # 获取nodes和targets
                            try:
                                # 构建nodes字典（支持多目标模式）
                                nodes = {
                                    'recon': {f'o{i+1}': node for i, node in enumerate(self.recon_nodes)},
                                    'command': {f'c{i+1}': node for i, node in enumerate(self.command_nodes)},
                                    'fire': {f'w{i+1}': node for i, node in enumerate(self.fire_nodes)}
                                }
                                # 获取targets（多目标模式）
                                targets = self.get_all_targets()
                                if nodes and targets:
                                    try:
                                        report = self.algorithm_service.generate_allocation_report(
                                            final_allocation, nodes, targets, None
                                        )
                                        report = self._filter_successful_allocation_rows(report)
                                        # 更新solution_detail
                                        if solution_detail is None:
                                            solution_detail = {}
                                        solution_detail['allocation_report'] = report
                                        solution_detail['final_allocation'] = final_allocation
                                    except Exception as e:
                                        print(f"生成分配报告失败: {e}")
                                        import traceback
                                        traceback.print_exc()
                            except Exception as e:
                                print(f"获取nodes或targets失败: {e}")
                                import traceback
                                traceback.print_exc()
                except Exception as e:
                    print(f"从pareto_archive提取数据失败: {e}")
                    import traceback
                    traceback.print_exc()
        
        if selected_allocation:
            self._render_multi_target_allocation(selected_allocation)

        # 假定 solution_detail = { 'allocation_report':..., 'evaluation':..., 'redundancy_matrix':... }，兼容无/部分缺失
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"详细结果 - 帕累托解{row_idx+1}")
        dlg.resize(1200, 800)
        layout = QtWidgets.QVBoxLayout(dlg)
        tabs = QtWidgets.QTabWidget()
        layout.addWidget(tabs)
        # 分配方案Tab
        allocation_widget = QtWidgets.QWidget()
        allocation_layout = QtWidgets.QVBoxLayout(allocation_widget)
        allocation_populated = False
        if report:
            # 显示完整的分配报告，包括所有状态的链
            all_rows = []
            for row in report:
                # 保留所有行，包括分组标题
                all_rows.append(row)
            
            if all_rows:
                # 获取所有可能的表头（从第一行非标题行获取）
                headers = None
                for row in all_rows:
                    if not str(row.get('目标ID', '')).startswith('==='):
                        headers = list(row.keys())
                        break
                
                if headers:
                    # 创建表格
                    table = QtWidgets.QTableWidget()
                    table.setColumnCount(len(headers))
                    table.setHorizontalHeaderLabels(headers)
                    table.setRowCount(len(all_rows))
                    
                    for r, row_data in enumerate(all_rows):
                        for c, header in enumerate(headers):
                            val = row_data.get(header, '')
                            item = QtWidgets.QTableWidgetItem(str(val))
                            item.setTextAlignment(QtCore.Qt.AlignCenter)
                            
                            # 如果是分组标题行，设置特殊样式
                            if str(row_data.get('目标ID', '')).startswith('==='):
                                item.setBackground(QtGui.QColor(220, 220, 220))
                                font = item.font()
                                font.setBold(True)
                                item.setFont(font)
                            table.setItem(r, c, item)
                    table.resizeColumnsToContents()
                    table.resizeRowsToContents()
                    allocation_layout.addWidget(table)
                    allocation_populated = True
        if not allocation_populated:
            allocation_layout.addWidget(QtWidgets.QLabel("无分配方案数据"))
        tabs.addTab(allocation_widget, "分配方案")
        # 评估指标Tab
        eval_widget = QtWidgets.QWidget()
        eval_layout = QtWidgets.QVBoxLayout(eval_widget)
        eval_data = solution_detail.get('evaluation', None) if solution_detail else None
        
        # 调试信息：输出数据结构（简化输出，避免打印大对象导致卡死）
        print(f"\n[调试] show_mopso_results - row_idx={row_idx}")
        print(f"[调试] pareto_solutions存在: {pareto_solutions is not None}")
        if pareto_solutions:
            print(f"[调试] pareto_solutions长度: {len(pareto_solutions)}")
        print(f"[调试] solution_detail存在: {solution_detail is not None}")
        if solution_detail:
            print(f"[调试] solution_detail键: {list(solution_detail.keys())}")
            print(f"[调试] evaluation存在: {'evaluation' in solution_detail}")
            if 'evaluation' in solution_detail:
                eval_val = solution_detail.get('evaluation')
                if isinstance(eval_val, dict):
                    print(f"[调试] evaluation类型: dict, 键数量: {len(eval_val)}, 键: {list(eval_val.keys())[:10]}")  # 只显示前10个键
                else:
                    print(f"[调试] evaluation类型: {type(eval_val)}")
        
        # 如果solution_detail中没有evaluation，尝试从pareto_archive重新计算（简化版，不生成all_feasible_chains避免卡死）
        if not eval_data and pareto_archive and row_idx < len(pareto_archive):
            try:
                entry = pareto_archive[row_idx]
                if len(entry) >= 2:
                    _, final_allocation, _ = entry[:3] if len(entry) >= 3 else (None, entry[1] if len(entry) >= 2 else None, None)
                    if final_allocation:
                        if not selected_allocation:
                            selected_allocation = final_allocation
                        try:
                            # 获取nodes和targets
                            nodes = {
                                'recon': {f'o{i+1}': node for i, node in enumerate(self.recon_nodes)},
                                'command': {f'c{i+1}': node for i, node in enumerate(self.command_nodes)},
                                'fire': {f'w{i+1}': node for i, node in enumerate(self.fire_nodes)}
                            }
                            targets = self.get_all_targets()
                            if nodes and targets:
                                # 不传递all_feasible_chains参数（传None），避免耗时计算导致UI卡死
                                eval_data = self.algorithm_service.calculate_multi_target_metrics(
                                    final_allocation, nodes, targets, None
                                )
                                # 更新solution_detail
                                if solution_detail is None:
                                    solution_detail = {}
                                solution_detail['evaluation'] = eval_data
                                print(f"[调试] 从pareto_archive重新计算evaluation成功")
                        except Exception as e:
                            print(f"[调试] 重新计算evaluation失败: {e}")
                            import traceback
                            traceback.print_exc()
            except Exception as e:
                print(f"[调试] 从pareto_archive提取数据失败: {e}")
        
        if eval_data and isinstance(eval_data, dict) and len(eval_data) > 0:
            # 按照多目标SSL构建的评估指标格式显示
            evaluation = eval_data  # 使用evaluation作为变量名，与show_multi_target_results保持一致
            # 创建评估指标表格（分为基础指标和综合指标两部分）
            metrics_data = [
                ['=== 基础指标 ===', ''],
                ['总目标数', evaluation.get('total_targets', 0)],
                ['已分配目标数', evaluation.get('allocated_targets', 0)],
                ['分配率', f"{evaluation.get('allocation_rate', 0):.2%}"],
                ['总火力能力', f"{evaluation.get('total_fire_power', 0):.2f}"],
                ['平均反应时间(s)', f"{evaluation.get('avg_reaction_time', 0):.2f}"],
                ['平均打击精度(σ²)', f"{evaluation.get('avg_precision', 0):.2f}"],
                ['平均链路曲折度', f"{evaluation.get('avg_tortuosity', 0):.2f}"],
                ['平均链路交叉数', f"{evaluation.get('avg_cross_count', 0):.2f}"],
                ['总体方案曲折度', f"{evaluation.get('overall_plan_tortuosity', 0):.2f}"],
                ['方案链间交叉数', evaluation.get('inter_chain_crossings', 0)],
                ['存在交叉链比例', f"{evaluation.get('crossing_chain_ratio', 0):.2%}"],
                ['火力利用率', f"{evaluation.get('fire_utilization', 0):.2%}"],
            ]
            
            # 添加侦察节点利用率
            metrics_data.append(['=== 侦察节点利用率 ===', ''])
            metrics_data.append(['整体侦察利用率', f"{evaluation.get('avg_recon_utilization', 0):.2%}"])
            recon_util = evaluation.get('recon_utilization', {})
            for recon_id, recon_data in sorted(recon_util.items()):
                if isinstance(recon_data, dict):
                    metrics_data.append([
                        f'{recon_id}', 
                        f"{recon_data.get('used', 0)}/{recon_data.get('parallel_limit', 0)} ({recon_data.get('utilization', 0):.1%})"
                    ])
                else:
                    # 兼容旧版本格式（如果存在）
                    metrics_data.append([f'{recon_id}利用率', f"{recon_data:.2%}"])
            
            # 添加指挥节点利用率
            metrics_data.append(['=== 指挥节点利用率 ===', ''])
            metrics_data.append(['整体指挥利用率', f"{evaluation.get('avg_command_utilization', 0):.2%}"])
            command_util = evaluation.get('command_utilization', {})
            for cmd_id, cmd_data in sorted(command_util.items()):
                if isinstance(cmd_data, dict):
                    metrics_data.append([
                        f'{cmd_id}', 
                        f"{cmd_data.get('used', 0)}/{cmd_data.get('capacity', 0)} ({cmd_data.get('utilization', 0):.1%})"
                    ])
            
            # 添加综合性指标
            metrics_data.append(['=== 综合性指标 ===', ''])
            metrics_data.append(['火力交叉覆盖度', f"{evaluation.get('fire_cross_coverage', 0):.2f}"])
            metrics_data.append(['平均目标火力覆盖数', f"{evaluation.get('avg_target_coverage', 0):.2f}"])
            metrics_data.append(['威胁度总和', f"{evaluation.get('total_threat_value', 0):.2f}"])
            metrics_data.append(['总成本', f"{evaluation.get('total_cost', 0):.2f}"])
            metrics_data.append(['平均成本/目标', f"{evaluation.get('avg_cost_per_target', 0):.2f}"])
            metrics_data.append(['成本效能(威胁度/成本)', f"{evaluation.get('cost_efficiency', 0):.4f}"])
            
            # 添加未分配目标
            unallocated = evaluation.get('unallocated_targets', [])
            if unallocated:
                metrics_data.append(['=== 未分配信息 ===', ''])
                metrics_data.append(['未分配目标', ', '.join(unallocated)])
            
            metrics_table = QtWidgets.QTableWidget()
            metrics_table.setColumnCount(2)
            metrics_table.setHorizontalHeaderLabels(['指标', '数值'])
            metrics_table.setRowCount(len(metrics_data))
            
            for r, (metric, value) in enumerate(metrics_data):
                metrics_table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(metric)))
                metrics_table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(value)))
                metrics_table.item(r, 0).setTextAlignment(QtCore.Qt.AlignCenter)
                metrics_table.item(r, 1).setTextAlignment(QtCore.Qt.AlignCenter)
            
            metrics_table.resizeColumnsToContents()
            metrics_table.resizeRowsToContents()
            metrics_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            eval_layout.addWidget(metrics_table)
        else:
            # 显示更详细的错误信息
            error_msg = "无评估数据"
            if eval_data is None:
                error_msg += "\n（eval_data为None）"
            elif not isinstance(eval_data, dict):
                error_msg += f"\n（eval_data类型错误: {type(eval_data)}）"
            elif len(eval_data) == 0:
                error_msg += "\n（eval_data为空字典）"
            eval_layout.addWidget(QtWidgets.QLabel(error_msg))
        tabs.addTab(eval_widget, "评估指标")
        # 冗余度矩阵功能已移除（仅用于多目标MOPSO优化）
        # 关闭按钮
        button_layout = QtWidgets.QHBoxLayout()
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        self._dock_secondary_dialog_left(dlg)
        dlg.exec_()

    def _create_dataframe_table(self, df):
        """从DataFrame创建表格"""
        table = QtWidgets.QTableWidget()
        
        # 如果包含"层级"列，将其移到前面
        if '层级' in df.columns:
            cols = df.columns.tolist()
            cols.remove('层级')
            cols.insert(1, '层级')  # 将层级列放在方案编号之后
            df = df[cols]
        
        table.setColumnCount(len(df.columns))
        table.setHorizontalHeaderLabels(df.columns.tolist())
        table.setRowCount(len(df))
        
        for r in range(len(df)):
            # 检查是否为第一层方案（分配目标数最优）
            is_first_layer = False
            if '层级' in df.columns:
                layer_value = df.iloc[r, df.columns.get_loc('层级')]
                is_first_layer = '第一层' in str(layer_value)
            
            for c in range(len(df.columns)):
                value = df.iloc[r, c]
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                
                # 为第一层方案设置背景颜色（浅黄色突出显示）
                if is_first_layer:
                    item.setBackground(QtGui.QColor(255, 255, 200))  # 浅黄色背景
                
                table.setItem(r, c, item)
        
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        
        return table
