"""画布绘制相关的视图逻辑。"""
from typing import Dict, List


class PlotView:
    """负责节点分布与结果示意图的绘制。"""

    def __init__(self, canvas, xlim, ylim):
        self.canvas = canvas
        self.ax = canvas.ax
        self.xlim = xlim
        self.ylim = ylim

    def attach_canvas(self, canvas):
        """切换绘制所使用的画布。"""
        self.canvas = canvas
        self.ax = canvas.ax

    @staticmethod
    def _safe_coord(coord):
        """将坐标元组安全转换为浮点值，非法数据返回None。"""
        if not coord or len(coord) < 2:
            return None
        try:
            x = float(coord[0])
            y = float(coord[1])
        except (TypeError, ValueError):
            return None
        if x != x or y != y:  # NaN 检查
            return None
        return x, y

    def _setup_axes(self, title: str):
        """统一设置坐标轴、网格与图例，保持主界面和弹窗显示风格一致。"""
        ax = self.ax
        ax.set_xlim(*self.xlim)
        ax.set_ylim(*self.ylim)
        ax.set_xlabel('X坐标(km)')
        ax.set_ylabel('Y坐标(km)')
        ax.grid(True, linestyle='--', alpha=0.7)
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        if by_label:  # 没有图例项时不绘制，避免出现空白小方块
            ax.legend(by_label.values(), by_label.keys(), loc='best', fontsize=8)
        ax.set_title(title)

    def render_nodes(self, node_lists: Dict[str, List[dict]], multi_target_mode: bool):
        """绘制当前节点分布。"""
        targets = node_lists.get('target', [])
        recon_nodes = node_lists.get('recon', [])
        command_nodes = node_lists.get('command', [])
        fire_nodes = node_lists.get('fire', [])

        self.ax.clear()

        targets_to_show = targets if multi_target_mode else targets[:1] or []
        for idx, target in enumerate(targets_to_show):
            coord = self._safe_coord(target.get('coord'))
            if coord is None:
                continue
            tx, ty = coord
            self.ax.scatter(tx, ty, color='blue', marker='o', s=200,
                            label='目标节点' if idx == 0 else "")
            self.ax.annotate(f'目标 t{idx+1}\n({tx:.2f},{ty:.2f})', (tx + 0.3, ty + 0.3), fontsize=10)

        self._scatter_nodes(recon_nodes, 'green', '^', '侦察节点', prefix='o')
        self._scatter_nodes(command_nodes, 'yellow', 's', '指挥节点', prefix='c')
        self._scatter_nodes(fire_nodes, 'purple', '*', '火力节点', prefix='w')

        self._setup_axes('节点分布图')
        self.canvas.draw()

    def render_result(self, nodes: Dict[str, dict], result: dict, show_optimal: bool = False):
        """绘制单目标结果示意图，可选显示指标优选链。"""
        self.ax.clear()
        try:
            tx, ty = nodes['target']
            self.ax.scatter(tx, ty, color='blue', marker='o', s=200, label='目标节点')
            self.ax.annotate(f'目标 t1\n({tx:.2f},{ty:.2f})', (tx + 0.3, ty + 0.3), fontsize=10)
        except KeyError:
            return

        self._scatter_dict(nodes['recon'], 'green', '^', '侦察节点')
        self._scatter_dict(nodes['command'], 'yellow', 's', '指挥节点')
        self._scatter_dict(nodes['fire'], 'purple', '*', '火力节点')

        df_eval = result.get('evaluation')
        if show_optimal and df_eval is not None and not df_eval.empty:
            kill_chains = result.get('kill_chains', [])
            self._highlight_optimal_chains(nodes, kill_chains, df_eval, tx, ty)

        self._setup_axes('结果示意图')
        self.canvas.draw()

    def draw_single_chain(self, nodes: Dict[str, dict], chain, color='blue', label='当前链'):
        try:
            tx, ty = nodes['target']
        except KeyError:
            return
        if not chain or len(chain) != 3:
            return
        recon_id, command_id, fire_id = chain
        if recon_id not in nodes['recon'] or command_id not in nodes['command'] or fire_id not in nodes['fire']:
            return
        self._plot_chain(nodes, chain, tx, ty, color=color, linewidth=2.5, label=label)
        self._setup_axes('结果示意图')
        self.canvas.draw()

    def render_multi_target_result(self, targets: Dict[str, dict], nodes: Dict[str, dict], allocation: Dict[str, dict]):
        """绘制多目标分配结果."""
        self.ax.clear()
        targets = targets or {}
        allocation = allocation or {}

        recon_nodes = nodes.get('recon', {})
        command_nodes = nodes.get('command', {})
        fire_nodes = nodes.get('fire', {})

        self._scatter_dict(recon_nodes, 'green', '^', '侦察节点')
        self._scatter_dict(command_nodes, 'yellow', 's', '指挥节点')
        self._scatter_dict(fire_nodes, 'purple', '*', '火力节点')

        allocated_label_used = False
        pending_label_used = False
        for target_id, target in targets.items():
            coord = self._safe_coord(target.get('coord'))
            if coord is None:
                continue
            tx, ty = coord
            allocated = target_id in allocation
            color = 'blue' if allocated else 'red'
            label = ''
            if allocated and not allocated_label_used:
                label = '已分配目标'
                allocated_label_used = True
            elif not allocated and not pending_label_used:
                label = '未分配目标'
                pending_label_used = True
            self.ax.scatter(tx, ty, color=color, marker='o', s=180, label=label)
            tag = target.get('name', target_id)
            self.ax.annotate(f'{tag}\n({tx:.2f},{ty:.2f})', (tx + 0.3, ty + 0.3), fontsize=10)

        palette = [
            '#e67e22', '#2980b9', '#27ae60', '#c0392b',
            '#8e44ad', '#d35400', '#16a085', '#2c3e50'
        ]
        for idx, (target_id, chain) in enumerate(allocation.items()):
            target = targets.get(target_id)
            if not target:
                continue
            recon = recon_nodes.get(chain['recon_id'])
            command = command_nodes.get(chain['command_id'])
            fire = fire_nodes.get(chain['fire_id'])
            if not recon or not command or not fire:
                continue
            target_coord = self._safe_coord(target.get('coord'))
            recon_coord = self._safe_coord(recon.get('coord')) if recon else None
            command_coord = self._safe_coord(command.get('coord')) if command else None
            fire_coord = self._safe_coord(fire.get('coord')) if fire else None
            if not all((target_coord, recon_coord, command_coord, fire_coord)):
                continue
            tx, ty = target_coord
            rx, ry = recon_coord
            cx, cy = command_coord
            fx, fy = fire_coord
            color = palette[idx % len(palette)]
            label = f'链 {idx+1}'
            self.ax.plot([tx, rx, cx, fx], [ty, ry, cy, fy],
                         color=color, linewidth=2, alpha=0.9, label=label)

        self._setup_axes('多目标分配结果')
        self.canvas.draw()

    def _scatter_nodes(self, nodes: List[dict], color, marker, label, prefix):
        """绘制列表形式的节点（供主界面缓存使用），并显示名称与坐标。"""
        for idx, node in enumerate(nodes):
            coord = self._safe_coord(node.get('coord'))
            if coord is None:
                continue
            x, y = coord
            text = f"{node.get('model', f'{prefix}{idx+1}')} - {node.get('name', f'{prefix}{idx+1}')}"
            self.ax.scatter(x, y, color=color, marker=marker, s=150,
                            label=label if idx == 0 else "")
            self.ax.annotate(f'{text}\n({x:.2f},{y:.2f})', (x + 0.3, y + 0.3), fontsize=10)

    def _scatter_dict(self, nodes: Dict[str, dict], color, marker, label):
        """绘制 dict 形式的节点（算法结果通常使用该格式）。"""
        for idx, (key, data) in enumerate(nodes.items()):
            coord = self._safe_coord(data.get('coord'))
            if coord is None:
                continue
            x, y = coord
            text = data.get('model', key)
            self.ax.scatter(x, y, color=color, marker=marker, s=150,
                            label=label if idx == 0 else "")
            self.ax.annotate(f'{text}\n({x:.2f},{y:.2f})', (x + 0.3, y + 0.3), fontsize=10)

    def _plot_chain(self, nodes, chain, tx, ty, **plot_kwargs):
        """按照 t -> o -> c -> w 的顺序连线，用于突出单条链。"""
        o, c, w = chain
        ox, oy = nodes['recon'][o]['coord']
        cx, cy = nodes['command'][c]['coord']
        wx, wy = nodes['fire'][w]['coord']
        self.ax.plot([tx, ox, cx, wx], [ty, oy, cy, wy], **plot_kwargs)

    def _highlight_optimal_chains(self, nodes, kill_chains, df_eval, tx, ty):
        if not kill_chains or df_eval.empty:
            return
        def _plot_if_valid(idx, color, desc):
            if idx is None or idx < 0 or idx >= len(kill_chains):
                return
            label = f'{desc} (L{idx+1})'
            self._plot_chain(nodes, kill_chains[idx], tx, ty, color=color, linewidth=3, label=label)

        # 优先依据“指标优选”列来确定需要高亮的链路，确保与表格展示一致。
        if '指标优选' in df_eval.columns:
            tag_series = df_eval['指标优选'].astype(str)
            tag_definitions = [
                ('时间最优', 'gold', '时间最优链'),
                ('精度最优', 'green', '精度最优链'),
                ('火力最优', 'purple', '火力最优链'),
                ('成本最优', '#e67e22', '成本最优链'),
                ('匹配度最优', '#1f8ef1', '匹配度最优链'),
            ]
            for keyword, color, desc in tag_definitions:
                matched = tag_series[tag_series.str.contains(keyword, na=False)].index
                if len(matched) == 0:
                    continue
                _plot_if_valid(matched[0], color, desc)
            return

        # 兼容无“指标优选”列的旧数据：回退到单指标极值高亮。
        min_time_idx = df_eval['反应时间(s)'].idxmin()
        min_sigma_idx = df_eval['打击精度(σ²)'].idxmin()
        max_fire_idx = df_eval['火力打击能力'].idxmax()
        highlights = [
            (min_time_idx, 'yellow', '时间最优链'),
            (min_sigma_idx, 'green', '精度最优链'),
            (max_fire_idx, 'purple', '火力最优链'),
        ]
        for idx, color, desc in highlights:
            _plot_if_valid(idx, color, desc)
