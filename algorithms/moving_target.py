"""
动目标处理工具模块。

提供动目标识别、位置计算、轨迹预测等功能。
"""

from typing import Dict, Tuple, Any

# 可移动目标类型定义
MOVABLE_TARGET_TYPES = {
    '主战坦克', '装甲运兵车', '车队/纵列', '轻步兵/散兵'
}

# 可移动节点类型（侦察、指挥、火力也可能移动）
MOVABLE_NODE_TYPES = {
    'recon': {'雷达无人机', '光电无人机', '无人侦察机'},
    'command': {'移动指挥车', '空中指挥机', '机动指挥所'},
    'fire': {'导弹发射车', '反坦克导弹车', '防空导弹车', '攻击无人机', '火箭炮'}
}


def is_movable_target(target: Dict[str, Any]) -> bool:
    """判断目标是否为可移动目标"""
    return target.get('type') in MOVABLE_TARGET_TYPES


def is_movable_node(node: Dict[str, Any], node_type: str) -> bool:
    """判断节点是否为可移动节点"""
    if node_type not in MOVABLE_NODE_TYPES:
        return False
    model = node.get('model', '')
    return model in MOVABLE_NODE_TYPES[node_type]


def calculate_moving_position(
    coord: Tuple[float, float],
    velocity: Tuple[float, float, float],
    time_elapsed: float
) -> Tuple[float, float]:
    """
    计算移动后的位置
    
    Args:
        coord: 初始坐标 (x, y)
        velocity: 速度 (vx, vy, vh)，单位 km/s
        time_elapsed: 经过时间（秒）
    
    Returns:
        新坐标 (x, y)
    """
    x, y = coord
    vx, vy, _ = velocity if len(velocity) >= 2 else (velocity[0] if velocity else 0, 0, 0)
    
    # 位置更新：新位置 = 初始位置 + 速度 × 时间
    new_x = x + vx * time_elapsed
    new_y = y + vy * time_elapsed
    
    return (new_x, new_y)


def update_target_position(target: Dict[str, Any], time_elapsed: float) -> Dict[str, Any]:
    """
    更新目标位置
    
    Args:
        target: 目标节点数据
        time_elapsed: 经过时间（秒）
    
    Returns:
        更新后的目标数据（创建副本，不修改原数据）
    """
    target_copy = target.copy()
    coord = target.get('coord', (0, 0))
    
    # 获取速度
    vx = target.get('vx', 0) or 0
    vy = target.get('vy', 0) or 0
    vh = target.get('vh', 0) or 0
    
    # 如果没有速度，不更新位置
    if vx == 0 and vy == 0 and vh == 0:
        return target_copy
    
    velocity = (vx, vy, vh)
    
    new_coord = calculate_moving_position(coord, velocity, time_elapsed)
    target_copy['coord'] = new_coord
    target_copy['original_coord'] = coord  # 保留原始位置
    
    return target_copy


def update_node_position(node: Dict[str, Any], time_elapsed: float) -> Dict[str, Any]:
    """
    更新节点位置
    
    Args:
        node: 节点数据
        time_elapsed: 经过时间（秒）
    
    Returns:
        更新后的节点数据（创建副本）
    """
    node_copy = node.copy()
    coord = node.get('coord', (0, 0))
    
    # 获取速度，优先使用 vx/vy 字段
    vx = node.get('vx', 0)
    vy = node.get('vy', 0)
    vh = node.get('vh', 0)
    
    if vx == 0 and vy == 0:
        return node_copy  # 静止节点
    
    new_coord = calculate_moving_position(coord, (vx, vy, vh), time_elapsed)
    node_copy['coord'] = new_coord
    node_copy['original_coord'] = coord
    
    return node_copy


def update_all_positions(
    targets: Dict[str, Any],
    nodes: Dict[str, Any],
    time_elapsed: float,
    update_nodes: bool = False
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    更新所有目标（和节点）的位置
    
    Args:
        targets: 目标字典
        nodes: 节点字典（包含 recon, command, fire）
        time_elapsed: 经过时间（秒）
        update_nodes: 是否同时更新节点位置
    
    Returns:
        (updated_targets, updated_nodes)
    """
    # 更新目标位置
    updated_targets = {}
    for tid, target in targets.items():
        updated_targets[tid] = update_target_position(target, time_elapsed)
    
    # 更新节点位置（可选）
    updated_nodes = nodes
    if update_nodes:
        updated_nodes = {
            'recon': {},
            'command': {},
            'fire': {}
        }
        for nid, node in nodes.get('recon', {}).items():
            updated_nodes['recon'][nid] = update_node_position(node, time_elapsed)
        for nid, node in nodes.get('command', {}).items():
            updated_nodes['command'][nid] = update_node_position(node, time_elapsed)
        for nid, node in nodes.get('fire', {}).items():
            updated_nodes['fire'][nid] = update_node_position(node, time_elapsed)
    
    return updated_targets, updated_nodes


def get_target_trajectory(
    target: Dict[str, Any],
    time_steps: list
) -> list:
    """
    获取目标轨迹点序列
    
    Args:
        target: 目标节点
        time_steps: 时间点列表（秒）
    
    Returns:
        轨迹点列表 [(t0, x0, y0), (t1, x1, y1), ...]
    """
    if not is_movable_target(target):
        coord = target.get('coord', (0, 0))
        return [(t, coord[0], coord[1]) for t in time_steps]
    
    trajectory = []
    coord = target.get('coord', (0, 0))
    velocity = (
        target.get('vx', 0),
        target.get('vy', 0),
        target.get('vh', 0)
    )
    
    for t in time_steps:
        new_coord = calculate_moving_position(coord, velocity, t)
        trajectory.append((t, new_coord[0], new_coord[1]))
    
    return trajectory


def has_movable_targets(targets: Dict[str, Any]) -> bool:
    """检查是否存在可移动目标"""
    return any(is_movable_target(t) for t in targets.values())
