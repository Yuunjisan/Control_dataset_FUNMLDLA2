#!/usr/bin/env python3
"""
generate_control_dataset.py
===========================

Generates a CONTROL dataset that isolates a single property:
    "Does the next-line completion target depend on a symbol defined
     in another file (cross-file) or in the same file (in-file)?"

The dataset consists of MINIMAL PAIRS. For each pair, the target line
(the line a completion model must predict) is BYTE-FOR-BYTE IDENTICAL
across the two conditions. The ONLY difference is whether the called
symbol is defined in the same file (condition = "in_file", the control,
"data-without-problem") or imported from another file (condition =
"cross_file", the treatment, "data-with-problem").

Because everything except the location of the definition is held fixed,
any difference a model shows between the two conditions is attributable
to the cross-file dependency alone, and to no other confounder.

Reference (motivation, NOT source of this data):
    Liu, Xu & McAuley. "RepoBench: Benchmarking Repository-Level Code
    Auto-Completion Systems." arXiv:2306.03091, 2023.

Usage:
    python generate_control_dataset.py --n 200 --seed 0 --out ./control_dataset
"""

import argparse
import json
import os
import random
import textwrap
from dataclasses import dataclass, asdict
from typing import List

# ----------------------------------------------------------------------
# Templates. Each template is a self-contained "behaviour" that can be
# defined either in-file or cross-file without changing the call site.
# The call site (the target line) only ever references `func_name` and
# the prepared argument variable, so it is invariant to definition site.
# ----------------------------------------------------------------------

@dataclass
class Template:
    func_name: str          # the symbol whose definition we relocate
    definition: str         # the function body (identical in both conditions)
    arg_setup: str          # in-file lines preceding the target that set up the argument
    target_line: str        # the line to predict (INVARIANT across conditions)


def build_templates() -> List[Template]:
    """A small library of behaviours. Names are templated so the generator
    can stamp out many distinct, non-trivial samples while preserving the
    single-confounder property."""
    return [
        Template(
            func_name="compute_total",
            definition=(
                "def compute_total(items):\n"
                "    return sum(items)"
            ),
            arg_setup="values = [1, 2, 3]",
            target_line="result = compute_total(values)",
        ),
        Template(
            func_name="normalize_name",
            definition=(
                "def normalize_name(name):\n"
                "    return name.strip().lower()"
            ),
            arg_setup='raw = \"  Alice  \"',
            target_line="clean = normalize_name(raw)",
        ),
        Template(
            func_name="to_celsius",
            definition=(
                "def to_celsius(f):\n"
                "    return (f - 32) * 5 / 9"
            ),
            arg_setup="fahrenheit = 212",
            target_line="celsius = to_celsius(fahrenheit)",
        ),
        Template(
            func_name="count_words",
            definition=(
                "def count_words(text):\n"
                "    return len(text.split())"
            ),
            arg_setup='sentence = \"the quick brown fox\"',
            target_line="n = count_words(sentence)",
        ),
        Template(
            func_name="clamp",
            definition=(
                "def clamp(x, lo, hi):\n"
                "    return max(lo, min(x, hi))"
            ),
            arg_setup="raw_score = 137",
            target_line="bounded = clamp(raw_score, 0, 100)",
        ),
        Template(
            func_name="dedupe",
            definition=(
                "def dedupe(seq):\n"
                "    return list(dict.fromkeys(seq))"
            ),
            arg_setup="items = [1, 1, 2, 3, 3, 3]",
            target_line="unique = dedupe(items)",
        ),
    ]


# Distinct module file names so that cross-file imports look natural and
# vary across samples (another incidental dimension we deliberately fix
# per-pair so it cannot leak as a confounder within a pair).
MODULE_NAMES = [
    "utils", "helpers", "core", "lib", "tools", "common", "ops", "support",
]


@dataclass
class Sample:
    pair_id: int
    condition: str          # "in_file" (control) or "cross_file" (treatment)
    files: dict             # path -> file content (the synthetic mini-project)
    prompt_file: str        # which file contains the target line
    target_line: str        # the line to predict (identical within a pair)
    func_name: str
    notes: str


def render_in_file(t: Template) -> dict:
    """Control condition: definition lives in the SAME file as the call."""
    main = (
        f"{t.definition}\n"
        f"\n"
        f"{t.arg_setup}\n"
        f"{t.target_line}\n"
    )
    return {"main.py": main}


def render_cross_file(t: Template, module: str) -> dict:
    """Treatment condition: definition is moved to ANOTHER file and imported.
    The target line is unchanged; only an import statement is added and the
    definition is relocated."""
    module_file = f"{module}.py"
    main = (
        f"from {module} import {t.func_name}\n"
        f"\n"
        f"{t.arg_setup}\n"
        f"{t.target_line}\n"
    )
    module_src = f"{t.definition}\n"
    return {module_file: module_src, "main.py": main}


def make_pair(pair_id: int, t: Template, module: str) -> List[Sample]:
    in_file = Sample(
        pair_id=pair_id,
        condition="in_file",
        files=render_in_file(t),
        prompt_file="main.py",
        target_line=t.target_line,
        func_name=t.func_name,
        notes="Control / data-without-problem: definition is in the same file.",
    )
    cross_file = Sample(
        pair_id=pair_id,
        condition="cross_file",
        files=render_cross_file(t, module),
        prompt_file="main.py",
        target_line=t.target_line,
        func_name=t.func_name,
        notes=(
            "Treatment / data-with-problem: definition moved to "
            f"{module}.py and imported. Target line is byte-for-byte identical "
            "to its in_file counterpart."
        ),
    )
    return [in_file, cross_file]


def verify_invariant(pair: List[Sample]) -> None:
    """Hard assertion guaranteeing the single-confounder property.

    Two things must hold for the control to be valid:
      (1) The target line is byte-for-byte identical across conditions.
      (2) The *call-site context* -- the argument setup and the target line,
          i.e. the lines that actually surround and inform the prediction --
          is identical across conditions. The legitimately-varying parts are
          ONLY: the presence of an import statement, and the location of the
          definition (in main.py vs a separate module). Those two changes ARE
          the property under test; everything else is held fixed.
    """
    a, b = pair
    assert a.target_line == b.target_line, (
        f"Target line differs within pair {a.pair_id}; control is broken."
    )

    def callsite_context(s: Sample) -> List[str]:
        # The lines in main.py that are NOT the relocated definition and NOT
        # the import: i.e. the argument setup and the target line.
        lines = s.files["main.py"].splitlines()
        ctx = []
        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                continue
            if stripped.startswith("from ") or stripped.startswith("import "):
                continue          # import differs by design (it's the property)
            if stripped.startswith("def ") or ln.startswith("    "):
                continue          # the definition body lives in main only for in_file
            ctx.append(ln)
        return ctx

    a_ctx = callsite_context(a)
    b_ctx = callsite_context(b)
    assert a_ctx == b_ctx, (
        f"Call-site context differs within pair {a.pair_id}; "
        f"an uncontrolled confounder was introduced.\n  in_file:   {a_ctx}\n"
        f"  cross_file: {b_ctx}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200,
                    help="number of minimal pairs to generate")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=str, default="./control_dataset")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    templates = build_templates()

    os.makedirs(args.out, exist_ok=True)
    samples: List[Sample] = []

    for pair_id in range(args.n):
        t = rng.choice(templates)
        module = rng.choice(MODULE_NAMES)
        pair = make_pair(pair_id, t, module)
        verify_invariant(pair)          # fail loudly if control is violated
        samples.extend(pair)

    # Write the dataset as JSONL (one sample per line).
    data_path = os.path.join(args.out, "control_dataset.jsonl")
    with open(data_path, "w") as f:
        for s in samples:
            f.write(json.dumps(asdict(s)) + "\n")

    # Also write a couple of human-readable example pairs for the blog.
    examples_path = os.path.join(args.out, "examples.md")
    with open(examples_path, "w") as f:
        f.write("# Example minimal pairs\n\n")
        for pid in range(min(2, args.n)):
            pair = [s for s in samples if s.pair_id == pid]
            f.write(f"## Pair {pid} (function: `{pair[0].func_name}`)\n\n")
            for s in pair:
                f.write(f"### Condition: `{s.condition}`\n\n")
                for path, content in s.files.items():
                    f.write(f"**`{path}`**\n\n```python\n{content}```\n\n")
                f.write(f"*Target line to predict:* `{s.target_line}`\n\n")

    # Dataset statistics.
    n_pairs = args.n
    n_samples = len(samples)
    stats = {
        "pairs": n_pairs,
        "samples": n_samples,
        "conditions": ["in_file", "cross_file"],
        "templates": len(templates),
        "seed": args.seed,
    }
    with open(os.path.join(args.out, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Wrote {n_samples} samples ({n_pairs} pairs) to {data_path}")
    print(f"Wrote examples to {examples_path}")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()
