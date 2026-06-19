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
