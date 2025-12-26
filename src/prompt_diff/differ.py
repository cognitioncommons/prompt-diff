"""
Prompt template differ with semantic awareness.

Compares prompt templates and highlights semantic differences
between variables, instructions, examples, etc.
"""

import difflib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .parser import PromptElement, PromptType, parse_prompt, get_all_variables


class ChangeType(Enum):
    """Type of change between prompts."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class ElementDiff:
    """Difference between two prompt elements."""
    change_type: ChangeType
    element_type: PromptType
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    old_line: Optional[int] = None
    new_line: Optional[int] = None
    details: dict = field(default_factory=dict)


@dataclass
class DiffResult:
    """Result of comparing two prompts."""
    old_path: str
    new_path: str
    element_diffs: list[ElementDiff]
    old_variables: set[str]
    new_variables: set[str]
    added_variables: set[str]
    removed_variables: set[str]
    similarity: float  # 0.0 to 1.0

    @property
    def has_changes(self) -> bool:
        return any(d.change_type != ChangeType.UNCHANGED for d in self.element_diffs)

    @property
    def summary(self) -> dict:
        """Get a summary of changes."""
        added = sum(1 for d in self.element_diffs if d.change_type == ChangeType.ADDED)
        removed = sum(1 for d in self.element_diffs if d.change_type == ChangeType.REMOVED)
        modified = sum(1 for d in self.element_diffs if d.change_type == ChangeType.MODIFIED)
        return {
            'added': added,
            'removed': removed,
            'modified': modified,
            'total_changes': added + removed + modified,
            'added_variables': list(self.added_variables),
            'removed_variables': list(self.removed_variables),
            'similarity': self.similarity,
        }


def diff_lines(old_lines: list[str], new_lines: list[str]) -> list[tuple[str, str]]:
    """
    Diff two lists of lines and return tagged results.

    Returns list of (tag, line) where tag is one of:
    - ' ' (unchanged)
    - '+' (added)
    - '-' (removed)
    - '?' (hints about modifications)
    """
    differ = difflib.Differ()
    result = list(differ.compare(old_lines, new_lines))
    return [(line[0], line[2:]) for line in result if line]


def compute_similarity(old_text: str, new_text: str) -> float:
    """Compute similarity ratio between two texts."""
    if not old_text and not new_text:
        return 1.0
    if not old_text or not new_text:
        return 0.0
    return difflib.SequenceMatcher(None, old_text, new_text).ratio()


def align_elements(
    old_elements: list[PromptElement],
    new_elements: list[PromptElement],
) -> list[tuple[Optional[PromptElement], Optional[PromptElement]]]:
    """
    Align elements from two prompts for comparison.

    Uses content similarity to match elements that may have been modified.
    """
    aligned = []

    # Filter out whitespace for matching purposes
    old_filtered = [(i, e) for i, e in enumerate(old_elements) if e.type != PromptType.WHITESPACE]
    new_filtered = [(i, e) for i, e in enumerate(new_elements) if e.type != PromptType.WHITESPACE]

    old_used = set()
    new_used = set()

    # First pass: exact matches
    for new_idx, new_elem in new_filtered:
        for old_idx, old_elem in old_filtered:
            if old_idx in old_used:
                continue
            if old_elem.type == new_elem.type and old_elem.content == new_elem.content:
                aligned.append((old_elem, new_elem))
                old_used.add(old_idx)
                new_used.add(new_idx)
                break

    # Second pass: similar matches (modified elements)
    for new_idx, new_elem in new_filtered:
        if new_idx in new_used:
            continue
        best_match = None
        best_score = 0.5  # Minimum similarity threshold

        for old_idx, old_elem in old_filtered:
            if old_idx in old_used:
                continue
            if old_elem.type == new_elem.type:
                score = compute_similarity(old_elem.content, new_elem.content)
                if score > best_score:
                    best_score = score
                    best_match = (old_idx, old_elem)

        if best_match:
            old_idx, old_elem = best_match
            aligned.append((old_elem, new_elem))
            old_used.add(old_idx)
            new_used.add(new_idx)

    # Remaining old elements (removed)
    for old_idx, old_elem in old_filtered:
        if old_idx not in old_used:
            aligned.append((old_elem, None))

    # Remaining new elements (added)
    for new_idx, new_elem in new_filtered:
        if new_idx not in new_used:
            aligned.append((None, new_elem))

    return aligned


def diff_prompts(
    old_text: str,
    new_text: str,
    old_path: str = "old",
    new_path: str = "new",
) -> DiffResult:
    """
    Compare two prompt templates and return detailed diff.

    Args:
        old_text: Original prompt text
        new_text: New prompt text
        old_path: Label for old version
        new_path: Label for new version

    Returns:
        DiffResult with detailed element-by-element comparison
    """
    old_elements = parse_prompt(old_text)
    new_elements = parse_prompt(new_text)

    old_variables = get_all_variables(old_elements)
    new_variables = get_all_variables(new_elements)

    aligned = align_elements(old_elements, new_elements)
    element_diffs = []

    for old_elem, new_elem in aligned:
        if old_elem is None:
            # Added
            element_diffs.append(ElementDiff(
                change_type=ChangeType.ADDED,
                element_type=new_elem.type,
                new_content=new_elem.content,
                new_line=new_elem.line_start,
            ))
        elif new_elem is None:
            # Removed
            element_diffs.append(ElementDiff(
                change_type=ChangeType.REMOVED,
                element_type=old_elem.type,
                old_content=old_elem.content,
                old_line=old_elem.line_start,
            ))
        elif old_elem.content == new_elem.content:
            # Unchanged
            element_diffs.append(ElementDiff(
                change_type=ChangeType.UNCHANGED,
                element_type=old_elem.type,
                old_content=old_elem.content,
                new_content=new_elem.content,
                old_line=old_elem.line_start,
                new_line=new_elem.line_start,
            ))
        else:
            # Modified
            element_diffs.append(ElementDiff(
                change_type=ChangeType.MODIFIED,
                element_type=old_elem.type,
                old_content=old_elem.content,
                new_content=new_elem.content,
                old_line=old_elem.line_start,
                new_line=new_elem.line_start,
                details={
                    'similarity': compute_similarity(old_elem.content, new_elem.content),
                },
            ))

    return DiffResult(
        old_path=old_path,
        new_path=new_path,
        element_diffs=element_diffs,
        old_variables=old_variables,
        new_variables=new_variables,
        added_variables=new_variables - old_variables,
        removed_variables=old_variables - new_variables,
        similarity=compute_similarity(old_text, new_text),
    )


def format_unified_diff(
    old_text: str,
    new_text: str,
    old_path: str = "old",
    new_path: str = "new",
    context_lines: int = 3,
) -> str:
    """Generate a unified diff string."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=old_path,
        tofile=new_path,
        lineterm='',
        n=context_lines,
    )
    return ''.join(diff)


def format_side_by_side_diff(
    old_text: str,
    new_text: str,
    width: int = 80,
) -> list[tuple[str, str, str]]:
    """
    Generate side-by-side diff.

    Returns list of (marker, old_line, new_line) tuples.
    Marker is one of: ' ' (same), '<' (removed), '>' (added), '|' (modified)
    """
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    result = []

    half_width = (width - 3) // 2

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for i in range(i1, i2):
                result.append((' ', old_lines[i][:half_width], new_lines[j1 + (i - i1)][:half_width]))
        elif tag == 'replace':
            max_len = max(i2 - i1, j2 - j1)
            for k in range(max_len):
                old_line = old_lines[i1 + k][:half_width] if i1 + k < i2 else ''
                new_line = new_lines[j1 + k][:half_width] if j1 + k < j2 else ''
                result.append(('|', old_line, new_line))
        elif tag == 'delete':
            for i in range(i1, i2):
                result.append(('<', old_lines[i][:half_width], ''))
        elif tag == 'insert':
            for j in range(j1, j2):
                result.append(('>', '', new_lines[j][:half_width]))

    return result
