"""
prompt-diff: Diff and version control prompt templates with semantic awareness.

A CLI tool for comparing prompt templates with special handling for
variables, instructions, and examples.
"""

__version__ = "0.1.0"

from .parser import parse_prompt, PromptElement, PromptType
from .differ import diff_prompts, DiffResult

__all__ = [
    "parse_prompt",
    "PromptElement",
    "PromptType",
    "diff_prompts",
    "DiffResult",
]
