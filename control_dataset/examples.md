# example minimal pairs

## pair 0 (function: `count_words`)

### condition: `in_file`

**`main.py`**

```python
def count_words(text):
    return len(text.split())

sentence = "the quick brown fox"
n = count_words(sentence)
```

*Target line to predict:* `n = count_words(sentence)`

### condition: `cross_file`

**`ops.py`**

```python
def count_words(text):
    return len(text.split())
```

**`main.py`**

```python
from ops import count_words

sentence = "the quick brown fox"
n = count_words(sentence)
```

*Target line to predict:* `n = count_words(sentence)`

## pair 1 (function: `compute_total`)

### condition: `in_file`

**`main.py`**

```python
def compute_total(items):
    return sum(items)

values = [1, 2, 3]
result = compute_total(values)
```

*Target line to predict:* `result = compute_total(values)`

### condition: `cross_file`

**`tools.py`**

```python
def compute_total(items):
    return sum(items)
```

**`main.py`**

```python
from tools import compute_total

values = [1, 2, 3]
result = compute_total(values)
```

*Target line to predict:* `result = compute_total(values)`

