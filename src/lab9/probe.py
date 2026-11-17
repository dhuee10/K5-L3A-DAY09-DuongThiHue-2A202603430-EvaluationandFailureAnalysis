"""Taxonomy evidence: run ONE bug switch of lab9.variant_agent on one claim@seed and print the trace.

    python -m lab9.probe --bug stale_clause --claim C-006 --seed 11
    python -m lab9.probe --list

Each probe is `fixed` + exactly one bug, registered as shape `probe_<bug>` at run time, so every
row of docs/failure_taxonomy.md can be re-run. Does not touch lab8/ or lab9/variants.py.
"""

from __future__ import annotations

import argparse

from lab9 import trace_case
from lab9.variant_agent import BENIGN, BUGS, make_shape

PROBES = sorted(BUGS - BENIGN)


def register() -> list[str]:
    from lab8.shapes import SHAPES
    for bug in PROBES:
        SHAPES.setdefault(f"probe_{bug}", make_shape(f"probe_{bug}", {"no_override", bug}))
    return [f"probe_{b}" for b in PROBES]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lab9.probe")
    ap.add_argument("--bug", choices=PROBES)
    ap.add_argument("--claim", default="C-001")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    if args.list or not args.bug:
        print("\n".join(PROBES))
        return 0
    register()
    return trace_case.main(["--shape", f"probe_{args.bug}", "--claim", args.claim, "--seed", str(args.seed)])


if __name__ == "__main__":
    raise SystemExit(main())
