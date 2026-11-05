"""Pure default development scenario. Creating it is an explicit CLI action."""
from copy import deepcopy

DEFAULT_RUN_ID = "demo-campus-run"
DEFAULT_EXPERIMENT_ID = "demo-campus-experiment"

_CONFIG = {
    "name": "社团活动筹备", "schema_version": 1, "seed": 7,
    "locations": [
        {"location_id": "teaching-building", "name": "教学楼", "position": {"x": 120, "y": 100}},
        {"location_id": "library", "name": "图书馆", "position": {"x": 350, "y": 100}},
        {"location_id": "activity-room", "name": "活动室", "position": {"x": 580, "y": 100}},
        {"location_id": "cafeteria", "name": "食堂", "position": {"x": 220, "y": 300}},
        {"location_id": "playground", "name": "操场", "position": {"x": 500, "y": 300}},
    ],
    "agents": [
        {"agent_id": "chen-yu", "name": "陈宇", "location_id": "teaching-building", "interests": ["编程", "读书"]},
        {"agent_id": "lin-xia", "name": "林夏", "location_id": "library", "interests": ["文学"]},
        {"agent_id": "zhou-ning", "name": "周宁", "location_id": "activity-room", "interests": ["组织活动"]},
        {"agent_id": "li-mu", "name": "李沐", "location_id": "cafeteria", "interests": ["美食"]},
        {"agent_id": "wang-yue", "name": "王悦", "location_id": "playground", "interests": ["运动"]},
        {"agent_id": "zhao-hang", "name": "赵航", "location_id": "teaching-building", "interests": ["摄影"]},
        {"agent_id": "sun-ke", "name": "孙可", "location_id": "library", "interests": ["阅读"]},
        {"agent_id": "xu-an", "name": "许安", "location_id": "activity-room", "interests": ["音乐"]},
    ],
}


def default_config() -> dict:
    return deepcopy(_CONFIG)
