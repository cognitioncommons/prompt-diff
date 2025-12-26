# prompt-diff

Diff and version control prompt templates with semantic awareness.

A CLI tool for comparing prompt templates that understands the semantic structure of prompts - identifying changes in variables, instructions, examples, and more.

## Installation

```bash
pip install prompt-diff
```

Or install from source:

```bash
git clone https://github.com/cognitioncommons/prompt-diff.git
cd prompt-diff
pip install -e .
```

## Usage

### Compare prompts

```bash
# Semantic diff (default) - shows changes by element type
prompt-diff compare v1/system.txt v2/system.txt

# Unified diff format (like git diff)
prompt-diff compare --format unified old.txt new.txt

# Side-by-side comparison
prompt-diff compare --format side-by-side old.txt new.txt

# JSON output for programmatic use
prompt-diff compare --format json old.txt new.txt
```

### Parse prompt structure

```bash
# Show semantic structure of a prompt
prompt-diff parse prompt.txt

# JSON output
prompt-diff parse --json-output prompt.txt
```

### List variables

```bash
# Extract all variables from a prompt
prompt-diff variables prompt.txt
```

## Features

### Semantic Element Detection

prompt-diff identifies different types of content in your prompts:

- **Variables**: `{{var}}`, `{var}`, `${var}`, `[PLACEHOLDER]`
- **Instructions**: Lines starting with "You must", "Do not", etc.
- **Examples**: Code blocks, example sections
- **Role markers**: `system:`, `user:`, `assistant:`
- **Comments**: Lines starting with `#` or `//`

### Variable Change Tracking

See which variables were added or removed between versions:

```
Variable Changes:
  + {{new_variable}}
  - {{old_variable}}
```

### Similarity Scoring

Each diff includes a similarity percentage to quickly gauge how much changed.

## Example Output

### Semantic Diff

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ Prompt Diff                                                                  │
│                                                                              │
│ Comparing:                                                                   │
│   - v1/system.txt                                                            │
│   + v2/system.txt                                                            │
│                                                                              │
│ Similarity: 75.3%                                                            │
╰─────────────────────────────────────────────────────────────────────────────╯

Variable Changes:
  + {{context}}
  - {{history}}

Changes:

~ instruction (lines 1 → 1) [82% similar]
  Old:
    You are a helpful assistant.
  New:
    You are a helpful AI assistant with expertise in coding.

+ example (line 15)
  Here is an example:
  ```python
  def hello():
      print("Hello!")
  ```

Summary: +2 -1 ~3
```

### Parse Output

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        Prompt Structure: system.txt                         │
├───────┬─────────────┬────────────────────────────────────────┬─────────────┤
│ Lines │ Type        │ Preview                                │ Variables   │
├───────┼─────────────┼────────────────────────────────────────┼─────────────┤
│ 1     │ role        │ system                                 │ -           │
│ 2-4   │ instruction │ You are a helpful assistant. You mu... │ -           │
│ 6-8   │ text        │ When responding, consider the {{con... │ context     │
│ 10-15 │ example     │ ```python...                           │ -           │
└───────┴─────────────┴────────────────────────────────────────┴─────────────┘
```

## Supported Template Syntaxes

| Syntax | Example | Detection |
|--------|---------|-----------|
| Jinja2 | `{{ variable }}` | Full support |
| Jinja2 blocks | `{% if condition %}` | Full support |
| Mustache | `{{variable}}` | Full support |
| Python f-string | `{variable}` | Full support |
| Shell | `${variable}` or `$variable` | Full support |
| XML-style | `<VARIABLE/>` | Full support |
| Placeholder | `[VARIABLE]` or `[[VARIABLE]]` | Full support |

## Python API

```python
from prompt_diff import parse_prompt, diff_prompts

# Parse a prompt
elements = parse_prompt(prompt_text)
for elem in elements:
    print(f"{elem.type}: {elem.content[:50]}...")

# Compare prompts
result = diff_prompts(old_text, new_text)
print(f"Similarity: {result.similarity:.1%}")
print(f"Added variables: {result.added_variables}")
print(f"Removed variables: {result.removed_variables}")
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please open an issue or submit a PR.

---

A [Cognition Commons](https://cognitioncommons.org) project.
