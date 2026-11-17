# FreeModel Aggregator

A live index of **free AI models** across providers, built for make.fun's
"The best live free-model aggregator" bounty. One run of `main.py`:

1. Pulls the live model catalogs of providers that publish a public,
   no-key model list: **OpenRouter, Pollinations, LLM7, Hugging Face
   Router, GitHub Models**.
2. Keeps only the models that are free to call (on OpenRouter, both the
   prompt and completion price must be exactly zero).
3. Probes a provider that allows keyless inference (Pollinations) with
   one tiny live completion and measures the real latency.
4. Prints one ranked leaderboard (by context window) plus a JSON
   summary, and lists how many models can be called with **no API key
   at all**.

## Run it

```bash
python3 main.py            # full index + probe
python3 main.py --top 30   # longer leaderboard
python3 main.py --prompt "Reply with exactly: OK"
```

Standard library only, Python 3.13. Every source is optional: a
provider that is down or has changed shape is reported as unavailable
and the run continues with the rest. Exit code 0 when at least one
source answered.

## Why it matters

"Free model" claims rot fast: catalogs change, prices flip, endpoints
die. This aggregator trusts nothing cached. Every number it prints was
fetched live in the same run, and the keyless probe proves at least one
listed model actually answers right now.

## License

MIT. See `LICENSE`.
