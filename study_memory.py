import json
from pathlib import Path


DEFAULT_MEMORY = {
    "muted_assignment_ids": [],
    "muted_prep_keys": [],
    "preferences": {
        "reminder_mode": "balanced",
    },
}


def load_memory(path=".study_agent_memory.json"):
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


def save_memory(memory, path=".study_agent_memory.json"):
    memory_path = Path(path)
    memory_path.write_text(json.dumps(memory, indent=2, sort_keys=True) + "\n")


def mute_assignment(assignment_id, path=".study_agent_memory.json"):
    memory = load_memory(path)
    muted_ids = {str(item_id) for item_id in memory.get("muted_assignment_ids", [])}
    muted_ids.add(str(assignment_id))
    memory["muted_assignment_ids"] = sorted(muted_ids)
    save_memory(memory, path)


def is_assignment_muted(assignment_id, memory):
    if assignment_id is None:
        return False

    muted_ids = {str(item_id) for item_id in memory.get("muted_assignment_ids", [])}
    return str(assignment_id) in muted_ids


def mute_prep(prep_key, path=".study_agent_memory.json"):
    memory = load_memory(path)
    muted_keys = {str(item_key) for item_key in memory.get("muted_prep_keys", [])}
    muted_keys.add(str(prep_key))
    memory["muted_prep_keys"] = sorted(muted_keys)
    save_memory(memory, path)


def is_prep_muted(prep_key, memory):
    if not prep_key:
        return False

    muted_keys = {str(item_key) for item_key in memory.get("muted_prep_keys", [])}
    return str(prep_key) in muted_keys
