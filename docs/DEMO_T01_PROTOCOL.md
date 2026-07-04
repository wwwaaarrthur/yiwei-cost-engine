# DEMO-T-01 Timed Public Demo Protocol

> Evidence status: protocol ready; machine timing must come from `scripts/demo_t01_timer.py` or a dated manual recording. The pre-existing `30min -> 30s` latency line remains an experience estimate until a timed run succeeds (source: `docs/NORTH_STAR_PROOF_MAP.md:42`).

## Timing Rule

- **Start**: the moment the public URL starts opening in a zero-login browser context.
- **End**: the quote result, cost breakdown, and similar historical orders have all rendered.
- **Target URL**: `https://yiwei-cost-engine.streamlit.app`.
- **Evidence unit**: run the same flow 3 times and report the median only if all required checkpoints render.
- **No estimate rule**: if Streamlit UI automation does not expose controls reliably, record `blocked-ui` and use a manual recording instead. Do not invent or extrapolate a timing claim.

## Machine Runner

Run from repo root:

```bash
python3 scripts/demo_t01_timer.py --runs 3 --output memory/evidence/demo-t01-timing-YYYYMMDD.json
```

The runner must report:

- `status`
- `runs_requested`
- one result object per run
- per-step timestamps
- `median_total_seconds` only when the quote result, cost breakdown, and similar-order checkpoints all pass.

## Recording Checklist

- Browser profile: zero-login / incognito / no Streamlit account session.
- Resolution: large enough to keep the URL bar, stopwatch, quote result, cost breakdown, and similar-order evidence visible.
- Stopwatch: visible from URL open through final render.
- URL bar: visible at start to prove public URL.
- Audio: include a short spoken marker with date and run number.
- Evidence storage: put final files under `memory/evidence/` outside this public repo if the recording contains local browser state.
- Hash: record `sha256sum <file>` or `shasum -a 256 <file>` beside the evidence.

## Five Spoken Points

1. "This is the public anonymized Yiwei Cost Engine demo."
2. "Manual baseline remains an experience estimate until separately timed."
3. "AI does not set the price; the rule engine computes and humans review."
4. "The quote output includes cost decomposition and similar historical orders."
5. "This is not UAT or adoption evidence; it is timed demo evidence only."

## Claim Template

Use only after successful timed evidence:

> Public demo quote flow rendered in `<median_total_seconds>s` median over 3 zero-login runs on `<date>`; manual 30-minute baseline remains an experience estimate, not a measured comparator.

If automation is blocked:

> Timed demo evidence is pending because public Streamlit UI automation did not expose required controls in headless mode; manual zero-login recording is the next evidence step.
