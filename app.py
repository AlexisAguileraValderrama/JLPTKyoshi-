from flask import Flask, request, jsonify, render_template
from database import init_db, get_db
from ai_client import summarize_grammar, evaluate_exercise

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


# --- Notebooks ---

@app.route("/api/notebooks", methods=["GET"])
def get_notebooks():
    db = get_db()
    notebooks = db.execute("SELECT * FROM notebooks ORDER BY created_at DESC").fetchall()
    db.close()
    return jsonify([dict(n) for n in notebooks])


@app.route("/api/notebooks", methods=["POST"])
def create_notebook():
    data = request.json
    name = (data.get("name") or "").strip()
    subtitle = (data.get("subtitle") or "").strip() or None
    if not name:
        return jsonify({"error": "Name is required"}), 400
    db = get_db()
    cur = db.execute("INSERT INTO notebooks (name, subtitle) VALUES (?, ?)", (name, subtitle))
    db.commit()
    notebook = db.execute("SELECT * FROM notebooks WHERE id = ?", (cur.lastrowid,)).fetchone()
    db.close()
    return jsonify(dict(notebook)), 201


@app.route("/api/notebooks/<int:notebook_id>", methods=["DELETE"])
def delete_notebook(notebook_id):
    db = get_db()
    db.execute("DELETE FROM notebooks WHERE id = ?", (notebook_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/notebooks/<int:notebook_id>", methods=["PATCH"])
def rename_notebook(notebook_id):
    data = request.json
    name = (data.get("name") or "").strip()
    subtitle = (data.get("subtitle") or "").strip() or None
    if not name:
        return jsonify({"error": "Name is required"}), 400
    db = get_db()
    db.execute("UPDATE notebooks SET name = ?, subtitle = ? WHERE id = ?", (name, subtitle, notebook_id))
    db.commit()
    notebook = db.execute("SELECT * FROM notebooks WHERE id = ?", (notebook_id,)).fetchone()
    db.close()
    return jsonify(dict(notebook))


# --- Grammar Sections ---

@app.route("/api/notebooks/<int:notebook_id>/grammar", methods=["GET"])
def get_grammar_sections(notebook_id):
    db = get_db()
    sections = db.execute(
        "SELECT * FROM grammar_sections WHERE notebook_id = ? ORDER BY created_at ASC",
        (notebook_id,)
    ).fetchall()
    db.close()
    return jsonify([dict(s) for s in sections])


@app.route("/api/notebooks/<int:notebook_id>/grammar", methods=["POST"])
def create_grammar_section(notebook_id):
    data = request.json
    grammar_input = (data.get("grammar_input") or "").strip()
    if not grammar_input:
        return jsonify({"error": "Grammar input is required"}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO grammar_sections (notebook_id, grammar_input) VALUES (?, ?)",
        (notebook_id, grammar_input)
    )
    db.commit()
    section = db.execute("SELECT * FROM grammar_sections WHERE id = ?", (cur.lastrowid,)).fetchone()
    db.close()
    return jsonify(dict(section)), 201


@app.route("/api/grammar/<int:section_id>", methods=["DELETE"])
def delete_grammar_section(section_id):
    db = get_db()
    db.execute("DELETE FROM grammar_sections WHERE id = ?", (section_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/grammar/<int:section_id>/summarize", methods=["POST"])
def summarize_section(section_id):
    data = request.json or {}
    use_search = bool(data.get("use_search", False))
    db = get_db()
    section = db.execute("SELECT * FROM grammar_sections WHERE id = ?", (section_id,)).fetchone()
    if not section:
        db.close()
        return jsonify({"error": "Not found"}), 404
    try:
        summary = summarize_grammar(section["grammar_input"], use_search=use_search)
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500
    db.execute("UPDATE grammar_sections SET ai_summary = ? WHERE id = ?", (summary, section_id))
    db.commit()
    updated = db.execute("SELECT * FROM grammar_sections WHERE id = ?", (section_id,)).fetchone()
    db.close()
    return jsonify(dict(updated))


# --- Exercises ---

@app.route("/api/grammar/<int:section_id>/exercises", methods=["GET"])
def get_exercises(section_id):
    db = get_db()
    exercises = db.execute(
        "SELECT * FROM exercises WHERE grammar_section_id = ? ORDER BY created_at ASC",
        (section_id,)
    ).fetchall()
    db.close()
    return jsonify([dict(e) for e in exercises])


@app.route("/api/grammar/<int:section_id>/exercises", methods=["POST"])
def create_exercise(section_id):
    db = get_db()
    cur = db.execute(
        "INSERT INTO exercises (grammar_section_id, user_input) VALUES (?, ?)",
        (section_id, "")
    )
    db.commit()
    ex = db.execute("SELECT * FROM exercises WHERE id = ?", (cur.lastrowid,)).fetchone()
    db.close()
    return jsonify(dict(ex)), 201


@app.route("/api/exercises/<int:exercise_id>", methods=["PATCH"])
def update_exercise(exercise_id):
    data = request.json
    user_input = data.get("user_input", "")
    db = get_db()
    db.execute("UPDATE exercises SET user_input = ? WHERE id = ?", (user_input, exercise_id))
    db.commit()
    ex = db.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    db.close()
    return jsonify(dict(ex))


@app.route("/api/exercises/<int:exercise_id>/evaluate", methods=["POST"])
def evaluate_ex(exercise_id):
    data = request.json or {}
    use_search = bool(data.get("use_search", False))
    db = get_db()
    ex = db.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    if not ex:
        db.close()
        return jsonify({"error": "Not found"}), 404
    section = db.execute(
        "SELECT * FROM grammar_sections WHERE id = ?", (ex["grammar_section_id"],)
    ).fetchone()
    if not ex["user_input"] or not ex["user_input"].strip():
        db.close()
        return jsonify({"error": "Please write your exercise first"}), 400
    try:
        feedback = evaluate_exercise(section["grammar_input"], ex["user_input"], use_search=use_search)
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500
    db.execute("UPDATE exercises SET ai_feedback = ? WHERE id = ?", (feedback, exercise_id))
    db.commit()
    updated = db.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    db.close()
    return jsonify(dict(updated))


@app.route("/api/exercises/<int:exercise_id>", methods=["DELETE"])
def delete_exercise(exercise_id):
    db = get_db()
    db.execute("DELETE FROM exercises WHERE id = ?", (exercise_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
