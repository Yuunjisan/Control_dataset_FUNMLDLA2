# A Control Dataset for cross-file Dependency in code completion

> **Links** (replace before submitting):
> - Dataset: `https://github.com/Yuunjisan/Control_dataset_FUNMLDLA2/blob/main/control_dataset/control_dataset.jsonl`
> - Generator code: `https://github.com/Yuunjisan/Control_dataset_FUNMLDLA2/blob/main/control_dataset/generate_control_dataset.py`

## the property: cross-file dependency

Code auto-completion systems such as GitHub Copilot predict the next line a developer will write. That line is often easy to guess from the current file. But in real projects the symbol on that line is mostly defined in another file of the same repository. Predicting `result = compute_total(values)` only makes sense if the model knows what `compute_total` is, and that definition may live one file over.

That is the property I want to test on its own: does the next-line completion target depend on a symbol defined in another file (cross-file) rather than in the same file (in-file)?

The property matters because it is the main idea of *RepoBench* (Liu, Xu & McAuley, 2023, [arXiv:2306.03091](https://arxiv.org/abs/2306.03091)). RepoBench argues that existing benchmarks evaluate completion within a single file and so do not reflect real multi-file programming. The hardest setting, *Cross-File-First* (XF-F), is the case where the line is the first use of a cross-file symbol, so in-file context gives no hint. RepoBench's own prompt-construction ablation shows the effect is large: with only short in-file context, exact-match accuracy on cross-file-first lines is around 7% for both Python and Java, far below the in-file setting, and adding cross-file context raises overall accuracy a lot (RepoBench, Appendix A, Table 5).

But RepoBench is built from real GitHub repositories. That is a strength for measuring real-world impact, and the authors are clear that these are "real world" data with unknown confounders. The 7% number is therefore mixed in with everything else that makes real code hard: unusual naming, long files, rare libraries, language idiom, and the intrinsic difficulty of a given line. From RepoBench alone we can't say that the cross-file location of the definition is what causes the drop, rather than the difficulty of the particular code that happens to contain cross-file lines.

A control dataset is built to answer exactly that question.

## what makes this a control dataset

Following the controlled "toy problem" approach, a synthetic setting with a single confounder and known ground truth, the dataset is built from **minimal pairs**. Each pair is two small synthetic projects that are identical except for one thing:

- **`in_file`** (the control, "data-without-problem"): the called function is defined in the same file as the call.
- **`cross_file`** (the treatment, "data-with-problem"): the same function definition is moved to another file and imported. The call site is unchanged.

The line a model must predict, the target line, is **byte-for-byte identical** in both conditions of a pair. The argument-setup line before it is identical too. The only differences are (1) the presence of an `import` statement and (2) where the definition lives. Those two differences are the property under test; nothing else varies. So any accuracy gap a model shows between the two conditions of a pair comes from the cross-file dependency and from no other factor.

That is what "precisely tests" means here: the dataset holds every confounder fixed by construction, so the one variable that changes is the cross-file-ness of the dependency.

## examples

The following two pairs are taken from the generated dataset (seed 0).

### pair 0 : function `count_words`

**Control (`in_file`)** : `main.py`:

```python
def count_words(text):
    return len(text.split())

sentence = "the quick brown fox"
n = count_words(sentence)
```

**Treatment (`cross_file`)** : `ops.py`:

```python
def count_words(text):
    return len(text.split())
```

`main.py`:

```python
from ops import count_words

sentence = "the quick brown fox"
n = count_words(sentence)
```

Target line to predict in **both** conditions: `n = count_words(sentence)`

### pair 1 : function `compute_total`

**Control (`in_file`)** : `main.py`:

```python
def compute_total(items):
    return sum(items)

values = [1, 2, 3]
result = compute_total(values)
```

**Treatment (`cross_file`)** : `tools.py`:

```python
def compute_total(items):
    return sum(items)
```

`main.py`:

```python
from tools import compute_total

values = [1, 2, 3]
result = compute_total(values)
```

Target line to predict in **both** conditions: `result = compute_total(values)`

In each pair the prediction target and its surrounding call-site context stay the same. Only the location of the definition (and the import it requires) changes.

## how the dataset was generated

The dataset is produced by a single self-contained Python script, `generate_control_dataset.py`, with no external dependencies.

1. **A small library of behaviour templates.** Each template bundles a function definition (such as `compute_total`, `normalize_name`, `to_celsius`, `clamp`, `dedupe`, `count_words`), the in-file lines that prepare its argument, and the target line that calls it. The call site references only the function name and the prepared argument, so it does not depend on where the definition lives.

2. **Pair construction.** For each of `n` pairs, the generator samples a template and a module name (such as `utils`, `helpers`, `ops`). It renders the `in_file` condition (definition plus call in `main.py`) and the `cross_file` condition (definition moved to `<module>.py`, plus an `import`), keeping the target line identical.

3. **An invariant check.** Before a pair is accepted, `verify_invariant` asserts that (a) the target line is identical across the two conditions and (b) the call-site context, meaning the argument setup plus the target line, is identical, with the import statement and the relocated definition being the only allowed differences. If a pair would introduce a second source of variation, generation fails rather than silently producing a broken control. During development this check caught a real bug in an earlier draft of the generator.

4. **Output.** The dataset is written as `control_dataset.jsonl`, one JSON object per sample, recording the pair id, condition, the project files, the prompt file, the target line, and a note. A `stats.json` and a human-readable `examples.md` are written alongside.

The run used for this post:

```
python generate_control_dataset.py --n 200 --seed 0 --out ./control_dataset
```

This produces **200 minimal pairs (400 samples)**, balanced across the two conditions and drawn from 6 behaviour templates. Generation is deterministic given the seed, so the dataset is reproducible.

Each JSONL line looks like this (one sample):

```json
{"pair_id": 0, "condition": "cross_file",
 "files": {"ops.py": "def count_words(text):\n    return len(text.split())\n",
           "main.py": "from ops import count_words\n\nsentence = \"the quick brown fox\"\nn = count_words(sentence)\n"},
 "prompt_file": "main.py",
 "target_line": "n = count_words(sentence)",
 "func_name": "count_words",
 "notes": "Treatment / data-with-problem: definition moved to ops.py and imported. Target line is byte-for-byte identical to its in_file counterpart."}
```

## scope and limitations

This is a minimal control, and it is worth being clear about what it does and does not show.

- It tests whether the cross-file location of a dependency,on its own, changes completion behaviour, and nothing more. It is not a measure of real-world difficulty; that is what RepoBench's uncontrolled, real-repository setting is for. The two go together: the control isolates the mechanism, the real data shows it matters in practice.
- The synthetic projects are small and the behaviours are simple. High absolute accuracy is not the goal. A control works best when the in-file version is easy,so that any drop in the cross-file version points to the manipulated property rather than to general difficulty.
- The dataset covers Python and a single import style (`from <module> import <name>`). Extending it to other import forms, to Java, or to multi-hop cross-file dependencies would broaden coverage, but each addition introduces another dimension that would itself need to be controlled.

## summary

RepoBench shows why cross-file dependency matters but, being built from real repositories,can't separate it from confounders. This control dataset fills that gap: minimal pairs that differ in exactly one property, whether the needed definition is in-file or cross-file, with the prediction target held byte-for-byte identical, generated by a short, self checking script. That design is what lets the dataset test the property directly instead of only correlating with it.

### reference

Tianyang Liu, Canwen Xu, Julian McAuley. *RepoBench: Benchmarking Repository-Level Code Auto-Completion Systems.* arXiv:2306.03091, 2023. https://arxiv.org/abs/2306.03091
