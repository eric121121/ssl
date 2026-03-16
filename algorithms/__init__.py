"""算法包入口，提供单目标与多目标算法接口。"""
from .single_target import loop_method, pso_method
from .multi_target import (
    enhanced_multi_target_ssl_allocation,
    mopso_multi_target_allocation,
    calculate_detailed_multi_target_metrics,
    generate_allocation_report,
)

__all__ = [
    "loop_method",
    "pso_method",
    "enhanced_multi_target_ssl_allocation",
    "mopso_multi_target_allocation",
    "calculate_detailed_multi_target_metrics",
    "generate_allocation_report",
]
