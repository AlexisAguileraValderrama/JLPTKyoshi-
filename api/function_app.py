import azure.functions as func
import json
import base64
import logging
import database as db
import ai_client

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _user_id(req: func.HttpRequest) -> str | None:
    header = req.headers.get("x-ms-client-principal")
    if not header:
        return None
    try:
        data = json.loads(base64.b64decode(header + "=="))
        return data.get("userId")
    except Exception:
        return None


def _json(data, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(data, default=str),
        status_code=status,
        mimetype="application/json",
    )


def _err(msg: str, status: int = 400) -> func.HttpResponse:
    return _json({"error": msg}, status)


# ── Notebooks ──────────────────────────────────────────────────────────────────

@app.route(route="notebooks", methods=["GET", "POST"])
def notebooks(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)

    if req.method == "GET":
        return _json(db.get_notebooks(uid))

    try:
        body = req.get_json()
    except ValueError:
        body = {}
    name = (body.get("name") or "").strip()
    subtitle = (body.get("subtitle") or "").strip() or None
    if not name:
        return _err("Name is required")
    nb = db.create_notebook(uid, name, subtitle)
    return _json(nb, 201)


@app.route(route="notebooks/{notebook_id}", methods=["DELETE", "PATCH"])
def notebook_by_id(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    notebook_id = req.route_params.get("notebook_id")

    if req.method == "DELETE":
        db.delete_notebook(uid, notebook_id)
        return _json({"ok": True})

    try:
        body = req.get_json()
    except ValueError:
        body = {}
    name = (body.get("name") or "").strip()
    subtitle = (body.get("subtitle") or "").strip() or None
    if not name:
        return _err("Name is required")
    updated = db.update_notebook(uid, notebook_id, name, subtitle)
    if not updated:
        return _err("Not found", 404)
    return _json(updated)


# ── Grammar Sections ───────────────────────────────────────────────────────────

@app.route(route="notebooks/{notebook_id}/grammar", methods=["GET", "POST"])
def grammar_sections(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    notebook_id = req.route_params.get("notebook_id")

    if req.method == "GET":
        return _json(db.get_grammar_sections(uid, notebook_id))

    try:
        body = req.get_json()
    except ValueError:
        body = {}
    grammar_input = (body.get("grammar_input") or "").strip()
    if not grammar_input:
        return _err("Grammar input is required")
    section = db.create_grammar_section(uid, notebook_id, grammar_input)
    return _json(section, 201)


@app.route(route="notebooks/{notebook_id}/grammar/reorder", methods=["POST"])
def reorder_grammar(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    notebook_id = req.route_params.get("notebook_id")
    try:
        body = req.get_json()
    except ValueError:
        body = {}
    ids = body.get("ids", [])
    if not ids:
        return _err("ids is required")
    db.reorder_grammar_sections(uid, notebook_id, ids)
    return _json({"ok": True})


@app.route(route="grammar/{section_id}", methods=["DELETE"])
def grammar_section_by_id(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    section_id = req.route_params.get("section_id")
    db.delete_grammar_section(uid, section_id)
    return _json({"ok": True})


@app.route(route="grammar/{section_id}/summarize", methods=["POST"])
def summarize(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    section_id = req.route_params.get("section_id")

    try:
        body = req.get_json()
    except ValueError:
        body = {}
    use_search = bool(body.get("use_search", False))

    section = db.get_grammar_section(uid, section_id)
    if not section:
        return _err("Not found", 404)

    try:
        summary = ai_client.summarize_grammar(section["grammar_input"], use_search=use_search)
    except Exception as e:
        logging.exception("summarize_grammar failed")
        return _err(str(e), 500)

    updated = db.update_grammar_summary(uid, section_id, summary)
    return _json(updated)


# ── Exercises ──────────────────────────────────────────────────────────────────

@app.route(route="grammar/{section_id}/exercises", methods=["GET", "POST"])
def exercises(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    section_id = req.route_params.get("section_id")

    if req.method == "GET":
        return _json(db.get_exercises(uid, section_id))

    ex = db.create_exercise(uid, section_id)
    return _json(ex, 201)


@app.route(route="exercises/{exercise_id}", methods=["PATCH", "DELETE"])
def exercise_by_id(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    exercise_id = req.route_params.get("exercise_id")

    if req.method == "DELETE":
        db.delete_exercise(uid, exercise_id)
        return _json({"ok": True})

    try:
        body = req.get_json()
    except ValueError:
        body = {}
    user_input = body.get("user_input", "")
    updated = db.update_exercise_input(uid, exercise_id, user_input)
    if not updated:
        return _err("Not found", 404)
    return _json(updated)


@app.route(route="exercises/{exercise_id}/evaluate", methods=["POST"])
def evaluate(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    exercise_id = req.route_params.get("exercise_id")

    try:
        body = req.get_json()
    except ValueError:
        body = {}
    use_search = bool(body.get("use_search", False))

    ex = db.get_exercise(uid, exercise_id)
    if not ex:
        return _err("Not found", 404)

    if not (ex.get("user_input") or "").strip():
        return _err("Please write your exercise first")

    section = db.get_grammar_section(uid, ex["grammar_section_id"])
    if not section:
        return _err("Grammar section not found", 404)

    try:
        feedback = ai_client.evaluate_exercise(
            section["grammar_input"], ex["user_input"], use_search=use_search
        )
    except Exception as e:
        logging.exception("evaluate_exercise failed")
        return _err(str(e), 500)

    updated = db.update_exercise_feedback(uid, exercise_id, feedback)
    return _json(updated)


# ── Q&A ────────────────────────────────────────────────────────────────────────

@app.route(route="grammar/{section_id}/qas", methods=["GET", "POST"])
def qas(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    section_id = req.route_params.get("section_id")

    if req.method == "GET":
        return _json(db.get_qas(uid, section_id))

    try:
        body = req.get_json()
    except ValueError:
        body = {}
    question = (body.get("question") or "").strip()
    if not question:
        return _err("Question is required")
    use_search = bool(body.get("use_search", False))

    section = db.get_grammar_section(uid, section_id)
    if not section:
        return _err("Grammar section not found", 404)

    qa = db.create_qa(uid, section_id, question)

    try:
        answer = ai_client.answer_qa(section["grammar_input"], question, use_search=use_search)
    except Exception as e:
        logging.exception("answer_qa failed")
        return _err(str(e), 500)

    updated = db.update_qa_answer(uid, qa["id"], answer)
    return _json(updated, 201)


@app.route(route="qas/{qa_id}", methods=["DELETE"])
def qa_by_id(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    qa_id = req.route_params.get("qa_id")
    db.delete_qa(uid, qa_id)
    return _json({"ok": True})


# ── Remember Tests ──────────────────────────────────────────────────────────────

@app.route(route="grammar/{section_id}/tests", methods=["GET", "POST"])
def remember_tests(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    section_id = req.route_params.get("section_id")

    if req.method == "GET":
        return _json(db.get_remember_tests(uid, section_id))

    try:
        body = req.get_json()
    except ValueError:
        body = {}
    user_answer = (body.get("user_answer") or "").strip()
    if not user_answer:
        return _err("Answer is required")

    section = db.get_grammar_section(uid, section_id)
    if not section:
        return _err("Grammar section not found", 404)

    test = db.create_remember_test(uid, section_id, user_answer)

    try:
        score, feedback = ai_client.assess_remember_test(section["grammar_input"], user_answer)
    except Exception as e:
        logging.exception("assess_remember_test failed")
        return _err(str(e), 500)

    updated = db.update_remember_test_result(uid, test["id"], score, feedback)
    db.update_grammar_last_test(uid, section_id, score)
    return _json(updated, 201)


@app.route(route="tests/{test_id}", methods=["DELETE"])
def test_by_id(req: func.HttpRequest) -> func.HttpResponse:
    uid = _user_id(req)
    if not uid:
        return _err("Unauthorized", 401)
    test_id = req.route_params.get("test_id")
    db.delete_remember_test(uid, test_id)
    return _json({"ok": True})
