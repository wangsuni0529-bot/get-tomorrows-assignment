"""Local mute list. This file never leaves the student's computer."""

import json
from pathlib import Path
from typing import Any

DEFAULT_MEMORY: dict[str, Any] = {
    "muted_assignment_ids": [],
    "muted_prep_keys": [],
    "preferences": {
        "reminder_mode": "balanced",
    },
}


def load_memory(path: str = ".study_agent_memory.json") -> dict[str, Any]:
    """Read the mute list, or return the default when the file is missing or broken."""
    memory_path = Path(path)

    if not memory_path.exists():
        return DEFAULT_MEMORY.copy()

    try:
        data = json.loads(memory_path.read_text())
    except json.JSONDecodeError:
        return DEFAULT_MEMORY.copy()

    memory = DEFAULT_MEMORY.copy()
    memory.update(data)
    memory.setdefault("muted_assignment_ids", [])
    memory.setdefault("muted_prep_keys", [])
    memory.setdefault("preferences", DEFAULT_MEMORY["preferences"].copy())

    return memory


def save_memory(memory: dict[str, Any], path: str = ".study_agent_memory.json") -> None:
    """Write the mute list as JSON."""
    memory_path = Path(path)
    memory_path.write_text(json.dumps(memory, indent=2, sort_keys=True) + "\n")


def mute_assignment(assignment_id: Any, path: str = ".study_agent_memory.json") -> None:
    """Hide one assignment on later runs."""
    memory = load_memory(path)
    muted_ids = {str(item_id) for item_id in memory.get("muted_assignment_ids", [])}
    muted_ids.add(str(assignment_id))
    memory["muted_assignment_ids"] = sorted(muted_ids)
    save_memory(memory, path)


def is_assignment_muted(assignment_id: Any, memory: dict[str, Any]) -> bool:
    """Return whether this assignment id is in the mute list."""
    if assignment_id is None:
        return False

    muted_ids = {str(item_id) for item_id in memory.get("muted_assignment_ids", [])}
    return str(assignment_id) in muted_ids


def mute_prep(prep_key: Any, path: str = ".study_agent_memory.json") -> None:
    """Hide one prep item on later runs."""
    memory = load_memory(path)
    muted_keys = {str(item_key) for item_key in memory.get("muted_prep_keys", [])}
    muted_keys.add(str(prep_key))
    memory["muted_prep_keys"] = sorted(muted_keys)
    save_memory(memory, path)


def is_prep_muted(prep_key: Any, memory: dict[str, Any]) -> bool:
    """Return whether this prep key is in the mute list."""
    if not prep_key:
        return False

    muted_keys = {str(item_key) for item_key in memory.get("muted_prep_keys", [])}
    return str(prep_key) in muted_keys
