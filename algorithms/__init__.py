"""算法包入口，提供单目标与多目标算法接口。"""
from .single_target import loop_method, pso_method
from .multi_target import (
    enhanced_multi_target_ssl_allocation,
    mopso_multi_target_allocation,
    calculate_detailed_multi_target_metrics,
    generate_allocation_report,
)
from .moving_target import (
    is_movable_target,
    is_movable_node,
    calculate_moving_position,
    update_target_position,
    update_node_position,
    update_all_positions,
    get_target_trajectory,
    has_movable_targets,
    MOVABLE_TARGET_TYPES,
    MOVABLE_NODE_TYPES,
)

__all__ = [
    "loop_method",
    "pso_method",
    "enhanced_multi_target_ssl_allocation",
    "mopso_multi_target_allocation",
    "calculate_detailed_multi_target_metrics",
    "generate_allocation_report",
    "is_movable_target",
    "is_movable_node",
    "calculate_moving_position",
    "update_target_position",
    "update_node_position",
    "update_all_positions",
    "get_target_trajectory",
    "has_movable_targets",
    "MOVABLE_TARGET_TYPES",
    "MOVABLE_NODE_TYPES",
]
