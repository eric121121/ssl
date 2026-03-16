"""
多目标杀伤链构建算法集合。

与 UI 的交互主要通过 services.algorithm_service 进行，这里只关注算法流程：
- 先计算所有目标的可行链
- 根据弹目偏好和侦察并行约束做分配
- 输出分配报告和统计指标
"""
import numpy as np
import pandas as pd
from typing import Any, Dict, List, Tuple

from .single_target import (
    distance,
    loop_method,
    _calculate_chain_shape_metrics,
    _segments_strictly_intersect,
)


def generate_all_feasible_chains(targets: Dict[str, Any], nodes: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """
    为所有目标生成可行链（复用现有逻辑）

    只对外暴露一个轻量接口，内部调用 loop_method，便于对话框或脚本快速检查每个目标的候选链。
    """
    all_chains = {}
    
    for target_id, target in targets.items():
        # 为每个目标单独计算可行链（复用现有算法）
        target_nodes = {
            'target': target['coord'],
            'recon': nodes['recon'],
            'command': nodes['command'], 
            'fire': nodes['fire']
        }
        
        # 使用现有的loop_method逻辑
        all_nodes = list(nodes['recon'].keys()) + list(nodes['command'].keys()) + list(nodes['fire'].keys()) + ['t1']
        result = loop_method(all_nodes, target_nodes)
        
        # 记录每条链的目标信息
        chains_with_target = []
        for chain in result['kill_chains']:
            o, c, w = chain
            chains_with_target.append({
                'target_id': target_id,
                'target_type': target['type'],
                'recon': o,
                'command': c, 
                'fire': w,
                'fire_type': nodes['fire'][w]['firepower_type']
            })
        
        all_chains[target_id] = chains_with_target
    
    return all_chains


def enhanced_multi_target_ssl_allocation(targets: Dict[str, Any], nodes: Dict[str, Any], preference_table: Dict) -> Dict[str, Any]:
    """
    增强版多目标SSL构建主函数
    1. 遍历搜索所有可行SSL
    2. 指挥节点可无限复用
    3. 火力节点冲突用弹目优先级排序
    4. 考虑侦察节点并行上限
    5. 计算最优分配方案
    """
    print("开始多目标SSL构建...")
    
    # 1. 遍历搜索所有可行SSL
    print("步骤1: 遍历搜索所有可行SSL...")
    all_feasible_chains = find_all_feasible_ssl_chains(targets, nodes)
    print(f"找到 {sum(len(chains) for chains in all_feasible_chains.values())} 条可行SSL")
    
    # 2. 识别火力节点冲突
    print("步骤2: 识别火力节点冲突...")
    fire_conflicts, fire_usage = identify_fire_conflicts_enhanced(all_feasible_chains)
    print(f"发现 {len(fire_conflicts)} 个火力节点存在冲突")
    
    # 3. 弹目优先级排序
    print("步骤3: 弹目优先级排序...")
    prioritized_chains = prioritize_chains_by_fire_target_preference(fire_conflicts, preference_table)
    
    # 4. 考虑侦察节点并行上限的分配
    print("步骤4: 考虑侦察节点并行上限的分配...")
    allocation_result = allocate_with_recon_limits(prioritized_chains, all_feasible_chains, nodes)
    final_allocation = allocation_result['final_allocation']
    all_chain_status = allocation_result['all_chain_status']
    
    # 5. 计算详细评估指标（传入all_feasible_chains用于计算目标覆盖度）
    print("步骤5: 计算评估指标...")
    detailed_evaluation = calculate_detailed_multi_target_metrics(final_allocation, nodes, targets, all_feasible_chains)
    
    # 6. 生成分配方案报告
    allocation_report = generate_allocation_report(final_allocation, nodes, targets, all_chain_status)
    
    return {
        'method_name': '增强版多目标SSL构建',
        'all_feasible_chains': all_feasible_chains,
        'fire_conflicts': fire_conflicts,
        'prioritized_chains': prioritized_chains,
        'final_allocation': final_allocation,
        'all_chain_status': all_chain_status,
        'evaluation': detailed_evaluation,
        'allocation_report': allocation_report
    }


def find_all_feasible_ssl_chains(targets: Dict[str, Any], nodes: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """
    遍历搜索所有可行的SSL杀伤链

    指挥节点可以无限复用，但侦察和火力节点有约束; 这里会计算链的性能指标以供后续排序。
    """
    all_chains = {}
    
    for target_id, target in targets.items():
        feasible_chains = []
        target_coord = target['coord']
        
        # 遍历所有侦察节点
        for recon_id, recon_node in nodes['recon'].items():
            # 检查侦察节点是否能覆盖目标
            if distance(target_coord, recon_node['coord']) <= recon_node['range']:
                
                # 遍历所有指挥节点（可无限复用）
                for command_id, command_node in nodes['command'].items():
                    # 检查侦察节点是否能与指挥节点通信
                    if distance(recon_node['coord'], command_node['coord']) <= command_node['range']:
                        
                        # 遍历所有火力节点
                        for fire_id, fire_node in nodes['fire'].items():
                            # 检查指挥节点是否能与火力节点通信
                            if distance(command_node['coord'], fire_node['coord']) <= command_node['range']:
                                # 检查火力节点是否能打击目标
                                if distance(fire_node['coord'], target_coord) <= fire_node['range']:
                                    
                                    # 计算杀伤链性能指标
                                    chain_metrics = calculate_chain_metrics(
                                        recon_id, command_id, fire_id, target_id, 
                                        recon_node, command_node, fire_node, target, nodes
                                    )
                                    
                                    feasible_chains.append({
                                        'target_id': target_id,
                                        'target_type': target['type'],
                                        'recon_id': recon_id,
                                        'command_id': command_id,
                                        'fire_id': fire_id,
                                        'fire_type': fire_node['firepower_type'],
                                        'ammo_type': fire_node['ammo_type'],
                                        'metrics': chain_metrics
                                    })
        
        all_chains[target_id] = feasible_chains
    
    return all_chains


def calculate_chain_metrics(recon_id: str, command_id: str, fire_id: str, target_id: str,
                           recon_node: Dict, command_node: Dict, fire_node: Dict, 
                           target: Dict, nodes: Dict) -> Dict:
    """
    计算单条杀伤链的性能指标。

    返回的 dict 会被用于排序（弹目偏好、反应时间等）以及表格展示。
    """
    
    # 反应时间 = 侦察处理时间 + 指挥处理时间 + 火力处理时间 + 飞行时间
    reaction_time = (recon_node['t_deal'] + command_node['t_deal'] + 
                    fire_node['t_deal'] + fire_node.get('t_flight', 0))
    
    # 打击精度 = 侦察精度 + 火力精度
    precision = recon_node['sigma2'] + fire_node['sigma2']
    
    # 火力打击能力 = 弹药数量 × 折算系数
    fire_power = fire_node['ammo']['count'] * fire_node['ammo']['omega']
    
    tortuosity, cross_count = _calculate_chain_shape_metrics(
        target['coord'], recon_node['coord'], command_node['coord'], fire_node['coord']
    )
    
    # 侦察节点类型
    recon_type = recon_node.get('model', '未知')
    
    # 弹药成本（从ammo字典中获取）
    # 兜底确保为float，避免Decimal参与加法
    _cost_val = fire_node['ammo'].get('cost', 0)
    try:
        ammo_cost = float(_cost_val)
    except Exception:
        ammo_cost = 0.0

    return {
        'reaction_time': reaction_time,
        'precision': precision,
        'fire_power': fire_power,
        'tortuosity': tortuosity,
        'cross_count': cross_count,
        'recon_type': recon_type,
        'ammo_cost': ammo_cost
    }


def _build_chain_segments(target_coord, recon_coord, command_coord, fire_coord):
    """返回一条链的关键路径段，用于方案级空间分析。"""
    return [
        (target_coord, recon_coord),
        (recon_coord, command_coord),
        (command_coord, fire_coord),
        (fire_coord, target_coord)
    ]


def _count_crossings_between_chains(chain_geometries: List[Dict[str, Any]]) -> int:
    """
    统计链间交叉数：有任意一段相交即视为这两条链存在一次交叉。
    """
    crossings = 0
    for idx, chain_a in enumerate(chain_geometries):
        segments_a = chain_a['segments']
        for jdx in range(idx + 1, len(chain_geometries)):
            chain_b = chain_geometries[jdx]
            segments_b = chain_b['segments']
            crossed = False
            for seg_a in segments_a:
                for seg_b in segments_b:
                    if _segments_strictly_intersect(seg_a[0], seg_a[1], seg_b[0], seg_b[1]):
                        crossings += 1
                        crossed = True
                        break
                if crossed:
                    break
    return crossings


def _calculate_plan_geometry_metrics(allocation: Dict[str, Dict], nodes: Dict[str, Any], targets: Dict[str, Any]) -> Tuple[float, int]:
    """计算方案级的整体曲折度与链间交叉数。"""
    total_open_length = 0.0
    total_direct_distance = 0.0
    chain_geometries = []
    for target_id, chain in allocation.items():
        target = targets.get(target_id, {})
        target_coord = target.get('coord')
        recon_id = chain.get('recon_id')
        command_id = chain.get('command_id')
        fire_id = chain.get('fire_id')
        if not (target_coord and recon_id in nodes['recon'] and command_id in nodes['command'] and fire_id in nodes['fire']):
            continue
        recon_coord = nodes['recon'][recon_id]['coord']
        command_coord = nodes['command'][command_id]['coord']
        fire_coord = nodes['fire'][fire_id]['coord']
        open_length = (
            distance(target_coord, recon_coord) +
            distance(recon_coord, command_coord) +
            distance(command_coord, fire_coord)
        )
        direct_distance = distance(target_coord, fire_coord)
        total_open_length += open_length
        total_direct_distance += direct_distance
        chain_geometries.append({
            'target_id': target_id,
            'segments': _build_chain_segments(target_coord, recon_coord, command_coord, fire_coord)
        })
    overall_plan_tortuosity = (total_open_length / total_direct_distance) if total_direct_distance > 0 else 0.0
    inter_chain_crossings = _count_crossings_between_chains(chain_geometries) if len(chain_geometries) > 1 else 0
    return overall_plan_tortuosity, inter_chain_crossings


def identify_fire_conflicts_enhanced(all_chains: Dict[str, List[Dict]]) -> Tuple[Dict, Dict]:
    """
    识别火力节点冲突（增强版）

    Returns:
        conflicts: 仅包含存在冲突（同一火力节点被多目标引用）的子集。
        fire_usage: 所有火力节点对应的链列表，用于 UI 展示火力工作量。
    """
    fire_usage = {}  # fire_id -> [chain_info]
    
    for target_id, chains in all_chains.items():
        for chain in chains:
            fire_id = chain['fire_id']
            if fire_id not in fire_usage:
                fire_usage[fire_id] = []
            fire_usage[fire_id].append(chain)
    
    # 找出有冲突的火力节点
    conflicts = {fire_id: chains for fire_id, chains in fire_usage.items() if len(chains) > 1}
    
    return conflicts, fire_usage


def prioritize_chains_by_fire_target_preference(conflicts: Dict, preference_table: Dict) -> Dict:
    """
    根据弹目优先级对冲突的火力节点进行排序。

    preference_table 由数据库驱动，数值越小代表越偏好，该函数会把得分写入 chain['preference_score']。
    """
    prioritized_conflicts = {}
    
    for fire_id, chains in conflicts.items():
        prioritized_chains = []
        
        for chain in chains:
            fire_type = chain['fire_type']
            target_type = chain['target_type']
            
            # 获取弹目优先级分数（数值越小优先级越高）
            preference_score = preference_table.get((fire_type, target_type), 999)
            
            prioritized_chain = chain.copy()
            prioritized_chain['preference_score'] = preference_score
            prioritized_chains.append(prioritized_chain)
        
        # 按优先级分数升序排序（分数越小优先级越高）
        prioritized_chains.sort(key=lambda x: x['preference_score'])
        prioritized_conflicts[fire_id] = prioritized_chains
    
    return prioritized_conflicts


def allocate_with_recon_limits(prioritized_conflicts: Dict, all_chains: Dict[str, List[Dict]], 
                              nodes: Dict[str, Any]) -> Dict[str, Dict]:
    """
    综合约束分配算法。

    分配顺序：可达成链 → 火力约束 → 指挥容量约束 → 侦察并行约束
    返回包含所有链状态的完整分配结果（成功/失败原因），便于生成报告。
    """
    final_allocation = {}
    used_fires = set()  # 火力节点使用跟踪（每个火力节点只能打击一个目标）
    used_command_count = {}  # 指挥节点使用计数 {command_id: 已分配目标数}
    used_recon_count = {}  # 侦察节点使用计数 {recon_id: 已分配目标数}
    
    # 收集所有需要分配的链（包括冲突和非冲突）
    all_chains_to_allocate = []
    
    # 添加冲突链
    for fire_id, chains in prioritized_conflicts.items():
        for chain in chains:
            all_chains_to_allocate.append((fire_id, chain, True))  # True表示是冲突链
    
    # 添加非冲突链
    for target_id, chains in all_chains.items():
        for chain in chains:
            fire_id = chain['fire_id']
            if fire_id not in prioritized_conflicts:  # 非冲突链
                all_chains_to_allocate.append((fire_id, chain, False))  # False表示非冲突链
    
    # 按优先级排序所有链
    all_chains_to_allocate.sort(key=lambda x: (
        x[2],  # 冲突链优先
        x[1]['preference_score'] if 'preference_score' in x[1] else 0,  # 然后按优先级分数
        x[1]['metrics']['reaction_time']  # 最后按反应时间
    ))
    
    # 记录所有链的状态
    all_chain_status = {}
    
    # 贪心分配
    for fire_id, chain, is_conflict in all_chains_to_allocate:
        target_id = chain['target_id']
        
        # 如果该目标已经分配了链，记录为冲突淘汰
        if target_id in final_allocation:
            all_chain_status[f"{target_id}_{fire_id}_{chain['recon_id']}_{chain['command_id']}"] = {
                'target_id': target_id,
                'chain': chain,
                'status': '冲突淘汰',
                'reason': '目标已被其他链分配',
                'is_conflict': is_conflict
            }
            continue
        
        # 如果该火力节点已被使用，记录为火力冲突
        if fire_id in used_fires:
            all_chain_status[f"{target_id}_{fire_id}_{chain['recon_id']}_{chain['command_id']}"] = {
                'target_id': target_id,
                'chain': chain,
                'status': '火力冲突',
                'reason': f'火力节点{fire_id}已被使用',
                'is_conflict': is_conflict
            }
            continue
        
        # 步骤3: 检查指挥节点容量限制
        command_id = chain['command_id']
        command_node = nodes['command'].get(command_id)
        
        if not command_node:
            all_chain_status[f"{target_id}_{fire_id}_{chain['recon_id']}_{command_id}"] = {
                'target_id': target_id,
                'chain': chain,
                'status': '指挥限制',
                'reason': f'指挥节点{command_id}不存在',
                'is_conflict': is_conflict
            }
            continue
        
        # 获取指挥节点容量
        command_capacity = command_node.get('command_capacity', float('inf'))  # 如果没有设置容量，则无限制
        current_command_usage = used_command_count.get(command_id, 0)
        
        if current_command_usage >= command_capacity:
            # 指挥节点已满
            all_chain_status[f"{target_id}_{fire_id}_{chain['recon_id']}_{command_id}"] = {
                'target_id': target_id,
                'chain': chain,
                'status': '指挥限制',
                'reason': f'指挥节点{command_id}已达容量上限({command_capacity})',
                'is_conflict': is_conflict
            }
            continue
        
        # 步骤4: 检查侦察节点并行上限
        recon_id = chain['recon_id']
        recon_node = nodes['recon'].get(recon_id)
        
        if not recon_node:
            # 记录侦察节点不存在
            all_chain_status[f"{target_id}_{fire_id}_{recon_id}_{command_id}"] = {
                'target_id': target_id,
                'chain': chain,
                'status': '侦察限制',
                'reason': f'侦察节点{recon_id}不存在',
                'is_conflict': is_conflict
            }
            continue
        
        # 获取侦察节点的并行上限（类似指挥节点容量）
        recon_parallel_limit = recon_node.get('parallel_limit', float('inf'))  # 如果没有设置，则无限制
        current_recon_usage = used_recon_count.get(recon_id, 0)
        
        # 检查侦察节点是否已达并行上限
        if current_recon_usage >= recon_parallel_limit:
            # 记录侦察节点限制
            all_chain_status[f"{target_id}_{fire_id}_{recon_id}_{command_id}"] = {
                'target_id': target_id,
                'chain': chain,
                'status': '侦察限制',
                'reason': f'侦察节点{recon_id}已达并行上限({recon_parallel_limit})',
                'is_conflict': is_conflict
            }
            continue
        
        # 所有约束都满足，成功分配
        final_allocation[target_id] = chain
        used_fires.add(fire_id)
        used_command_count[command_id] = current_command_usage + 1
        used_recon_count[recon_id] = current_recon_usage + 1
        
        # 记录成功分配
        all_chain_status[f"{target_id}_{fire_id}_{recon_id}_{command_id}"] = {
            'target_id': target_id,
            'chain': chain,
            'status': '成功分配',
            'reason': '满足所有约束条件',
            'is_conflict': is_conflict
        }
    
    # 检查无可行链的目标
    for target_id in all_chains.keys():
        if target_id not in final_allocation:
            # 检查是否有可行链
            if target_id in all_chains and not all_chains[target_id]:
                all_chain_status[f"{target_id}_no_feasible"] = {
                    'target_id': target_id,
                    'chain': None,
                    'status': '无可行链',
                    'reason': '目标无任何可行的SSL链',
                    'is_conflict': False
                }
    
    return {
        'final_allocation': final_allocation,
        'all_chain_status': all_chain_status,
        'used_fires': used_fires,
        'used_command_count': used_command_count,
        'used_recon_count': used_recon_count
    }


def calculate_detailed_multi_target_metrics(final_allocation: Dict, nodes: Dict[str, Any],
                                          targets: Dict[str, Any], all_feasible_chains: Dict[str, List[Dict]] = None) -> Dict:
    """
    聚合多目标方案的指标。

    除传统指标（火力、反应时间、威胁度等）外，还会计算：
        * `overall_plan_tortuosity`：整体链路曲折度
        * `inter_chain_crossings`：链路之间的交叉次数
        * `recon_utilization`：各侦察节点的负载率
    这些数据会在 UI 侧展示为“评估表”与“统计摘要”。
    """
    if not final_allocation:
        return {
            'total_targets': 0,
            'allocated_targets': 0,
            'allocation_rate': 0.0,
            'total_fire_power': 0,
            'avg_reaction_time': 0,
            'avg_precision': 0,
            'avg_tortuosity': 0,
            'avg_cross_count': 0,
            'crossing_chain_ratio': 0,
            'overall_plan_tortuosity': 0,
            'inter_chain_crossings': 0,
            'fire_utilization': 0.0,
            'recon_utilization': {},
            'unallocated_targets': list(targets.keys()),
            # 综合性指标
            'fire_cross_coverage': 0,
            'avg_target_coverage': 0,
            'total_threat_value': 0,
            'total_cost': 0,
            'avg_cost_per_target': 0,
            'cost_efficiency': 0
        }
    
    total_fire_power = 0
    total_reaction_time = 0
    total_precision = 0
    total_tortuosity = 0
    total_cross_count = 0
    crossing_chain_count = 0
    used_fires = set()
    used_recon_count = {}
    valid_chains = 0
    
    # 综合性指标统计
    total_threat_value = 0  # 威胁度总和
    total_cost = 0  # 总成本
    fire_to_targets = {}  # 火力节点到目标的映射（用于火力交叉统计）
    target_coverage_count = {}  # 每个目标被多少火力节点覆盖
    
    for target_id, chain in final_allocation.items():
        if chain['fire_id'] in nodes['fire']:
            fire_node = nodes['fire'][chain['fire_id']]
            recon_node = nodes['recon'][chain['recon_id']]
            target = targets.get(target_id, {})
            
            # 累计各项指标
            total_fire_power += chain['metrics']['fire_power']
            total_reaction_time += chain['metrics']['reaction_time']
            total_precision += chain['metrics']['precision']
            total_tortuosity += chain['metrics'].get('tortuosity', 0)
            cross_val = chain['metrics'].get('cross_count', 0)
            total_cross_count += cross_val
            if cross_val:
                crossing_chain_count += 1
            
            used_fires.add(chain['fire_id'])
            
            # 统计侦察节点使用情况
            recon_type = chain['metrics']['recon_type']
            used_recon_count[recon_type] = used_recon_count.get(recon_type, 0) + 1
            
            # 综合性指标统计
            # 1. 威胁度累计
            threat_level = target.get('threat_level', 0)
            total_threat_value += threat_level
            
            # 2. 成本累计（从链路指标中获取）
            chain_metrics = chain.get('metrics', {})
            ammo_cost = chain_metrics.get('ammo_cost', 0)
            total_cost += ammo_cost
            
            # 3. 火力交叉统计：记录每个火力节点打击的目标
            if chain['fire_id'] not in fire_to_targets:
                fire_to_targets[chain['fire_id']] = []
            fire_to_targets[chain['fire_id']].append(target_id)
            
            valid_chains += 1
    
    # 计算平均值
    avg_reaction_time = total_reaction_time / valid_chains if valid_chains > 0 else 0
    avg_precision = total_precision / valid_chains if valid_chains > 0 else 0
    avg_tortuosity = total_tortuosity / valid_chains if valid_chains > 0 else 0
    avg_cross_count = total_cross_count / valid_chains if valid_chains > 0 else 0
    crossing_chain_ratio = crossing_chain_count / valid_chains if valid_chains > 0 else 0
    overall_plan_tortuosity, inter_chain_crossings = _calculate_plan_geometry_metrics(final_allocation, nodes, targets)
    
    # 计算资源利用率
    fire_utilization = len(used_fires) / len(nodes['fire']) if len(nodes['fire']) > 0 else 0
    
    # 计算侦察节点利用率（按单个节点统计，类似指挥节点）
    recon_utilization = {}
    used_recon_nodes = set()
    total_recon_capacity = 0
    used_recon_capacity = 0
    
    for target_id, chain in final_allocation.items():
        recon_id = chain.get('recon_id')
        if recon_id:
            used_recon_nodes.add(recon_id)
    
    # 统计所有侦察节点容量和已用容量
    for recon_id, recon_node in nodes['recon'].items():
        parallel_limit = recon_node.get('parallel_limit', 1)
        total_recon_capacity += parallel_limit
        
        # 统计该侦察节点的实际使用情况
        used_count = 0
        for target_id, chain in final_allocation.items():
            if chain.get('recon_id') == recon_id:
                used_count += 1
        
        if parallel_limit > 0:
            utilization_rate = used_count / parallel_limit
            recon_utilization[recon_id] = {
                'used': used_count,
                'parallel_limit': parallel_limit,
                'utilization': utilization_rate
            }
        used_recon_capacity += used_count
    
    # 整体侦察节点利用率
    avg_recon_utilization = used_recon_capacity / total_recon_capacity if total_recon_capacity > 0 else 0
    
    # 计算指挥节点利用率
    command_utilization = {}
    used_command_nodes = set()
    total_command_capacity = 0
    used_command_capacity = 0
    
    for target_id, chain in final_allocation.items():
        command_id = chain.get('command_id')
        if command_id:
            used_command_nodes.add(command_id)
    
    # 统计所有指挥节点容量和已用容量
    for command_id, command_node in nodes['command'].items():
        capacity = command_node.get('command_capacity', 0)
        total_command_capacity += capacity
        
        # 统计该指挥节点的实际使用情况
        used_count = 0
        for target_id, chain in final_allocation.items():
            if chain.get('command_id') == command_id:
                used_count += 1
        
        if capacity > 0:
            utilization_rate = used_count / capacity
            command_utilization[command_id] = {
                'used': used_count,
                'capacity': capacity,
                'utilization': utilization_rate
            }
        used_command_capacity += used_count
    
    # 整体指挥节点利用率
    avg_command_utilization = used_command_capacity / total_command_capacity if total_command_capacity > 0 else 0
    
    # 找出未分配的目标
    unallocated_targets = [tid for tid in targets.keys() if tid not in final_allocation]
    
    # 综合性指标计算
    # 1. 火力交叉覆盖度：平均每个火力节点打击的目标数
    fire_cross_coverage = sum(len(tgts) for tgts in fire_to_targets.values()) / len(fire_to_targets) if fire_to_targets else 0
    
    # 2. 计算每个目标的可用火力覆盖数（从所有可行链中统计）
    avg_target_coverage = 0
    if all_feasible_chains:
        target_fire_counts = {}
        for target_id, chains in all_feasible_chains.items():
            # 统计每个目标有多少不同的火力节点可以打击
            unique_fires = set()
            for chain in chains:
                unique_fires.add(chain['fire_id'])
            target_fire_counts[target_id] = len(unique_fires)
        
        # 计算平均覆盖度
        if target_fire_counts:
            avg_target_coverage = sum(target_fire_counts.values()) / len(target_fire_counts)
    
    # 3. 成本效能指标
    avg_cost_per_target = total_cost / valid_chains if valid_chains > 0 else 0
    # 成本效能 = 威胁度总和 / 总成本（威胁度越高，成本越低，效能越好）
    cost_efficiency = total_threat_value / total_cost if total_cost > 0 else 0
    
    return {
        'total_targets': len(targets),
        'allocated_targets': len(final_allocation),
        'allocation_rate': len(final_allocation) / len(targets) if len(targets) > 0 else 0,
        'total_fire_power': total_fire_power,
        'avg_reaction_time': avg_reaction_time,
        'avg_precision': avg_precision,
        'avg_tortuosity': avg_tortuosity,
        'avg_cross_count': avg_cross_count,
        'crossing_chain_ratio': crossing_chain_ratio,
        'overall_plan_tortuosity': overall_plan_tortuosity,
        'inter_chain_crossings': inter_chain_crossings,
        'fire_utilization': fire_utilization,
        'recon_utilization': recon_utilization,  # 详细侦察节点利用率
        'avg_recon_utilization': avg_recon_utilization,  # 平均侦察节点利用率
        'command_utilization': command_utilization,  # 详细指挥节点利用率
        'avg_command_utilization': avg_command_utilization,  # 平均指挥节点利用率
        'unallocated_targets': unallocated_targets,
        # 综合性指标
        'fire_cross_coverage': fire_cross_coverage,
        'avg_target_coverage': avg_target_coverage,
        'total_threat_value': total_threat_value,
        'total_cost': total_cost,
        'avg_cost_per_target': avg_cost_per_target,
        'cost_efficiency': cost_efficiency
    }


def generate_allocation_report(final_allocation: Dict, nodes: Dict[str, Any],
                             targets: Dict[str, Any], all_chain_status: Dict = None) -> List[Dict]:
    """
    生成完整的分配方案详细报告，包含所有链的状态。

    输出的数据结构可直接塞入 QTableWidget：
        * 每个分组（成功、冲突、侦察限制等）都会插入一个标题行
        * 目标未分配的原因会写入 `备注`
    若 `all_chain_status` 为空，则仅基于 `final_allocation` 输出成功链。
    """
    report = []
    
    if all_chain_status:
        # 按状态分组显示
        status_groups = {
            '成功分配': [],
            '火力冲突': [],
            '冲突淘汰': [],
            '侦察限制': [],
            '无可行链': []
        }
        
        # 按状态分组
        for status_key, status_info in all_chain_status.items():
            status = status_info['status']
            if status in status_groups:
                status_groups[status].append(status_info)
        
        # 对成功分配的链按目标ID排序
        if '成功分配' in status_groups:
            status_groups['成功分配'].sort(key=lambda x: int(x['target_id'][1:]) if x['target_id'].startswith('t') else 0)
        
        # 生成报告
        for status_name, chains in status_groups.items():
            if not chains:
                continue
                
            # 添加状态分组标题
            report.append({
                '目标ID': f"=== {status_name} ===",
                '目标类型': '',
                '威胁等级': '',
                '侦察节点': '',
                '指挥节点': '',
                '火力节点': '',
                '弹药类型': '',
                '反应时间(s)': '',
                '打击精度(σ²)': '',
                '火力能力': '',
                '链路曲折度': '',
                '链路交叉数': ''
            })
            
            # 添加该状态下的所有链
            for status_info in chains:
                target_id = status_info['target_id']
                chain = status_info['chain']
                
                if chain is None:  # 无可行链的情况
                    target = targets.get(target_id, {})
                    report.append({
                        '目标ID': target_id,
                        '目标类型': target.get('type', '未知'),
                        '威胁等级': target.get('threat_level', '未知'),
                        '侦察节点': '无',
                        '指挥节点': '无',
                        '火力节点': '无',
                        '弹药类型': '无',
                        '反应时间(s)': '无',
                        '打击精度(σ²)': '无',
                        '火力能力': '无',
                        '链路曲折度': '无',
                        '链路交叉数': '无'
                    })
                else:
                    target = targets.get(target_id, {})
                    fire_node = nodes['fire'].get(chain['fire_id'], {})
                    recon_node = nodes['recon'].get(chain['recon_id'], {})
                    command_node = nodes['command'].get(chain['command_id'], {})
                    
                    report.append({
                        '目标ID': target_id,
                        '目标类型': target.get('type', '未知'),
                        '威胁等级': target.get('threat_level', '未知'),
                        '侦察节点': f"{chain['recon_id']}({chain['metrics']['recon_type']})",
                        '指挥节点': chain['command_id'],
                        '火力节点': f"{chain['fire_id']}({chain['fire_type']})",
                        '弹药类型': chain['ammo_type'],
                        '反应时间(s)': round(chain['metrics']['reaction_time'], 2) if 'metrics' in chain else '未知',
                        '打击精度(σ²)': round(chain['metrics']['precision'], 2) if 'metrics' in chain else '未知',
                        '火力能力': round(chain['metrics']['fire_power'], 2) if 'metrics' in chain else '未知',
                        '链路曲折度': round(chain['metrics'].get('tortuosity', 0), 2) if 'metrics' in chain else '未知',
                        '链路交叉数': chain['metrics'].get('cross_count', '未知') if 'metrics' in chain else '未知'
                    })
        
        # 添加统计信息
        total_chains = len(all_chain_status)
        success_count = len(status_groups['成功分配'])
        conflict_count = len(status_groups['火力冲突'])
        eliminated_count = len(status_groups['冲突淘汰'])
        recon_limit_count = len(status_groups['侦察限制'])
        no_feasible_count = len(status_groups['无可行链'])
        
        report.append({
            '目标ID': "=== 统计信息 ===",
            '目标类型': '',
            '威胁等级': '',
            '侦察节点': '',
            '指挥节点': '',
            '火力节点': '',
            '弹药类型': '',
            '反应时间(s)': '',
            '打击精度(σ²)': '',
            '火力能力': '',
            '链路曲折度': '',
            '链路交叉数': '',
            '分配状态': '',
            '失败原因': '',
            '是否冲突链': ''
        })
        
        report.append({
            '目标ID': f"总链数: {total_chains}",
            '目标类型': f"成功分配: {success_count}",
            '威胁等级': f"火力冲突: {conflict_count}",
            '侦察节点': f"冲突淘汰: {eliminated_count}",
            '指挥节点': f"侦察限制: {recon_limit_count}",
            '火力节点': f"无可行链: {no_feasible_count}",
            '弹药类型': f"成功率: {success_count/total_chains*100:.1f}%" if total_chains > 0 else "0%",
            '反应时间(s)': '',
            '打击精度(σ²)': '',
            '火力能力': '',
            '分配状态': '',
            '失败原因': '',
            '是否冲突链': ''
        })
    
    else:
        # 兼容旧版本，只显示成功分配的链
        for target_id, chain in final_allocation.items():
            target = targets[target_id]
            fire_node = nodes['fire'][chain['fire_id']]
            recon_node = nodes['recon'][chain['recon_id']]
            command_node = nodes['command'][chain['command_id']]
            
            report.append({
                '目标ID': target_id,
                '目标类型': target['type'],
                '威胁等级': target.get('threat_level', '未知'),
                '侦察节点': f"{chain['recon_id']}({chain['metrics']['recon_type']})",
                '指挥节点': chain['command_id'],
                '火力节点': f"{chain['fire_id']}({chain['fire_type']})",
                '弹药类型': chain['ammo_type'],
                '反应时间(s)': round(chain['metrics']['reaction_time'], 2),
                '打击精度(σ²)': round(chain['metrics']['precision'], 2),
                '火力能力': round(chain['metrics']['fire_power'], 2),
                '链路曲折度': round(chain['metrics'].get('tortuosity', 0), 2),
                '链路交叉数': chain['metrics'].get('cross_count', 0)
            })
    
    return report


# ============================================================================
# 多目标SSL的MOPSO+帕累托优化方案
# ============================================================================

def mopso_multi_target_allocation(
    targets: Dict[str, Any], 
    nodes: Dict[str, Any], 
    preference_table: Dict,
    num_particles: int = 50,
    max_iterations: int = 80,
    archive_size: int = 100,
    random_seed: int = None,
    use_hierarchical: bool = True
) -> Dict[str, Any]:
    """
    纯MOPSO多目标优化：直接搜索节点组合，不使用预遍历
    
    参数：
        targets: 所有目标节点
        nodes: 所有节点（侦察、指挥、火力）
        preference_table: 弹目偏好表
        num_particles: 粒子数量
        max_iterations: 最大迭代次数
        archive_size: 帕累托档案大小
        random_seed: 随机种子（用于实验可重复性）
        use_hierarchical: 是否使用层次化帕累托（默认True）
    
    返回：
        包含帕累托前沿、收敛数据等的字典
    """
    
    if random_seed is not None:
        np.random.seed(random_seed)
    
    print("=" * 60)
    if use_hierarchical:
        print("开始MOPSO多目标SSL分配优化（两层层次化帕累托，6目标简化版）...")
        print("  第一层: 最大化威胁度覆盖（已包含分配数量信息）")
        print("  第二层: 优化成本、时间、精度、匹配度、火力等5个指标")
    else:
        print("开始MOPSO多目标SSL分配优化（传统6目标帕累托）...")
    print("=" * 60)
    
    # 准备节点列表
    recon_list = list(nodes['recon'].keys())
    command_list = list(nodes['command'].keys())
    fire_list = list(nodes['fire'].keys())
    target_ids = sorted(targets.keys())
    
    print(f"目标数量: {len(target_ids)}")
    print(f"节点数量: 侦察{len(recon_list)}, 指挥{len(command_list)}, 火力{len(fire_list)}")
    
    # MOPSO主算法（纯PSO，直接搜索节点组合）
    print(f"\nMOPSO优化（{num_particles}粒子, {max_iterations}迭代）...")
    mopso_result = _mopso_search_pure(
        targets, nodes, preference_table,
        recon_list, command_list, fire_list, target_ids,
        num_particles, max_iterations, archive_size,
        use_hierarchical
    )
    
    # 生成帕累托前沿报告
    print("\n生成帕累托前沿报告...")
    pareto_report = _generate_pareto_report_pure(
        mopso_result['pareto_archive'], 
        nodes, targets
    )
    
    # 计算详细评估指标
    print("计算评估指标...")
    evaluation = _calculate_mopso_evaluation_pure(
        mopso_result['pareto_archive'],
        nodes, targets
    )

    # 为每个帕累托解生成详细方案（方案二）
    pareto_solutions = []
    # 可行链全集（可选，单次生成以复用）
    try:
        all_feasible_chains = generate_all_feasible_chains(targets, nodes)
    except Exception:
        all_feasible_chains = None
    for entry in mopso_result['pareto_archive']:
        try:
            # 结构 (objectives, allocation, position)
            _, final_allocation, _ = entry
        except Exception:
            final_allocation = None
        # 单解评估
        try:
            eval_detail = calculate_detailed_multi_target_metrics(final_allocation, nodes, targets, all_feasible_chains) if final_allocation else None
        except Exception:
            eval_detail = None
        # 单解报告（all_chain_status传None，函数内部自处理）
        try:
            alloc_report = generate_allocation_report(final_allocation, nodes, targets, None) if final_allocation else []
        except Exception:
            alloc_report = []
        pareto_solutions.append({
            'allocation_report': alloc_report,
            'evaluation': eval_detail,
            'redundancy_matrix': None,
            'final_allocation': final_allocation
        })

    print(f"\n[完成] 找到 {len(mopso_result['pareto_archive'])} 个帕累托最优解")
    print("=" * 60)
    
    return {
        'method_name': 'MOPSO多目标优化（两层层次化，6目标）' if use_hierarchical else 'MOPSO多目标优化（传统6目标）',
        'pareto_archive': mopso_result['pareto_archive'],
        'convergence_data': mopso_result['convergence_data'],
        'pareto_report': pareto_report,
        'evaluation': evaluation,
        'pareto_solutions': pareto_solutions,
        'num_particles': num_particles,
        'max_iterations': max_iterations,
        'hierarchical_mode': use_hierarchical
    }




# ============================================================================
# Pareto相关工具函数（被MOPSO使用）
# ============================================================================

def _is_dominated_mopso(obj1, obj2):
    """判断obj1是否被obj2支配（MOPSO专用）"""
    at_least_one_better = False
    for o1, o2 in zip(obj1, obj2):
        if o2 > o1:
            return False
        if o2 < o1:
            at_least_one_better = True
    return at_least_one_better


def _is_dominated_hierarchical(obj1, obj2):
    """
    层次化支配关系判断（两层帕累托）
    
    第一层：优先比较威胁度覆盖（obj[0]，已包含分配数量信息）
    第二层：在威胁度覆盖相同时，比较其他5个目标（obj[1:6]）
    
    参数：
        obj1, obj2: 6维目标函数向量（简化后）
        
    返回：
        True - obj1被obj2支配
        False - obj1不被obj2支配
    """
    # 提取威胁度覆盖（注意是负值*10，需要还原）
    threat1 = -obj1[0] / 10  # 还原实际威胁度
    threat2 = -obj2[0] / 10
    
    # 第一层：优先比较威胁度覆盖（威胁度越高，覆盖越好）
    if threat2 > threat1:
        return True  # obj2威胁度覆盖更高，obj1被支配
    elif threat2 < threat1:
        return False  # obj1威胁度覆盖更高，不被支配
    
    # 第二层：威胁度覆盖相同时，比较其他5个目标（传统帕累托支配）
    # obj[1:] 包括：成本、时间、精度、匹配度、火力
    at_least_one_better = False
    for o1, o2 in zip(obj1[1:], obj2[1:]):
        if o2 > o1:  # obj2在某个目标上更差
            return False
        if o2 < o1:  # obj2在某个目标上更好
            at_least_one_better = True
    
    return at_least_one_better


def _update_pareto_archive(archive, new_solution):
    """更新帕累托档案（传统支配关系）"""
    new_objectives, new_allocation, new_position = new_solution
    
    dominated = False
    to_remove = []
    
    for i, (arch_obj, arch_alloc, arch_pos) in enumerate(archive):
        if _is_dominated_mopso(new_objectives, arch_obj):
            dominated = True
            break
        elif _is_dominated_mopso(arch_obj, new_objectives):
            to_remove.append(i)
    
    if not dominated:
        for i in reversed(to_remove):
            archive.pop(i)
        archive.append((new_objectives, new_allocation, new_position))
    
    return archive


def _update_pareto_archive_hierarchical(archive, new_solution):
    """
    使用层次化支配关系更新帕累托档案
    
    第一层：优先保证最大化分配目标数
    第二层：在分配数相同时优化其他7个目标
    """
    new_objectives, new_allocation, new_position = new_solution
    
    dominated = False
    to_remove = []
    
    for i, (arch_obj, arch_alloc, arch_pos) in enumerate(archive):
        if _is_dominated_hierarchical(new_objectives, arch_obj):
            dominated = True  # 新解被档案中的解支配
            break
        elif _is_dominated_hierarchical(arch_obj, new_objectives):
            to_remove.append(i)  # 档案中的解被新解支配
    
    if not dominated:
        # 删除被支配的旧解
        for i in reversed(to_remove):
            archive.pop(i)
        # 添加新解
        archive.append((new_objectives, new_allocation, new_position))
    
    return archive


def _calculate_crowding_distance(objectives_list):
    """计算拥挤度距离"""
    num_solutions = len(objectives_list)
    if num_solutions == 0:
        return []
    
    num_objectives = len(objectives_list[0])
    crowding_distances = [0.0] * num_solutions
    
    for m in range(num_objectives):
        sorted_indices = sorted(range(num_solutions), 
                               key=lambda i: objectives_list[i][m])
        
        crowding_distances[sorted_indices[0]] = float('inf')
        crowding_distances[sorted_indices[-1]] = float('inf')
        
        obj_min = objectives_list[sorted_indices[0]][m]
        obj_max = objectives_list[sorted_indices[-1]][m]
        obj_range = obj_max - obj_min
        
        if obj_range > 0:
            for i in range(1, num_solutions - 1):
                idx = sorted_indices[i]
                crowding_distances[idx] += (
                    objectives_list[sorted_indices[i + 1]][m] -
                    objectives_list[sorted_indices[i - 1]][m]
                ) / obj_range
    
    return crowding_distances


def _crowding_distance_truncation(archive, max_size):
    """使用拥挤度距离裁剪档案"""
    if len(archive) <= max_size:
        return archive
    
    objectives_list = [obj for obj, _, _ in archive]
    crowding_distances = _calculate_crowding_distance(objectives_list)
    
    # 按拥挤度距离降序排序
    sorted_indices = sorted(range(len(archive)), 
                          key=lambda i: crowding_distances[i], 
                          reverse=True)
    
    # 保留前max_size个
    return [archive[i] for i in sorted_indices[:max_size]]


# ============================================================================
# 纯MOPSO版本 - 不使用预遍历，直接搜索节点组合
# ============================================================================

def _initialize_particle_smart(target_ids, targets, nodes, recon_list, command_list, fire_list):
    """
    智能初始化：根据距离约束选择节点。

    对每个目标依次挑选满足距离/射程条件的 o-c-w 组合，优先挑选尚未分配的火力节点，
    以便粒子群在初始阶段就具备较高的可行链比例。
    """
    position = []
    used_fire = set()  # 记录已使用的火力节点，避免冲突
    
    for target_id in target_ids:
        target = targets[target_id]
        target_coord = target['coord']
        
        # 找到距离内的侦察节点
        valid_recon = [
            i for i, rid in enumerate(recon_list)
            if distance(target_coord, nodes['recon'][rid]['coord']) <= nodes['recon'][rid]['range']
        ]
        
        if not valid_recon:
            # 没有可用侦察节点，随机选择
            recon_idx = np.random.randint(0, len(recon_list))
        else:
            recon_idx = valid_recon[np.random.randint(len(valid_recon))]
        
        recon_coord = nodes['recon'][recon_list[recon_idx]]['coord']
        
        # 找到能与侦察节点通信的指挥节点
        valid_command = [
            i for i, cid in enumerate(command_list)
            if distance(recon_coord, nodes['command'][cid]['coord']) <= nodes['command'][cid]['range']
        ]
        
        if not valid_command:
            # 若侦察节点与所有指挥节点都不连通，则随机选择一个，后续适应度会惩罚该粒子。
            command_idx = np.random.randint(0, len(command_list))
        else:
            command_idx = valid_command[np.random.randint(len(valid_command))]
        
        command_coord = nodes['command'][command_list[command_idx]]['coord']
        
        # 找到射程内且未使用的火力节点
        valid_fire = [
            i for i, fid in enumerate(fire_list)
            if (distance(command_coord, nodes['fire'][fid]['coord']) <= nodes['command'][command_list[command_idx]]['range']
                and distance(nodes['fire'][fid]['coord'], target_coord) <= nodes['fire'][fid]['range']
                and fid not in used_fire)
        ]
        
        if valid_fire:
            fire_idx = valid_fire[np.random.randint(len(valid_fire))]
            used_fire.add(fire_list[fire_idx])
        else:
            # 找不到不冲突的火力节点，尝试找任何距离内的
            any_valid_fire = [
                i for i, fid in enumerate(fire_list)
                if (distance(command_coord, nodes['fire'][fid]['coord']) <= nodes['command'][command_list[command_idx]]['range']
                    and distance(nodes['fire'][fid]['coord'], target_coord) <= nodes['fire'][fid]['range'])
            ]
            if any_valid_fire:
                fire_idx = any_valid_fire[np.random.randint(len(any_valid_fire))]
            else:
                fire_idx = -1  # 不分配
        
        position.extend([recon_idx, command_idx, fire_idx])
    
    return position


def _mopso_search_pure(
    targets, nodes, preference_table,
    recon_list, command_list, fire_list, target_ids,
    num_particles, max_iterations, archive_size,
    use_hierarchical=True
):
    """
    纯PSO搜索：直接编码节点选择，不预先生成可行链
    
    粒子编码：
    - 每个目标需要3个节点：侦察、指挥、火力
    - position[i*3]   = 侦察节点索引
    - position[i*3+1] = 指挥节点索引  
    - position[i*3+2] = 火力节点索引（-1表示不分配）
    
    参数：
        use_hierarchical: 是否使用层次化帕累托优化
    """
    
    # PSO参数
    w_start = 0.9
    w_end = 0.4
    c1 = 2.0
    c2 = 2.0
    
    num_targets = len(target_ids)
    num_recon = len(recon_list)
    num_command = len(command_list)
    num_fire = len(fire_list)
    particle_dim = num_targets * 3
    
    # 初始化粒子群
    particles = []
    velocities = []
    personal_best_archives = []
    global_pareto_archive = []
    
    print("初始化粒子群...")
    for i in range(num_particles):
        if i < num_particles // 3:
            # 前1/3粒子：智能初始化（距离引导）
            position = _initialize_particle_smart(
                target_ids, targets, nodes, 
                recon_list, command_list, fire_list
            )
        else:
            # 后2/3粒子：随机初始化（保持多样性）
            position = []
            for t_idx in range(num_targets):
                recon_idx = np.random.randint(0, num_recon)
                command_idx = np.random.randint(0, num_command)
                if np.random.random() < 0.8:
                    fire_idx = np.random.randint(0, num_fire)
                else:
                    fire_idx = -1
                position.extend([recon_idx, command_idx, fire_idx])
        
        particles.append(position)
        velocities.append([np.random.uniform(-2, 2) for _ in range(particle_dim)])
        personal_best_archives.append([])
    
    convergence_data = []
    
    # MOPSO主循环
    for iteration in range(max_iterations):
        w = w_start - (w_start - w_end) * (iteration / max_iterations)
        
        feasible_count = 0
        for i in range(num_particles):
            # 评估粒子
            is_feasible, objectives, allocation = _evaluate_particle_pure(
                particles[i], target_ids, recon_list, command_list, fire_list,
                nodes, targets, preference_table
            )
            
            if is_feasible and allocation:
                feasible_count += 1
                # 根据模式选择档案更新策略
                if use_hierarchical:
                    # 使用层次化支配关系
                    personal_best_archives[i] = _update_pareto_archive_hierarchical(
                        personal_best_archives[i],
                        (objectives, allocation, particles[i].copy())
                    )
                    global_pareto_archive = _update_pareto_archive_hierarchical(
                        global_pareto_archive,
                        (objectives, allocation, particles[i].copy())
                    )
                else:
                    # 使用传统支配关系
                    personal_best_archives[i] = _update_pareto_archive(
                        personal_best_archives[i],
                        (objectives, allocation, particles[i].copy())
                    )
                    global_pareto_archive = _update_pareto_archive(
                        global_pareto_archive,
                        (objectives, allocation, particles[i].copy())
                    )
        
        # 限制档案大小
        if len(global_pareto_archive) > archive_size:
            global_pareto_archive = _crowding_distance_truncation(
                global_pareto_archive, archive_size
            )
        
        # 记录收敛数据
        if global_pareto_archive:
            avg_objectives = np.mean([obj for obj, _, _ in global_pareto_archive], axis=0)
            convergence_data.append({
                'iteration': iteration,
                'pareto_size': len(global_pareto_archive),
                'avg_objectives': avg_objectives.tolist()
            })
        
        # 更新粒子
        for i in range(num_particles):
            personal_guide = _select_guide_pure(personal_best_archives[i], particles[i], particle_dim)
            global_guide = _select_guide_pure(global_pareto_archive, particles[i], particle_dim)
            
            for j in range(particle_dim):
                r1, r2 = np.random.random(), np.random.random()
                velocities[i][j] = (
                    w * velocities[i][j] +
                    c1 * r1 * (personal_guide[j] - particles[i][j]) +
                    c2 * r2 * (global_guide[j] - particles[i][j])
                )
                particles[i][j] = particles[i][j] + velocities[i][j]
                
                # 边界处理
                dim_type = j % 3
                if dim_type == 0:  # 侦察节点
                    particles[i][j] = int(np.clip(particles[i][j], 0, num_recon - 1))
                elif dim_type == 1:  # 指挥节点
                    particles[i][j] = int(np.clip(particles[i][j], 0, num_command - 1))
                else:  # 火力节点
                    particles[i][j] = int(np.clip(particles[i][j], -1, num_fire - 1))
        
        # 打印进度
        if iteration == 0 or iteration % 20 == 0 or iteration == max_iterations - 1:
            print(f"  迭代 {iteration:3d}/{max_iterations}: "
                  f"可行解 = {feasible_count:2d}/{num_particles}, "
                  f"帕累托解数 = {len(global_pareto_archive):3d}")
    
    return {
        'pareto_archive': global_pareto_archive,
        'convergence_data': convergence_data
    }


def _evaluate_particle_pure(particle, target_ids, recon_list, command_list, fire_list,
                            nodes, targets, preference_table):
    """
    渐进式粒子评估：逐目标尝试分配，最大化利用粒子价值
    
    改进要点：
    1. 实时跟踪资源占用（火力、指挥容量、侦察并行）
    2. 逐个目标检查约束，失败的目标不影响其他目标
    3. 返回所有成功分配的部分（而非全有或全无）
    """
    allocation = {}
    
    # 实时跟踪资源使用情况（渐进式分配的核心）
    used_fires = set()           # 已使用的火力节点
    used_command_count = {}      # 指挥节点使用计数 {command_id: count}
    used_recon_count = {}        # 侦察节点使用计数 {recon_id: count}
    
    # 逐个目标尝试分配
    for t_idx, target_id in enumerate(target_ids):
        # 解码节点索引
        recon_idx = int(particle[t_idx * 3])
        command_idx = int(particle[t_idx * 3 + 1])
        fire_idx = int(particle[t_idx * 3 + 2])
        
        if fire_idx == -1:
            continue  # 不分配该目标
        
        # 获取节点
        recon_id = recon_list[recon_idx]
        command_id = command_list[command_idx]
        fire_id = fire_list[fire_idx]
        
        recon_node = nodes['recon'][recon_id]
        command_node = nodes['command'][command_id]
        fire_node = nodes['fire'][fire_id]
        target = targets[target_id]
        target_coord = target['coord']
        
        # ========== 渐进式约束检查 ==========
        
        # 约束1：距离可达性
        if distance(target_coord, recon_node['coord']) > recon_node['range']:
            continue  # 该目标失败，继续下一个
        if distance(recon_node['coord'], command_node['coord']) > command_node['range']:
            continue  # 该目标失败，继续下一个
        if distance(command_node['coord'], fire_node['coord']) > command_node['range']:
            continue  # 该目标失败，继续下一个
        if distance(fire_node['coord'], target_coord) > fire_node['range']:
            continue  # 该目标失败，继续下一个
        
        # 约束2：火力节点唯一性（实时检查）
        if fire_id in used_fires:
            continue  # 火力冲突，跳过该目标
        
        # 约束3：指挥节点容量限制（实时检查）
        command_capacity = command_node.get('command_capacity', float('inf'))
        current_command_usage = used_command_count.get(command_id, 0)
        if current_command_usage >= command_capacity:
            continue  # 指挥容量满，跳过该目标
        
        # 约束4：侦察节点并行上限（实时检查）
        recon_parallel = recon_node.get('parallel_limit', float('inf'))
        current_recon_usage = used_recon_count.get(recon_id, 0)
        if current_recon_usage >= recon_parallel:
            continue  # 侦察并行满，跳过该目标
        
        # ========== 所有约束满足，分配成功 ==========
        
        # 计算链性能
        reaction_time = (recon_node['t_deal'] + command_node['t_deal'] + 
                        fire_node['t_deal'] + fire_node.get('t_flight', 0))
        precision = recon_node['sigma2'] + fire_node['sigma2']
        fire_power = fire_node['ammo']['count'] * fire_node['ammo']['omega']
        tortuosity, cross_count = _calculate_chain_shape_metrics(
            target_coord, recon_node['coord'], command_node['coord'], fire_node['coord']
        )
        ammo_cost = fire_node['ammo'].get('cost', 0)
        
        allocation[target_id] = {
            'target_id': target_id,
            'target_type': target['type'],
            'recon_id': recon_id,
            'command_id': command_id,
                'fire_id': fire_id,
                'fire_type': fire_node['firepower_type'],
                'ammo_type': fire_node['ammo_type'],
                'metrics': {
                    'reaction_time': reaction_time,
                    'precision': precision,
                    'fire_power': fire_power,
                    'tortuosity': tortuosity,
                    'cross_count': cross_count,
                    'recon_type': recon_node.get('model', '未知'),
                    'ammo_cost': ammo_cost
                }
        }
        
        # 更新资源占用状态（关键：实时更新）
        used_fires.add(fire_id)
        used_command_count[command_id] = current_command_usage + 1
        used_recon_count[recon_id] = current_recon_usage + 1
    
    # ========== 接受部分成功的分配 ==========
    
    if not allocation:
        return False, None, None  # 完全失败才拒绝
    
    # 计算目标函数（基于实际分配的目标）
    objectives = _calculate_objectives_pure(allocation, targets, nodes, preference_table)
    return True, objectives, allocation  # 返回部分成功的分配


def _calculate_objectives_pure(allocation, targets, nodes, preference_table):
    """
    计算6个目标函数值（全部转换为最小化问题）
    
    简化说明：
    - 原8个目标合并为6个：f1+f2合并（威胁度覆盖已包含数量信息），f6删除（资源利用通过f5和层次化保证）
    
    目标优先级：
    1. 最大化威胁度覆盖（已包含分配目标数信息，转换为最小化负威胁度）
    2. 最小化总成本
    3. 最小化平均反应时间
    4. 最小化平均精度
    5. 最小化弹目不匹配度
    6. 最大化火力能力（转换为最小化负火力）
    """
    
    allocated_count = len(allocation)
    
    # 目标1: 最大化威胁度覆盖 → 最小化负威胁度（放大10倍权重，原f1+f2合并）
    # 威胁度覆盖已包含分配数量和质量双重信息，比单纯计数更有意义
    if allocation:
        f1_neg_threat = -sum(targets[tid]['threat_level'] for tid in allocation.keys()) * 10
    else:
        f1_neg_threat = 0
    
    # 目标2: 最小化总成本（原f3）
    f2_total_cost = 0.0
    for chain in allocation.values():
        _c = chain['metrics'].get('ammo_cost', 0)
        try:
            f2_total_cost += float(_c)
        except Exception:
            continue
    
    # 目标3: 最小化平均反应时间（原f4）
    if allocation:
        f3_avg_reaction_time = sum(chain['metrics']['reaction_time'] for chain in allocation.values()) / allocated_count
    else:
        f3_avg_reaction_time = 999999
    
    # 目标4: 最小化平均精度（σ²）（原f5）
    if allocation:
        f4_avg_precision = sum(chain['metrics']['precision'] for chain in allocation.values()) / allocated_count
    else:
        f4_avg_precision = 999999
    
    # 目标5: 最小化弹目不匹配度（原f7）
    # preference_rank范围1-4（1最好，4最差），如果找不到匹配则使用最差值4
    f5_preference_score = sum(
        preference_table.get((chain['fire_type'], chain['target_type']), 4)
        for chain in allocation.values()
    )
    
    # 目标6: 最大化总火力能力 → 最小化负火力（原f8）
    # 删除原f6（火力利用率），因为：1)通过层次化已优先分配更多目标，利用率自然提升
    # 2)总火力f6已能反映资源利用效果，单独利用率指标冗余
    if allocation:
        total_firepower = sum(chain['metrics']['fire_power'] for chain in allocation.values())
        f6_neg_firepower = -total_firepower
    else:
        f6_neg_firepower = 0
    
    return [f1_neg_threat, f2_total_cost, f3_avg_reaction_time, 
            f4_avg_precision, f5_preference_score, f6_neg_firepower]


def _select_guide_pure(archive, current_position, particle_dim):
    """从档案中选择引导解"""
    if not archive:
        return current_position
    
    objectives_list = [obj for obj, _, _ in archive]
    crowding_distances = _calculate_crowding_distance(objectives_list)
    
    total_distance = sum(d for d in crowding_distances if d != float('inf'))
    if total_distance == 0:
        return archive[0][2]
    
    finite_indices = [i for i, d in enumerate(crowding_distances) if d != float('inf')]
    if not finite_indices:
        return archive[0][2]
    
    finite_distances = [crowding_distances[i] for i in finite_indices]
    probabilities = [d / total_distance for d in finite_distances]
    
    selected_idx = finite_indices[np.random.choice(len(finite_indices), p=probabilities)]
    return archive[selected_idx][2]


def _generate_pareto_report_pure(pareto_archive, nodes, targets):
    """生成帕累托前沿报告（6目标简化版）"""
    if not pareto_archive:
        return pd.DataFrame()
    
    report = []
    for idx, (objectives, allocation, position) in enumerate(pareto_archive, 1):
        # 将负值还原为正值以便显示（注意：已放大的权重需要除回来）
        threat_coverage = -int(objectives[0]) // 10  # f1是负的威胁度*10（合并了原f1+f2）
        # 从分配方案中提取实际分配目标数（用于显示）
        allocated_count = len(allocation) if allocation else 0
        total_cost = objectives[1]  # f2: 总成本
        avg_reaction_time = objectives[2]  # f3: 平均反应时间
        avg_precision = objectives[3]  # f4: 平均精度
        preference_mismatch_sum = objectives[4]  # f5: 弹目不匹配度总和
        total_firepower = -objectives[5]  # f6: 总火力能力（取负还原）
        
        plan_tortuosity, chain_crossings = _calculate_plan_geometry_metrics(allocation or {}, nodes, targets)
        
        # 计算平均弹目匹配度：preference_rank范围1-4（1最好，4最差），转换为0-10匹配度
        # 公式：(4 - avg_rank) / 3 * 10，使得1->10, 2->6.67, 3->3.33, 4->0
        if allocated_count > 0:
            avg_preference_rank = preference_mismatch_sum / allocated_count
            # 将preference_rank (1-4) 转换为匹配度分数 (0-10)
            # preference_rank越小越好(1最好)，所以匹配度 = (4 - rank) / 3 * 10
            match_score = (4 - avg_preference_rank) / 3 * 10
            match_score = max(0, min(10, match_score))  # 限制在0-10范围内
        else:
            match_score = 0
        
        row = {
            '方案编号': f'P{idx}',
            '分配目标数': allocated_count,  # 从实际分配中计算
            '威胁度覆盖': threat_coverage,  # 合并后的威胁度指标
            '总成本': round(total_cost, 0),
            '平均反应时间(s)': round(avg_reaction_time, 2),
            '平均精度(σ²)': round(avg_precision, 2),
            '弹目匹配度': round(match_score, 1),
            '总火力能力': round(total_firepower, 0),
            '总体方案曲折度': round(plan_tortuosity, 2),
            '方案链间交叉数': chain_crossings
            # 删除了"火力利用率"，已通过总火力和层次化保证
        }
        report.append(row)
    
    df = pd.DataFrame(report)
    
    if not df.empty:
        df['推荐'] = ''
        # 标记各指标最优解
        coverage_best = df['分配目标数'].idxmax()
        threat_best = df['威胁度覆盖'].idxmax()
        
        # 合并覆盖最优和威胁最优（因为威胁度覆盖已包含分配数量信息）
        if coverage_best == threat_best:
            # 同一个解，合并标记
            df.loc[coverage_best, '推荐'] = '✓ 覆盖/威胁最优'
        else:
            # 不同解，分别标记（这种情况较少见）
            df.loc[coverage_best, '推荐'] = '✓ 覆盖最优'
            if df.loc[threat_best, '推荐'] == '':
                df.loc[threat_best, '推荐'] = '✓ 威胁最优'
            elif '威胁最优' not in df.loc[threat_best, '推荐']:
                df.loc[threat_best, '推荐'] += ' | 威胁最优'
        
        # 避免重复标记同一行
        cost_best = df['总成本'].idxmin()
        if df.loc[cost_best, '推荐'] == '':
            df.loc[cost_best, '推荐'] = '✓ 成本最优'
        elif '成本最优' not in df.loc[cost_best, '推荐']:
            df.loc[cost_best, '推荐'] += ' | 成本最优'
            
        time_best = df['平均反应时间(s)'].idxmin()
        if df.loc[time_best, '推荐'] == '':
            df.loc[time_best, '推荐'] = '✓ 时间最优'
        elif '时间最优' not in df.loc[time_best, '推荐']:
            df.loc[time_best, '推荐'] += ' | 时间最优'
            
        precision_best = df['平均精度(σ²)'].idxmin()
        if df.loc[precision_best, '推荐'] == '':
            df.loc[precision_best, '推荐'] = '✓ 精度最优'
        elif '精度最优' not in df.loc[precision_best, '推荐']:
            df.loc[precision_best, '推荐'] += ' | 精度最优'
    
    return df


def _calculate_mopso_evaluation_pure(pareto_archive, nodes, targets):
    """计算评估指标（优化后，包含分配目标数统计）"""
    if not pareto_archive:
        return {
            'pareto_size': 0,
            'max_allocated': 0,
            'avg_allocated': 0,
            'coverage_rate': 0
        }
    
    all_objectives = [obj for obj, _, _ in pareto_archive]
    obj_array = np.array(all_objectives)
    
    # 提取分配目标数（第一个目标，需要取负并除以权重10）
    allocated_counts = -obj_array[:, 0] / 10
    max_allocated = int(allocated_counts.max())
    avg_allocated = allocated_counts.mean()
    
    total_targets = len(targets)
    coverage_rate = max_allocated / total_targets * 100 if total_targets > 0 else 0
    
    return {
        'pareto_size': len(pareto_archive),
        'total_targets': total_targets,
        'max_allocated': max_allocated,
        'avg_allocated': round(avg_allocated, 1),
        'coverage_rate': round(coverage_rate, 1),
        'objectives_min': obj_array.min(axis=0).tolist(),
        'objectives_max': obj_array.max(axis=0).tolist(),
        'objectives_mean': obj_array.mean(axis=0).tolist(),
        'objectives_std': obj_array.std(axis=0).tolist()
    }
