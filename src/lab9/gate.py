"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    rows = pr.get("rows") or []
    man = pr.get("manifest") or {}
    bman = base.get("manifest") or {}

    # 1. Aggregates must be finite numbers (NaN < min is False, so a naive gate passes NaN).
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v} (NaN/inf): a crashed grader is not a score")

    # 2. Graders must have run on every row.
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s), first: {pr['evaluator_failures'][0]}")
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]
    for m in graded:
        bad = [f"{r.get('item_id')}@{r.get('seed')}" for r in rows if not isinstance(r.get(m), bool)]
        if bad:
            problems.append(f"{len(bad)} row(s) with no boolean value for graded metric {m} (first {bad[0]})")

    # 3. Row count and (item, seed) coverage: no dropped, duplicated or cherry-picked rows.
    try:
        want = int(man.get("items")) * len(man.get("seeds") or [])
    except (TypeError, ValueError):
        want = -1
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest promises {man.get('items')} items x {len(man.get('seeds') or [])} seeds = {want}")
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    dupes = len(keys) - len(set(keys))
    if dupes:
        problems.append(f"{dupes} duplicated (item_id, seed) row(s)")
    seeds = set(man.get("seeds") or [])
    off = sorted({s for _, s in keys if s not in seeds}, key=str)
    if off:
        problems.append(f"rows use seeds {off} not listed in the manifest")
    if list(man.get("seeds") or []) != list(bman.get("seeds") or []) or man.get("items") != bman.get("items"):
        problems.append(f"manifest {man.get('items')} items / seeds {man.get('seeds')} differs from the "
                        f"baseline's {bman.get('items')} items / seeds {bman.get('seeds')}")
    bkeys = {(r.get("item_id"), r.get("seed")) for r in base.get("rows") or []}
    if set(keys) != bkeys:
        miss, extra = len(bkeys - set(keys)), len(set(keys) - bkeys)
        problems.append(f"(item, seed) set differs from the baseline's: {miss} missing, {extra} extra")

    # 4. Slice tags are fixed by the eval set, not by the PR.
    btags = {r.get("item_id"): sorted(r.get("slices") or []) for r in base.get("rows") or []}
    retag = sorted({r.get("item_id") for r in rows
                    if r.get("item_id") in btags and sorted(r.get("slices") or []) != btags[r.get("item_id")]}, key=str)
    if retag:
        problems.append(f"slice tags differ from the baseline's for {retag[:5]}{' ...' if len(retag) > 5 else ''}")
    tags_by_item: dict = {}
    for r in rows:
        tags_by_item.setdefault(r.get("item_id"), set()).add(tuple(sorted(r.get("slices") or [])))
    split = sorted((i for i, t in tags_by_item.items() if len(t) > 1), key=str)
    if split:
        problems.append(f"items with different slice tags across seeds: {split[:5]}")

    # 5. The reported aggregates must be the ones the rows give (no hand-edited metrics).
    if rows and not problems:
        problems += _recheck_metrics(pr, spec)

    # 6. Ratchet: on the same eval set, thresholds may only get stricter.
    if base_spec is not None:
        problems += ratchet_problems(spec, base_spec)
    return problems


def _recheck_metrics(pr: dict, spec: dict) -> list[str]:
    rows = pr["rows"]
    ids = [m for m in GRADERS if all(m in r for r in rows)]
    has_cost = all("cost" in r for r in rows)
    norm = [r if has_cost else {**r, "cost": 0.0} for r in rows]
    got = aggregate(norm, ids, k_values=spec.get("pass_k", []))
    out = []
    for k, v in (pr.get("metrics") or {}).items():
        if k not in got or (k == "cost_per_success" and not has_cost):
            continue
        g = got[k]
        if (g is None) != (v is None) or (g is not None and not (isinstance(v, (int, float)) and abs(g - v) <= 1e-3)):
            out.append(f"metric {k} = {v} but the rows give {g}: report metrics must come from its rows")
    return out


def _looser(th: dict, base_th: dict, where: str) -> list[str]:
    out = []
    for key, bv in base_th.items():
        nv = th.get(key)
        if key == "no_significant_drop":
            if bv and not nv:
                out.append(f"{where}: no_significant_drop dropped")
        elif key in ("min",):
            if nv is None or nv < bv:
                out.append(f"{where}: {key} {bv} -> {nv} (looser)")
        elif key in ("max", "max_increase"):
            if nv is None or nv > bv:
                out.append(f"{where}: {key} {bv} -> {nv} (looser)")
        elif nv != bv:
            out.append(f"{where}: {key} {bv} -> {nv}")
    return out


def ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    """Same eval set as main => every threshold the same or stricter; nothing removed."""
    same_set = (spec.get("eval_set_version") == base_spec.get("eval_set_version")
                or spec.get("eval_set") == base_spec.get("eval_set"))
    if not same_set:
        return []
    out = []
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        out.append(f"RATCHET eval_set_version {base_spec.get('eval_set_version')} -> {spec.get('eval_set_version')} "
                   f"on the same eval set {spec.get('eval_set')}")
    new = {m["id"]: m for m in spec.get("metrics", [])}
    for bm in base_spec.get("metrics", []):
        m = new.get(bm["id"])
        if m is None:
            out.append(f"RATCHET metric {bm['id']} removed")
            continue
        if bm.get("blocking") and not m.get("blocking"):
            out.append(f"RATCHET metric {bm['id']} no longer blocking")
        out += [f"RATCHET {p}" for p in _looser(m.get("threshold") or {}, bm.get("threshold") or {}, f"metric {bm['id']}")]
    new_sl = {(s.get("name"), s.get("metric")): s for s in spec.get("slices") or []}
    for bs in base_spec.get("slices") or []:
        sid = f"slice {bs.get('name')}/{bs.get('metric')}"
        s = new_sl.get((bs.get("name"), bs.get("metric")))
        if s is None:
            out.append(f"RATCHET {sid} removed")
            continue
        if bs.get("blocking") and not s.get("blocking"):
            out.append(f"RATCHET {sid} no longer blocking")
        bth = {k: bs[k] for k in ("min", "max", "no_significant_drop") if k in bs}
        out += [f"RATCHET {p}" for p in _looser(s, bth, sid)]
    bb, nb = base_spec.get("bootstrap") or {}, spec.get("bootstrap") or {}
    if nb.get("confidence", 0.95) > bb.get("confidence", 0.95):
        out.append(f"RATCHET bootstrap confidence {bb.get('confidence')} -> {nb.get('confidence')} (wider CI)")
    for k in ("rng", "method"):
        if nb.get(k) != bb.get(k):
            out.append(f"RATCHET bootstrap {k} {bb.get(k)} -> {nb.get(k)}")
    if nb.get("n_resamples", 1000) < bb.get("n_resamples", 1000):
        out.append(f"RATCHET bootstrap n_resamples {bb.get('n_resamples')} -> {nb.get('n_resamples')}")
    if list(spec.get("seeds") or []) != list(base_spec.get("seeds") or []):
        out.append(f"RATCHET seeds {base_spec.get('seeds')} -> {spec.get('seeds')}")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, metric = s["name"], s["metric"]
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", f"n={len(a)}"
        if val is None:
            verdict = "missing"
        elif "min" in s and val < s["min"]:
            verdict = "fail"
        if s.get("no_significant_drop") and a:
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note += f" Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
            else:
                verdict = "missing"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        th = {k: s[k] for k in ("min", "no_significant_drop") if k in s}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        lines.append(f"  {sid:<34} {val!s:<8} {json.dumps(th):<40} {note:<36} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
