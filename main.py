#!/usr/bin/env python3
"""
FreeModel Aggregator — a live index of free AI models across providers.

What it does, in one run:
  1. Pulls the live model catalogs of several providers that expose a
     public, no-key model list (OpenRouter, Pollinations, LLM7,
     Hugging Face Router, GitHub Models).
  2. Keeps only the models that are free to call (for OpenRouter: both
     prompt and completion price are exactly zero).
  3. Probes the providers that allow keyless inference (Pollinations)
     with a tiny live completion and measures real latency.
  4. Prints one ranked, unified leaderboard plus a JSON summary.

Standard library only. Every provider is optional: a source that is
down, slow, or has changed shape is reported as unavailable and the
run continues with the rest. Exit code is 0 when at least one source
answered, 1 when none did.

Usage:  python3 main.py [--prompt "Reply with exactly: OK"] [--top 15]
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

UA = {"User-Agent": "free-model-aggregator/1.0 (+https://make.fun)"}
TIMEOUT = 20


def fetch_json(url, timeout=TIMEOUT):
    """GET a JSON document; return (data, error_string)."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace")), None
    except Exception as exc:  # network, HTTP, JSON shape: all degrade
        return None, f"{type(exc).__name__}: {exc}"


def fetch_text(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace"), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------- sources

def source_openrouter():
    """OpenRouter's public catalog; free = prompt and completion price 0."""
    data, err = fetch_json("https://openrouter.ai/api/v1/models")
    if err:
        return [], err
    models = []
    for m in data.get("data", []):
        pricing = m.get("pricing") or {}
        try:
            free = float(pricing.get("prompt", "1")) == 0.0 and \
                   float(pricing.get("completion", "1")) == 0.0
        except (TypeError, ValueError):
            free = False
        if free:
            models.append({
                "provider": "OpenRouter",
                "id": m.get("id", "?"),
                "name": m.get("name", m.get("id", "?")),
                "context": m.get("context_length") or 0,
                "free": True,
                "keyless_call": False,
            })
    return models, None


def source_pollinations():
    """Pollinations publishes its text model list without a key."""
    data, err = fetch_json("https://text.pollinations.ai/models")
    if err:
        return [], err
    names = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                names.append(item.get("name") or item.get("id") or "?")
    elif isinstance(data, dict):
        names = list(data.keys())
    return [{
        "provider": "Pollinations",
        "id": n, "name": n, "context": 0,
        "free": True, "keyless_call": True,
    } for n in names if n and n != "?"], None


def source_llm7():
    """LLM7 exposes an OpenAI-shaped model list on its free tier."""
    data, err = fetch_json("https://api.llm7.io/v1/models")
    if err:
        return [], err
    return [{
        "provider": "LLM7",
        "id": m.get("id", "?"), "name": m.get("id", "?"), "context": 0,
        "free": True, "keyless_call": True,
    } for m in data.get("data", [])], None


def source_hf_router():
    """Hugging Face Router model list (public catalog endpoint)."""
    data, err = fetch_json("https://router.huggingface.co/v1/models")
    if err:
        return [], err
    out = []
    for m in data.get("data", []) if isinstance(data, dict) else []:
        out.append({
            "provider": "HF Router",
            "id": m.get("id", "?"), "name": m.get("id", "?"), "context": 0,
            "free": True, "keyless_call": False,
        })
    return out, None


def source_github_models():
    """GitHub Models public catalog."""
    data, err = fetch_json("https://models.github.ai/catalog/models")
    if err:
        return [], err
    out = []
    items = data if isinstance(data, list) else data.get("models", [])
    for m in items:
        out.append({
            "provider": "GitHub Models",
            "id": m.get("id") or m.get("name", "?"),
            "name": m.get("friendly_name") or m.get("name", "?"),
            "context": (m.get("limits") or {}).get("max_input_tokens") or 0,
            "free": True, "keyless_call": False,
        })
    return out, None


SOURCES = [source_openrouter, source_pollinations, source_llm7,
           source_hf_router, source_github_models]


# ---------------------------------------------------------------- probes

def probe_pollinations(prompt):
    """One tiny keyless completion; returns (latency_s, snippet, error)."""
    from urllib.parse import quote
    url = "https://text.pollinations.ai/" + quote(prompt)
    start = time.time()
    text, err = fetch_text(url, timeout=30)
    if err:
        return None, None, err
    return round(time.time() - start, 2), (text or "").strip()[:80], None


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Live free-model aggregator")
    ap.add_argument("--prompt", default="Reply with exactly: OK",
                    help="probe prompt for keyless live completions")
    ap.add_argument("--top", type=int, default=15,
                    help="rows to show in the ranked table")
    args = ap.parse_args()

    all_models, source_report = [], []
    for src in SOURCES:
        models, err = src()
        name = src.__name__.replace("source_", "")
        source_report.append({
            "source": name, "models": len(models),
            "status": "ok" if err is None else f"unavailable ({err})",
        })
        all_models.extend(models)

    # De-duplicate on (provider, id), rank by context length then name.
    seen, unique = set(), []
    for m in all_models:
        key = (m["provider"], m["id"])
        if key not in seen:
            seen.add(key)
            unique.append(m)
    unique.sort(key=lambda m: (-(m["context"] or 0), m["provider"], m["id"]))

    print("=" * 68)
    print("FREE-MODEL AGGREGATOR — live index of free AI models")
    print("=" * 68)
    print("\nSources (live catalog pulls, no API keys):")
    for row in source_report:
        print(f"  {row['source']:<16} {row['models']:>5} free models   {row['status']}")

    total = len(unique)
    print(f"\nTotal free models indexed: {total}")
    keyless = [m for m in unique if m["keyless_call"]]
    print(f"Callable with no key at all: {len(keyless)} "
          f"(providers: {sorted({m['provider'] for m in keyless})})")

    print(f"\nTop {min(args.top, total)} by context window:")
    print(f"  {'#':>3}  {'provider':<14} {'context':>9}  model")
    for i, m in enumerate(unique[:args.top], 1):
        ctx = f"{m['context']:,}" if m["context"] else "n/a"
        print(f"  {i:>3}  {m['provider']:<14} {ctx:>9}  {m['id']}")

    print("\nLive keyless probe (Pollinations, one tiny completion):")
    latency, snippet, err = probe_pollinations(args.prompt)
    if err:
        print(f"  probe failed: {err}")
    else:
        print(f"  latency {latency}s, reply: {snippet!r}")

    summary = {
        "total_free_models": total,
        "sources": source_report,
        "keyless_callable": len(keyless),
        "probe": {"provider": "Pollinations", "latency_s": latency,
                  "reply": snippet, "error": err},
        "top": unique[:args.top],
    }
    print("\nJSON summary:")
    print(json.dumps(summary, indent=2))
    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
