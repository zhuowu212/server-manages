EDITOR_TRANSITIONS = {
    ("planned", "purchased"),
    ("purchased", "racked"),
    ("racked", "active"),
    ("active", "repair"),
    ("active", "retired"),
    ("repair", "active"),
}

ALL_STATUSES = {"planned", "purchased", "racked", "active", "repair", "retired"}
ALL_TYPES = {"physical", "virtual", "network", "storage"}
VALID_HOST_STATUSES = {"racked", "active", "repair"}


def editor_can_transition(current: str, target: str) -> bool:
    return current == target or (current, target) in EDITOR_TRANSITIONS
