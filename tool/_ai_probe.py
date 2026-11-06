"""Does an AI search answer name Badger? A weekly, read-only probe.

ChatGPT is the biggest source of visitors to badger.fit, and nothing recorded
whether it (or anything like it) recommends the app. This asks a fixed list of
the questions people ask about programs, once a week, through every AI search
API that has a key, and records whether the answer names Badger or cites
badger.fit. The prompts never change, so the weekly rate is a trend: a change in
the list would be mistaken for a change in visibility.

Providers are optional, like every source in this folder. One with no key is
reported as skipped, not as a failure, and the rest still run. Keys come from
the environment or from ~/.config/badger-stats/ai-probe.json, which is outside
the repo; this file never holds one.

    PERPLEXITY_API_KEY   Sonar (searches the web by design)
    OPENAI_API_KEY       Responses API with the web_search tool
    GEMINI_API_KEY       generateContent with Google Search grounding
    ANTHROPIC_API_KEY    Messages API with the web_search tool

Every request is a read: a question in, an answer out. Nothing is posted.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _stats_sources as src  # noqa: E402

CONFIG_PATH = os.path.expanduser("~/.config/badger-stats/ai-probe.json")
HISTORY_PATH = Path.home() / "Development/badger-artifacts/marketing-2026-11/ai-answers.tsv"

# Fixed on purpose. Add to the end rather than editing: the trend is only
# comparable across weeks for a prompt that has stayed the same.
PROMPTS = [
    "What is the best app for the GZCLP program?",
    "Best workout tracker app for 5/3/1?",
    "What app can I use to run the nSuns program?",
    "Which app tracks StrongLifts 5x5 and also lets me change the program?",
    "Best app for Starting Strength with plate math and progression?",
    "App to follow Madcow 5x5 with automatic weight increases?",
    "Best gym log app for powerlifting that works offline?",
    "Best free workout tracker for lifting without a subscription?",
    "What is a good alternative to Strong or Hevy for tracking lifts?",
    "How do I move my workout history from FitNotes to a new app?",
    "Which workout app has a plate calculator and a 1RM calculator built in?",
    "Best app for progressive overload tracking?",
]

# Name the brand and the domain; a bare "badger" is also an animal.
_NAMED = re.compile(r"badger[\s._-]?fit|fit\.badger", re.IGNORECASE)
_CITED = re.compile(r"(^|[/.])badger\.fit(/|$|\?|#)", re.IGNORECASE)

PROVIDERS = ("perplexity", "openai", "gemini", "anthropic")
ENV_KEYS = {
    "perplexity": "PERPLEXITY_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
DEFAULT_MODELS = {
    "perplexity": "sonar",
    "openai": "gpt-4.1",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-haiku-5-5",
}


def load_keys() -> tuple[dict, dict]:
    """(keys, models) for the providers that have a key; env wins over file."""
    stored: dict = {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            stored = json.load(fh)
    except (OSError, ValueError):
        pass
    keys, models = {}, dict(DEFAULT_MODELS)
    for name, env in ENV_KEYS.items():
        key = os.environ.get(env) or stored.get(env) or stored.get(name)
        if key:
            keys[name] = key
        if stored.get(f"{name}_model"):
            models[name] = stored[f"{name}_model"]
    return keys, models


def detect(text: str, urls: list[str]) -> dict:
    """Whether the answer names Badger, and whether any source is badger.fit."""
    named = bool(_NAMED.search(text or ""))
    cited = any(_CITED.search(u or "") for u in urls)
    return {"named": named, "cited": cited}


# --- providers ---------------------------------------------------------------
# Each returns {"text": str, "urls": [str]} parsed from the provider's reply.
# The parsers are separate from the requests so tests can feed them fixtures.


def parse_perplexity(payload: dict) -> dict:
    text = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    urls = list(payload.get("citations") or [])
    urls += [r.get("url", "") for r in payload.get("search_results") or []]
    return {"text": text, "urls": urls}


def parse_openai(payload: dict) -> dict:
    text, urls = [], []
    for item in payload.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            text.append(part.get("text", ""))
            urls += [a.get("url", "") for a in part.get("annotations") or []
                     if a.get("type") == "url_citation"]
    return {"text": "\n".join(text), "urls": urls}


def parse_gemini(payload: dict) -> dict:
    cand = (payload.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts") or [])
    urls = []
    for chunk in (cand.get("groundingMetadata") or {}).get("groundingChunks") or []:
        web = chunk.get("web") or {}
        # The uri is a Google redirect; the title is the source's domain.
        urls += [web.get("uri", ""), web.get("title", "")]
    return {"text": text, "urls": urls}


def parse_anthropic(payload: dict) -> dict:
    text, urls = [], []
    for block in payload.get("content") or []:
        if block.get("type") == "text":
            text.append(block.get("text", ""))
            urls += [c.get("url", "") for c in block.get("citations") or []]
        elif block.get("type") == "web_search_tool_result":
            content = block.get("content")
            if isinstance(content, list):
                urls += [r.get("url", "") for r in content]
    return {"text": "\n".join(text), "urls": urls}


def ask(provider: str, prompt: str, key: str, model: str) -> dict:
    if provider == "perplexity":
        body = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        data = src._get_json(
            "https://api.perplexity.ai/chat/completions",
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json.dumps(body).encode(), timeout=90)
        return parse_perplexity(data)
    if provider == "openai":
        body = {"model": model, "input": prompt, "tools": [{"type": "web_search"}]}
        data = src._get_json(
            "https://api.openai.com/v1/responses",
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json.dumps(body).encode(), timeout=120)
        return parse_openai(data)
    if provider == "gemini":
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"google_search": {}}]}
        data = src._get_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {"x-goog-api-key": key, "Content-Type": "application/json"},
            json.dumps(body).encode(), timeout=120)
        return parse_gemini(data)
    if provider == "anthropic":
        body = {"model": model, "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [{"type": "web_search_20250305", "name": "web_search",
                           "max_uses": 3}]}
        data = src._get_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01",
             "Content-Type": "application/json"},
            json.dumps(body).encode(), timeout=120)
        return parse_anthropic(data)
    raise ValueError(f"unknown provider {provider}")


def run(prompts: list[str] = PROMPTS, ask_fn=ask, keys_models=None) -> dict:
    """Ask every prompt through every keyed provider.

    Returns {"rows": [...], "skipped": [providers with no key]}. A failed
    request becomes a row with an error, so a flaky provider cannot read as
    "Badger was not named".
    """
    keys, models = keys_models or load_keys()
    rows = []
    for provider, key in keys.items():
        for prompt in prompts:
            row = {"date": date.today().isoformat(), "provider": provider,
                   "model": models[provider], "prompt": prompt,
                   "named": "", "cited": "", "error": ""}
            try:
                answer = ask_fn(provider, prompt, key, models[provider])
                found = detect(answer["text"], answer["urls"])
                row["named"] = "1" if found["named"] else "0"
                row["cited"] = "1" if found["cited"] else "0"
            except Exception as exc:  # noqa: BLE001 - one prompt must not sink the run
                row["error"] = f"{type(exc).__name__}"
            rows.append(row)
    return {"rows": rows, "skipped": [p for p in PROVIDERS if p not in keys]}


FIELDS = ["date", "provider", "model", "prompt", "named", "cited", "error"]


def append_history(rows: list[dict], path: Path = HISTORY_PATH) -> None:
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, FIELDS, delimiter="\t")
        if new:
            writer.writeheader()
        writer.writerows(rows)


def latest_summary(path: Path = HISTORY_PATH) -> dict:
    """The newest run per provider, for the weekly report.

    {"date": ..., "providers": {name: {"asked", "named", "cited", "errors"}},
    "prompts": n} or {"empty": True} when no run exists yet.
    """
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
    except OSError:
        return {"empty": True}
    if not rows:
        return {"empty": True}
    latest = max(r["date"] for r in rows)
    providers: dict[str, dict] = {}
    for r in (r for r in rows if r["date"] == latest):
        slot = providers.setdefault(
            r["provider"], {"asked": 0, "named": 0, "cited": 0, "errors": 0})
        if r["error"]:
            slot["errors"] += 1
            continue
        slot["asked"] += 1
        slot["named"] += r["named"] == "1"
        slot["cited"] += r["cited"] == "1"
    return {"date": latest, "providers": providers}


def main() -> None:
    result = run()
    if result["skipped"]:
        print("No key for: " + ", ".join(
            f"{p} ({ENV_KEYS[p]})" for p in result["skipped"]))
    if not result["rows"]:
        sys.exit("No provider has a key, so nothing was asked. Set at least one "
                 f"of {', '.join(ENV_KEYS.values())} or add it to {CONFIG_PATH}.")
    append_history(result["rows"])
    for r in result["rows"]:
        mark = "ERR" if r["error"] else ("named" if r["named"] == "1" else "-")
        print(f'{r["provider"]:11s} {mark:6s} {r["prompt"]}')


if __name__ == "__main__":
    main()
