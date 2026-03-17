# -*- coding: utf-8 -*-
"""
单目标杀伤链搜索算法集合。

包含：
- 穷举遍历（loop_method）
- 粒子群（pso_method）
并提供大量几何与指标计算辅助函数。

支持动目标：通过 time_elapsed 参数实现目标位置随时间更新
"""
import numpy as np
import pandas as pd
from math import sqrt
from typing import Dict, List, Tuple, Any, Optional

from .moving_target import (
    is_movable_target,
    update_target_position,
    calculate_moving_position,
    has_movable_targets,
)


# PSO 适应度函数权重常量（多目标加权系数）
PSO_WEIGHT_TIME = 0.375      # 时间权重
PSO_WEIGHT_SIGMA = 0.3125    # 精度权重
PSO_WEIGHT_FIRE = 0.3125     # 火力权重


def distance(p1, p2):
    """计算两点之间的欧氏距离"""
    return sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def _redundancy(chain1, chain2):
    """计算两条链的冗余度（不同节点的比例）"""
    return round(sum(1 for a, b in zip(chain1, chain2) if a != b) / 3, 2)


def _orientation(p, q, r):
    """计算向量叉乘符号，用于判断端点方位。"""
    val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    if abs(val) < 1e-9:
        return 0
    return 1 if val > 0 else 2


def _on_segment(p, q, r):
    """判断点 q 是否位于线段 pr 上，用于处理共线边界的交叉判定。"""
    return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])


def _segments_strictly_intersect(p1, p2, p3, p4):
    """判断两线段是否发生非端点交叉。"""
    shared = {tuple(p1), tuple(p2)} & {tuple(p3), tuple(p4)}
    if shared:
        return False
    o1 = _orientation(p1, p2, p3)
    o2 = _orientation(p1, p2, p4)
    o3 = _orientation(p3, p4, p1)
    o4 = _orientation(p3, p4, p2)

    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and _on_segment(p1, p3, p2):
        return True
    if o2 == 0 and _on_segment(p1, p4, p2):
        return True
    if o3 == 0 and _on_segment(p3, p1, p4):
        return True
    if o4 == 0 and _on_segment(p3, p2, p4):
        return True
    return False


def _calculate_chain_shape_metrics(target_coord, recon_coord, command_coord, fire_coord):
    """
    计算链路曲折度与交叉度。
    曲折度采用交通网络常见定义（见例如 Transportation Research, 27A(2), 1993）：
    τ = 实际路径长度 / 起终点直线距离。
    """
    d_target_recon = distance(target_coord, recon_coord)
    d_recon_command = distance(recon_coord, command_coord)
    d_command_fire = distance(command_coord, fire_coord)
    open_length = d_target_recon + d_recon_command + d_command_fire
    direct_distance = distance(target_coord, fire_coord)
    tortuosity = open_length / direct_distance if direct_distance > 0 else 0.0

    crossing = 1 if _segments_strictly_intersect(target_coord, recon_coord, command_coord, fire_coord) else 0
    return tortuosity, crossing


def _build_reachability_matrix(all_nodes: List[str], nodes: Dict[str, Any]) -> np.ndarray:
    """
    基于坐标计算节点可达性矩阵。

    返回一个 0/1 矩阵，行列均为 all_nodes 中的节点 id，值为 1 代表连通。
    该矩阵用于 loop_method 中评估可行链组合。
    """
    reachability_matrix = np.zeros((len(all_nodes), len(all_nodes)), dtype=int)
    for i, node1 in enumerate(all_nodes):
        for j, node2 in enumerate(all_nodes):
            if node1 == node2:
                reachability_matrix[i, j] = 0
                continue
            if node1 == 't1' and node2 in nodes['recon']:
                d = distance(nodes['target'], nodes['recon'][node2]['coord'])
                reachability_matrix[i, j] = 1 if d <= nodes['recon'][node2]['range'] else 0
            elif node1 in nodes['recon'] and node2 in nodes['command']:
                d = distance(nodes['recon'][node1]['coord'], nodes['command'][node2]['coord'])
                reachability_matrix[i, j] = 1 if d <= nodes['command'][node2]['range'] else 0
            elif node1 in nodes['command'] and node2 in nodes['fire']:
                d = distance(nodes['command'][node1]['coord'], nodes['fire'][node2]['coord'])
                reachability_matrix[i, j] = 1 if d <= nodes['command'][node1]['range'] else 0
            elif node1 in nodes['fire'] and node2 == 't1':
                d = distance(nodes['fire'][node1]['coord'], nodes['target'])
                reachability_matrix[i, j] = 1 if d <= nodes['fire'][node1]['range'] else 0
    return reachability_matrix


def _is_dominated(solution1, solution2):
    """检查solution1是否被solution2支配"""
    # solution格式: (t_total, sigma2, -fire_power)
    # 注意fire_power取负值，因为我们要最大化火力
    return (all(s2 <= s1 for s1, s2 in zip(solution1, solution2)) and 
            any(s2 < s1 for s1, s2 in zip(solution1, solution2)))


def _extract_target_type(nodes: Dict[str, Any]):
    """从节点字典中提取目标类型（如果存在）。"""
    target_info = nodes.get('target_info') or nodes.get('target_meta') or {}
    if isinstance(nodes.get('target'), dict):
        # 兼容直接把目标字典放在 nodes['target'] 的情况
        target_info = {**target_info, **nodes['target']}
    return target_info.get('type')


def _normalize_preference_table(pref_raw: Any) -> Dict[Tuple[str, str], float]:
    """把多种格式的弹目偏好表统一为 {(fire_type, target_type): rank}。"""
    if not pref_raw:
        return {}
    if isinstance(pref_raw, dict):
        return {k: float(v) for k, v in pref_raw.items()}
    pref_dict: Dict[Tuple[str, str], float] = {}
    for item in pref_raw:
        if not item or len(item) < 3:
            continue
        fire_type, target_type, rank = item[0], item[1], item[2]
        pref_dict[(fire_type, target_type)] = float(rank)
    return pref_dict


def _compute_match_rank(fire_node: Dict[str, Any], target_type: Any, preference_table: Dict[Tuple[str, str], float], default_rank: float = 3.0) -> float:
    """根据弹目偏好返回匹配度的“等级”值（数值越小越匹配）。"""
    if not target_type:
        return default_rank
    fire_type = fire_node.get('firepower_type') or fire_node.get('model') or fire_node.get('ammo_type')
    if not fire_type:
        return default_rank
    return preference_table.get((fire_type, target_type), default_rank)


def _rank_to_match_score(rank: float) -> float:
    """把 1-4 的偏好等级转换成 0-10 的匹配度分值，便于展示。"""
    try:
        score = (4 - float(rank)) / 3 * 10
    except Exception:
        return 0.0
    return max(0.0, min(10.0, score))


def _find_pareto_front(kill_chains, nodes):
    """寻找帕累托最优解集"""
    pareto_front = []
    objectives_data = []
    preference_table = _normalize_preference_table(nodes.get('preference_table'))
    target_type = _extract_target_type(nodes)
    
    # 计算所有杀伤链的目标函数值
    for o, c, w in kill_chains:
        t_total = nodes['recon'][o]['t_deal'] + nodes['command'][c]['t_deal'] + nodes['fire'][w]['t_deal'] + nodes['fire'][w]['t_flight']
        sigma2 = nodes['recon'][o]['sigma2'] + nodes['fire'][w]['sigma2']
        fire_power = nodes['fire'][w]['ammo']['count'] * nodes['fire'][w]['ammo']['omega']
        ammo_cost = float(nodes['fire'][w]['ammo'].get('cost', 0) or 0)
        preference_rank = _compute_match_rank(nodes['fire'][w], target_type, preference_table)
        
        # 目标函数: [反应时间, 打击精度, 成本, 弹目匹配度(等级越小越好), -火力能力]
        objectives = [t_total, sigma2, ammo_cost, preference_rank, -fire_power]
        objectives_data.append((o, c, w, objectives))
    
    # 寻找帕累托最优解
    for i, (o, c, w, objectives) in enumerate(objectives_data):
        is_dominated = False
        for j, (o2, c2, w2, objectives2) in enumerate(objectives_data):
            if i != j and _is_dominated(objectives, objectives2):
                is_dominated = True
                break
        
        if not is_dominated:
            pareto_front.append((o, c, w, objectives))
    
    return pareto_front


def pso_method(all_nodes: List[str], nodes: Dict[str, Any]) -> Dict[str, Any]:
    """
    粒子群优化（PSO）版单目标搜索。

    思路：
        1. 把 (侦察, 指挥, 火力) 三元组映射为粒子坐标
        2. 通过多目标合成适应度值驱动粒子更新
        3. 直接基于粒子群收敛结果构建帕累托最优链（不再额外做邻域搜索）
    """
    reachability_matrix = _build_reachability_matrix(all_nodes, nodes)

    # PSO 参数：优先加速运行，牺牲部分覆盖度
    num_particles = 30  # 粒子数减小，单代评估量下降
    max_iterations = 30  # 迭代次数减半，加快结束
    w = 0.7  # 较小惯性配合线性衰减，加速收敛
    c1 = 1.5  # 个体学习保持
    c2 = 1.5  # 略弱的全局牵引，避免过早团聚

    recon_list = list(nodes['recon'].keys())
    command_list = list(nodes['command'].keys())
    fire_list = list(nodes['fire'].keys())

    preference_table = _normalize_preference_table(nodes.get('preference_table'))
    target_type = _extract_target_type(nodes)

    n_recon = len(recon_list)
    n_command = len(command_list)
    n_fire = len(fire_list)

    particles = []
    velocities = []
    personal_best_positions = []
    personal_best_fitness = []

    for _ in range(num_particles):
        position = [
            np.random.randint(0, n_recon),
            np.random.randint(0, n_command),
            np.random.randint(0, n_fire)
        ]
        particles.append(position)
        velocity = [
            np.random.uniform(-1, 1),
            np.random.uniform(-1, 1),
            np.random.uniform(-1, 1)
        ]
        velocities.append(velocity)
        personal_best_positions.append(position.copy())
        personal_best_fitness.append(float('inf'))

    global_best_position = None
    global_best_fitness = float('inf')

    kill_chains = []
    evaluated_chains = set()

    def fitness(position):
        """计算单条链的综合评价值，并把合法链保存到 kill_chains。"""
        o_idx, c_idx, w_idx = position
        o = recon_list[o_idx]
        c = command_list[c_idx]
        w = fire_list[w_idx]
        chain_key = (o, c, w)
        if chain_key in evaluated_chains:
            return float('inf')
        evaluated_chains.add(chain_key)
        
        # 距离约束检查（保持SSL部分不变）
        d_target_recon = distance(nodes['target'], nodes['recon'][o]['coord'])
        if d_target_recon > nodes['recon'][o]['range']:
            return 1000 + d_target_recon
        d_recon_command = distance(nodes['recon'][o]['coord'], nodes['command'][c]['coord'])
        if d_recon_command > nodes['command'][c]['range']:
            return 1000 + d_recon_command
        d_command_fire = distance(nodes['command'][c]['coord'], nodes['fire'][w]['coord'])
        if d_command_fire > nodes['command'][c]['range']:
            return 1000 + d_command_fire
        d_fire_target = distance(nodes['fire'][w]['coord'], nodes['target'])
        if d_fire_target > nodes['fire'][w]['range']:
            return 1000 + d_fire_target
        
        # 计算目标函数值（不进行加权和，保持原始值）
        t_total = nodes['recon'][o]['t_deal'] + nodes['command'][c]['t_deal'] + nodes['fire'][w]['t_deal'] + nodes['fire'][w]['t_flight']
        sigma2 = nodes['recon'][o]['sigma2'] + nodes['fire'][w]['sigma2']
        fire_power = nodes['fire'][w]['ammo']['count'] * nodes['fire'][w]['ammo']['omega']
        
        # 使用多目标适应度：返回一个综合指标用于PSO优化
        # 这里使用简单的加权和作为PSO的适应度，但后续会用帕累托方法重新评估
        normalized_time = t_total / 1000.0
        normalized_sigma = sigma2 / 50.0
        normalized_fire = (50.0 - fire_power) / 50.0
        # 权重重新归一化，移除链路长度影响
        fitness_value = (
            0.375 * normalized_time
            + 0.3125 * normalized_sigma
            + 0.3125 * normalized_fire
        )
        
        kill_chains.append((o, c, w))
        return fitness_value

    # PSO主循环
    for iteration in range(max_iterations):
        # 评估所有粒子的适应度
        for i in range(num_particles):
            current_fitness = fitness(particles[i])
            if current_fitness < personal_best_fitness[i]:
                personal_best_fitness[i] = current_fitness
                personal_best_positions[i] = particles[i].copy()
                if current_fitness < global_best_fitness:
                    global_best_fitness = current_fitness
                    global_best_position = particles[i].copy()
        # 更新粒子位置和速度
        for i in range(num_particles):
            for j in range(3):
                r1, r2 = np.random.random(), np.random.random()
                if global_best_position is not None:
                    # 动态调整惯性权重：随迭代进行逐渐减小，前期探索后期开发
                    dynamic_w = w * (1 - iteration / max_iterations)
                    velocities[i][j] = (
                        dynamic_w * velocities[i][j]
                        + c1 * r1 * (personal_best_positions[i][j] - particles[i][j])
                        + c2 * r2 * (global_best_position[j] - particles[i][j])
                    )
                    particles[i][j] = particles[i][j] + velocities[i][j]
                else:
                    velocities[i][j] = (
                        w * velocities[i][j]
                        + c1 * r1 * (personal_best_positions[i][j] - particles[i][j])
                    )
                    particles[i][j] = particles[i][j] + velocities[i][j]
                
                # 边界处理
                if j == 0:
                    particles[i][j] = max(0, min(n_recon - 1, int(particles[i][j])))
                elif j == 1:
                    particles[i][j] = max(0, min(n_command - 1, int(particles[i][j])))
                else:
                    particles[i][j] = max(0, min(n_fire - 1, int(particles[i][j])))

    # 去重
    kill_chains = list(set(kill_chains))
    print(f"PSO找到 {len(kill_chains)} 条可行链（未使用领域搜索补充）")
    
    # 寻找帕累托最优解集
    pareto_front = _find_pareto_front(kill_chains, nodes)
    
    # 构建评估表
    evaluation = []
    for idx, (o, c, w) in enumerate(kill_chains, 1):
        t_total = nodes['recon'][o]['t_deal'] + nodes['command'][c]['t_deal'] + nodes['fire'][w]['t_deal'] + nodes['fire'][w]['t_flight']
        sigma2 = nodes['recon'][o]['sigma2'] + nodes['fire'][w]['sigma2']
        fire_power = nodes['fire'][w]['ammo']['count'] * nodes['fire'][w]['ammo']['omega']
        ammo_cost = float(nodes['fire'][w]['ammo'].get('cost', 0) or 0)
        preference_rank = _compute_match_rank(nodes['fire'][w], target_type, preference_table)
        match_score = _rank_to_match_score(preference_rank)
        
        # 检查是否为帕累托最优解
        is_pareto = any((o, c, w) == (pf[0], pf[1], pf[2]) for pf in pareto_front)
        
        tortuosity, cross_count = _calculate_chain_shape_metrics(
            nodes['target'], nodes['recon'][o]['coord'], nodes['command'][c]['coord'], nodes['fire'][w]['coord']
        )
        evaluation.append({
            '编号': f'L{idx}', 
            '杀伤链': f"t1-{o}-{c}-{w}",
            '反应时间(s)': t_total, 
            '打击精度(σ²)': sigma2, 
            '火力打击能力': fire_power,
            '火力成本': ammo_cost,
            '弹目匹配度': round(match_score, 1),
            '链路曲折度': round(tortuosity, 2),
            '链路交叉数': cross_count,
            '帕累托最优': '是' if is_pareto else '否'
        })
    
    df_eval = pd.DataFrame(evaluation)

    # 指标优选标记（基于帕累托最优解集）
    if not df_eval.empty:
        df_eval['指标优选'] = ''

        def _append_opt_label(row_idx, label):
            """给同一条链叠加多个指标优选标签。"""
            if row_idx is None or pd.isna(row_idx):
                return
            existing = df_eval.at[row_idx, '指标优选']
            df_eval.at[row_idx, '指标优选'] = label if not existing else f"{existing} | {label}"
        
        # 在帕累托最优解中寻找各指标最优
        pareto_indices = df_eval[df_eval['帕累托最优'] == '是'].index
        
        if len(pareto_indices) > 0:
            time_opt_idx = df_eval.loc[pareto_indices, '反应时间(s)'].idxmin()
            sigma_opt_idx = df_eval.loc[pareto_indices, '打击精度(σ²)'].idxmin()
            fire_opt_idx = df_eval.loc[pareto_indices, '火力打击能力'].idxmax()
            cost_opt_idx = df_eval.loc[pareto_indices, '火力成本'].idxmin()
            match_opt_idx = df_eval.loc[pareto_indices, '弹目匹配度'].idxmax()
            
            _append_opt_label(time_opt_idx, '时间最优')
            _append_opt_label(sigma_opt_idx, '精度最优')
            _append_opt_label(fire_opt_idx, '火力最优')
            _append_opt_label(cost_opt_idx, '成本最优')
            _append_opt_label(match_opt_idx, '匹配度最优')

    red_matrix = None
    if kill_chains:
        red_matrix = pd.DataFrame(np.zeros((len(kill_chains), len(kill_chains))),
                                  index=[f'L{i+1}' for i in range(len(kill_chains))],
                                  columns=[f'L{i+1}' for i in range(len(kill_chains))])
        for i in range(len(kill_chains)):
            for j in range(len(kill_chains)):
                if i != j:
                    red_matrix.iloc[i, j] = _redundancy(kill_chains[i], kill_chains[j])

    return {
        'method_name': '粒子群算法(帕累托优化)',
        'reachability_matrix': reachability_matrix,
        'kill_chains': kill_chains,
        'evaluation': df_eval,
        'pareto_front': pareto_front,
        'redundancy_matrix': red_matrix,
    }

def loop_method(all_nodes: List[str], nodes: Dict[str, Any]) -> Dict[str, Any]:
    """穷举所有合法的 (侦察, 指挥, 火力) 组合，并给出指标评估。"""
    reachability_matrix = _build_reachability_matrix(all_nodes, nodes)

    recon_list = list(nodes['recon'].keys())
    command_list = list(nodes['command'].keys())
    fire_list = list(nodes['fire'].keys())

    preference_table = _normalize_preference_table(nodes.get('preference_table'))
    target_type = _extract_target_type(nodes)

    # A/B/C/D 分别表示“目标->侦察”“侦察->指挥”“指挥->火力”“火力->目标”的可达性。
    A = np.array([1 if distance(nodes['target'], nodes['recon'][o]['coord']) <= nodes['recon'][o]['range'] else 0 for o in recon_list])
    B = np.zeros((len(recon_list), len(command_list)))
    for i, o in enumerate(recon_list):
        for j, c in enumerate(command_list):
            B[i, j] = 1 if distance(nodes['recon'][o]['coord'], nodes['command'][c]['coord']) <= nodes['command'][c]['range'] else 0

    C = np.zeros((len(command_list), len(fire_list)))
    for i, c in enumerate(command_list):
        for j, w in enumerate(fire_list):
            C[i, j] = 1 if distance(nodes['command'][c]['coord'], nodes['fire'][w]['coord']) <= nodes['command'][c]['range'] else 0

    D = np.array([1 if distance(nodes['fire'][w]['coord'], nodes['target']) <= nodes['fire'][w]['range'] else 0 for w in fire_list])

    kill_chains = []
    for i, o in enumerate(recon_list):
        if A[i] != 1:
            continue
        for j, c in enumerate(command_list):
            if B[i, j] != 1:
                continue
            for k, w in enumerate(fire_list):
                if C[j, k] == 1 and D[k] == 1 and (o, c, w) not in kill_chains:
                    kill_chains.append((o, c, w))

    evaluation = []
    for idx, (o, c, w) in enumerate(kill_chains, 1):
        t_total = nodes['recon'][o]['t_deal'] + nodes['command'][c]['t_deal'] + nodes['fire'][w]['t_deal'] + nodes['fire'][w]['t_flight']
        sigma2 = nodes['recon'][o]['sigma2'] + nodes['fire'][w]['sigma2']
        fire_power = nodes['fire'][w]['ammo']['count'] * nodes['fire'][w]['ammo']['omega']
        ammo_cost = float(nodes['fire'][w]['ammo'].get('cost', 0) or 0)
        preference_rank = _compute_match_rank(nodes['fire'][w], target_type, preference_table)
        match_score = _rank_to_match_score(preference_rank)
        tortuosity, cross_count = _calculate_chain_shape_metrics(
            nodes['target'], nodes['recon'][o]['coord'], nodes['command'][c]['coord'], nodes['fire'][w]['coord']
        )
        evaluation.append({'编号': f'L{idx}', '杀伤链': f"t1-{o}-{c}-{w}",
                          '反应时间(s)': t_total, '打击精度(σ²)': sigma2, '火力打击能力': fire_power,
                          '火力成本': ammo_cost, '弹目匹配度': round(match_score, 1),
                          '链路曲折度': round(tortuosity, 2),
                          '链路交叉数': cross_count})
    df_eval = pd.DataFrame(evaluation)

    if not df_eval.empty:
        df_eval['指标优选'] = ''

        def _append_opt_label(row_idx, label):
            """给同一条链叠加多个指标优选标签。"""
            if row_idx is None or pd.isna(row_idx):
                return
            existing = df_eval.at[row_idx, '指标优选']
            df_eval.at[row_idx, '指标优选'] = label if not existing else f"{existing} | {label}"

        _append_opt_label(df_eval['反应时间(s)'].idxmin(), '时间最优')
        _append_opt_label(df_eval['打击精度(σ²)'].idxmin(), '精度最优')
        _append_opt_label(df_eval['火力打击能力'].idxmax(), '火力最优')
        _append_opt_label(df_eval['火力成本'].idxmin(), '成本最优')
        _append_opt_label(df_eval['弹目匹配度'].idxmax(), '匹配度最优')

    red_matrix = None
    if kill_chains:
        red_matrix = pd.DataFrame(np.zeros((len(kill_chains), len(kill_chains))),
                                  index=[f'L{i+1}' for i in range(len(kill_chains))],
                                  columns=[f'L{i+1}' for i in range(len(kill_chains))])
        for i in range(len(kill_chains)):
            for j in range(len(kill_chains)):
                if i != j:
                    red_matrix.iloc[i, j] = _redundancy(kill_chains[i], kill_chains[j])

    return {
        'method_name': '循环搜索',
        'reachability_matrix': reachability_matrix,
        'kill_chains': kill_chains,
        'evaluation': df_eval,
        'pareto_front': [],
        'redundancy_matrix': red_matrix,
    }
