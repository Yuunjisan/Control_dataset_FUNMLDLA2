# Cross-File Dependency Control Dataset

A control dataset of **minimal pairs** that isolates a single property of code
auto-completion: whether the next-line target depends on a symbol defined
**in the same file** (control) or **in another file** (treatment, cross-file).

Within each pair the target line is byte-for-byte identical; only the location
of the definition (and the import it requires) changes. This holds every other
confounder fixed, so any model behaviour difference is attributable to the
cross-file dependency alone.

Motivated by RepoBench (Liu, Xu & McAuley, 2023, arXiv:2306.03091), which shows
cross-file dependencies hurt completion but, being built from real repositories,
cannot isolate the property from confounders.

## Files
- `generate_control_dataset.py` — the generator (no dependencies, stdlib only)
- `control_dataset.jsonl` — the dataset, one JSON sample per line
- `examples.md` — two human-readable example pairs
- `stats.json` — dataset statistics

## Reproduce
```
python generate_control_dataset.py --n 200 --seed 0 --out ./control_dataset
```
Deterministic given the seed.

## Schema (per JSONL line)
| field        | meaning                                              |
|--------------|------------------------------------------------------|
| `pair_id`    | id linking the two conditions of a minimal pair      |
| `condition`  | `in_file` (control) or `cross_file` (treatment)      |
| `files`      | map of filename -> file content (the mini-project)   |
| `prompt_file`| file containing the target line (`main.py`)          |
| `target_line`| the line to predict (identical within a pair)        |
| `func_name`  | the relocated symbol                                 |
| `notes`      | human-readable description                           |
