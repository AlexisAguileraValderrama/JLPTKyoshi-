from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError
import os
import uuid
from datetime import datetime, timezone

_container = None


def _get():
    global _container
    if _container is None:
        client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
        db = client.create_database_if_not_exists(
            os.environ.get("COSMOS_DATABASE", "jlptkyoshi")
        )
        _container = db.create_container_if_not_exists(
            id="jlpt",
            partition_key=PartitionKey(path="/user_id"),
        )
    return _container


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clean(item: dict) -> dict:
    """Strip Cosmos metadata and internal fields before sending to the client."""
    return {k: v for k, v in item.items() if not k.startswith("_") and k not in ("type", "user_id")}


# ── Notebooks ──

def get_notebooks(user_id: str) -> list:
    rows = _get().query_items(
        "SELECT * FROM c WHERE c.user_id=@u AND c.type='notebook' ORDER BY c.created_at DESC",
        parameters=[{"name": "@u", "value": user_id}],
        partition_key=user_id,
    )
    return [_clean(r) for r in rows]


def create_notebook(user_id: str, name: str, subtitle) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "type": "notebook",
        "user_id": user_id,
        "name": name,
        "subtitle": subtitle,
        "created_at": _now(),
    }
    return _clean(_get().create_item(doc))


def get_notebook(user_id: str, notebook_id: str) -> dict | None:
    try:
        return _get().read_item(item=notebook_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return None


def update_notebook(user_id: str, notebook_id: str, name: str, subtitle) -> dict | None:
    item = get_notebook(user_id, notebook_id)
    if not item:
        return None
    item["name"] = name
    item["subtitle"] = subtitle
    return _clean(_get().replace_item(item=notebook_id, body=item))


def delete_notebook(user_id: str, notebook_id: str):
    for section in get_grammar_sections_raw(user_id, notebook_id):
        delete_grammar_section(user_id, section["id"])
    _get().delete_item(item=notebook_id, partition_key=user_id)


# ── Grammar Sections ──

def get_grammar_sections_raw(user_id: str, notebook_id: str) -> list:
    rows = _get().query_items(
        "SELECT * FROM c WHERE c.user_id=@u AND c.type='grammar_section' AND c.notebook_id=@nb ORDER BY c.created_at ASC",
        parameters=[{"name": "@u", "value": user_id}, {"name": "@nb", "value": notebook_id}],
        partition_key=user_id,
    )
    return list(rows)


def get_grammar_sections(user_id: str, notebook_id: str) -> list:
    return [_clean(r) for r in get_grammar_sections_raw(user_id, notebook_id)]


def create_grammar_section(user_id: str, notebook_id: str, grammar_input: str) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "type": "grammar_section",
        "user_id": user_id,
        "notebook_id": notebook_id,
        "grammar_input": grammar_input,
        "ai_summary": None,
        "created_at": _now(),
    }
    return _clean(_get().create_item(doc))


def get_grammar_section(user_id: str, section_id: str) -> dict | None:
    try:
        return _get().read_item(item=section_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return None


def update_grammar_summary(user_id: str, section_id: str, summary: str) -> dict | None:
    item = get_grammar_section(user_id, section_id)
    if not item:
        return None
    item["ai_summary"] = summary
    return _clean(_get().replace_item(item=section_id, body=item))


def delete_grammar_section(user_id: str, section_id: str):
    for ex in get_exercises_raw(user_id, section_id):
        _get().delete_item(item=ex["id"], partition_key=user_id)
    for qa in get_qas_raw(user_id, section_id):
        _get().delete_item(item=qa["id"], partition_key=user_id)
    _get().delete_item(item=section_id, partition_key=user_id)


# ── Exercises ──

def get_exercises_raw(user_id: str, section_id: str) -> list:
    rows = _get().query_items(
        "SELECT * FROM c WHERE c.user_id=@u AND c.type='exercise' AND c.grammar_section_id=@gs ORDER BY c.created_at ASC",
        parameters=[{"name": "@u", "value": user_id}, {"name": "@gs", "value": section_id}],
        partition_key=user_id,
    )
    return list(rows)


def get_exercises(user_id: str, section_id: str) -> list:
    return [_clean(r) for r in get_exercises_raw(user_id, section_id)]


def create_exercise(user_id: str, section_id: str) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "type": "exercise",
        "user_id": user_id,
        "grammar_section_id": section_id,
        "user_input": "",
        "ai_feedback": None,
        "created_at": _now(),
    }
    return _clean(_get().create_item(doc))


def get_exercise(user_id: str, exercise_id: str) -> dict | None:
    try:
        return _get().read_item(item=exercise_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return None


def update_exercise_input(user_id: str, exercise_id: str, user_input: str) -> dict | None:
    item = get_exercise(user_id, exercise_id)
    if not item:
        return None
    item["user_input"] = user_input
    return _clean(_get().replace_item(item=exercise_id, body=item))


def update_exercise_feedback(user_id: str, exercise_id: str, feedback: str) -> dict | None:
    item = get_exercise(user_id, exercise_id)
    if not item:
        return None
    item["ai_feedback"] = feedback
    return _clean(_get().replace_item(item=exercise_id, body=item))


def delete_exercise(user_id: str, exercise_id: str):
    _get().delete_item(item=exercise_id, partition_key=user_id)


# ── Q&A ──

def get_qas(user_id: str, section_id: str) -> list:
    rows = _get().query_items(
        "SELECT * FROM c WHERE c.user_id=@u AND c.type='qa' AND c.grammar_section_id=@gs ORDER BY c.created_at ASC",
        parameters=[{"name": "@u", "value": user_id}, {"name": "@gs", "value": section_id}],
        partition_key=user_id,
    )
    return [_clean(r) for r in rows]


def create_qa(user_id: str, section_id: str, question: str) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "type": "qa",
        "user_id": user_id,
        "grammar_section_id": section_id,
        "question": question,
        "ai_answer": None,
        "created_at": _now(),
    }
    return _clean(_get().create_item(doc))


def get_qa(user_id: str, qa_id: str) -> dict | None:
    try:
        return _get().read_item(item=qa_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return None


def update_qa_answer(user_id: str, qa_id: str, answer: str) -> dict | None:
    item = get_qa(user_id, qa_id)
    if not item:
        return None
    item["ai_answer"] = answer
    return _clean(_get().replace_item(item=qa_id, body=item))


def delete_qa(user_id: str, qa_id: str):
    _get().delete_item(item=qa_id, partition_key=user_id)


def get_qas_raw(user_id: str, section_id: str) -> list:
    rows = _get().query_items(
        "SELECT * FROM c WHERE c.user_id=@u AND c.type='qa' AND c.grammar_section_id=@gs",
        parameters=[{"name": "@u", "value": user_id}, {"name": "@gs", "value": section_id}],
        partition_key=user_id,
    )
    return list(rows)
