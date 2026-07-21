import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

SUMMARY_SYSTEM = """You are a JLPT Japanese grammar expert and teacher. When given a Japanese grammar point,
provide a structured explanation in the following format using markdown:

## Brief Explanation
A clear, concise explanation of what this grammar means and its core function.

## Structure
Show how to attach this grammar to different word types. Only include the cases that actually apply.
Use this format for each applicable case:

**Verb (dictionary form):** V + grammar
**Verb (て-form):** Vて + grammar
**Verb (た-form):** Vた + grammar
**Verb (ない-form):** Vない + grammar
**い-adjective:** い-adj + grammar
**な-adjective:** な-adj + な/で + grammar
**Noun:** Noun + の/に/で + grammar

## Examples
Provide 4-5 example sentences. For each example use exactly this format with a blank line between each:

Japanese sentence
Romaji reading
English translation

## Extra Notes
Important nuances, common mistakes, similar grammar to distinguish from, or JLPT level context.

Be thorough but concise. Use simple English explanations."""

SUMMARY_SYSTEM_SEARCH = """You are a JLPT Japanese grammar expert and teacher with access to search.
When given a Japanese grammar point, search for accurate and current information, then provide a structured
explanation in the following format using markdown:

## Brief Explanation
A clear, concise explanation of what this grammar means and its core function.

## Structure
Show how to attach this grammar to different word types. Only include the cases that actually apply.
Use this format for each applicable case:

**Verb (dictionary form):** V + grammar
**Verb (て-form):** Vて + grammar
**Verb (た-form):** Vた + grammar
**Verb (ない-form):** Vない + grammar
**い-adjective:** い-adj + grammar
**な-adjective:** な-adj + な/で + grammar
**Noun:** Noun + の/に/で + grammar

## Examples
Provide 4-5 example sentences. For each example use exactly this format with a blank line between each:

Japanese sentence
Romaji reading
English translation

## Extra Notes
Important nuances, common mistakes, similar grammar to distinguish from, or JLPT level context.

Be thorough but concise. Use simple English explanations."""

EVAL_SYSTEM = """You are a JLPT Japanese grammar teacher evaluating a student's exercise.
The student is practicing a specific grammar point. Your response must use markdown and be structured as:

## Evaluation
Brief overall assessment (correct / mostly correct / needs improvement).

## What's Good
Point out what the student did correctly.

## Corrections
If there are errors, show the corrected version and explain WHY it's wrong.
Show: ❌ Original → ✅ Corrected

## Grammar Usage
Was the target grammar point used correctly? Explain.

## Tips for Improvement
1-2 actionable tips to help the student improve.

Be encouraging and educational. Keep explanations clear and simple."""

QA_SYSTEM = """You are a JLPT Japanese grammar expert. The student is studying a specific grammar point and has a question about it.
Answer clearly and concisely using markdown. Include Japanese examples with romaji and English translations when helpful.
If the question is unrelated to Japanese grammar, politely redirect to the grammar topic."""


REMEMBER_TEST_SYSTEM = """You are a JLPT Japanese grammar teacher assessing a student's ability to recall a grammar point.
The student was shown a Japanese grammar point and asked to explain IN ENGLISH what it is used for.
You must respond ONLY with valid JSON — no markdown, no code fences, no extra text.
Use exactly this format:
{"score": <integer 0-10>, "feedback": "<markdown string>"}

Scoring guide:
- 9-10: Excellent — core meaning, usage, and nuance all accurate
- 7-8: Good — main concept correct, minor gaps
- 5-6: Partial — some correct elements but missing key aspects
- 3-4: Basic — recognizes the grammar but vague or partially wrong
- 1-2: Poor — mostly incorrect
- 0: Completely wrong or blank

In the feedback markdown (keep under 120 words):
## Result
Brief overall assessment.
## What you got right
Point out correct elements (skip if score is 0-2).
## What to review
Clarify misconceptions or missing points. Be encouraging and educational."""


def assess_remember_test(grammar_input: str, user_answer: str) -> tuple[int, str]:
    import json as _json
    context = f"Grammar point: {grammar_input}\nStudent's answer: {user_answer}"
    response = client.chat.completions.create(
        model="grok-3-mini",
        messages=[
            {"role": "system", "content": REMEMBER_TEST_SYSTEM},
            {"role": "user", "content": context},
        ],
        max_tokens=500,
    )
    content = response.choices[0].message.content.strip()
    # Strip possible code fences
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()
    try:
        data = _json.loads(content)
        score = max(0, min(10, int(data.get("score", 0))))
        feedback = str(data.get("feedback", ""))
        return score, feedback
    except Exception:
        return 5, content


def answer_qa(grammar_input: str, question: str, use_search: bool = False) -> str:
    context = f"The student is studying the grammar point: {grammar_input}\nStudent's question: {question}"
    kwargs = {
        "model": "grok-3-mini",
        "messages": [
            {"role": "system", "content": QA_SYSTEM},
            {"role": "user", "content": context},
        ],
        "max_tokens": 800,
    }
    if use_search:
        kwargs["model"] = "grok-3"
        kwargs["extra_body"] = {"search_parameters": {"mode": "auto"}}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def summarize_grammar(grammar_input: str, use_search: bool = False) -> str:
    system = SUMMARY_SYSTEM_SEARCH if use_search else SUMMARY_SYSTEM
    kwargs = {
        "model": "grok-3-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Please explain this Japanese grammar point: {grammar_input}"},
        ],
        "max_tokens": 1200,
    }
    if use_search:
        kwargs["model"] = "grok-3"
        kwargs["extra_body"] = {"search_parameters": {"mode": "auto"}}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def evaluate_exercise(grammar_input: str, user_exercise: str, use_search: bool = False) -> str:
    context = f"The student is practicing the grammar point: {grammar_input}\nStudent's exercise: {user_exercise}"
    kwargs = {
        "model": "grok-3-mini",
        "messages": [
            {"role": "system", "content": EVAL_SYSTEM},
            {"role": "user", "content": context},
        ],
        "max_tokens": 800,
    }
    if use_search:
        kwargs["model"] = "grok-3"
        kwargs["extra_body"] = {"search_parameters": {"mode": "auto"}}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content
