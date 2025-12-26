"""
Prompt template parser with semantic element detection.

Identifies variables, instructions, examples, and other semantic elements
in prompt templates.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterator


class PromptType(Enum):
    """Types of prompt elements."""
    TEXT = "text"
    VARIABLE = "variable"          # {{var}}, {var}, ${var}
    INSTRUCTION = "instruction"    # Lines starting with instruction keywords
    EXAMPLE = "example"            # Example blocks
    ROLE = "role"                  # Role markers (system:, user:, etc.)
    COMMENT = "comment"            # Comments (# or //)
    WHITESPACE = "whitespace"      # Significant whitespace


@dataclass
class PromptElement:
    """A semantic element in a prompt template."""
    type: PromptType
    content: str
    line_start: int
    line_end: int
    raw: str  # Original text including delimiters
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# Variable patterns for different template syntaxes
VARIABLE_PATTERNS = [
    # Jinja2: {{ variable }} or {{ variable | filter }}
    (r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\s*\|\s*[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\}\}', 'jinja2'),
    # Jinja2 blocks: {% if %}, {% for %}, etc.
    (r'\{%\s*([a-zA-Z_]+(?:\s+[^%]+)?)\s*%\}', 'jinja2_block'),
    # Mustache: {{variable}} or {{{variable}}}
    (r'\{\{\{?\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}\}?', 'mustache'),
    # Python f-string style: {variable} or {variable:format}
    (r'\{([a-zA-Z_][a-zA-Z0-9_]*)(?::[^}]*)?\}', 'fstring'),
    # Shell style: ${variable} or $variable
    (r'\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}', 'shell_brace'),
    (r'\$([a-zA-Z_][a-zA-Z0-9_]*)', 'shell'),
    # XML-style: <variable/> or <variable>
    (r'<([A-Z_][A-Z0-9_]*)(?:\s*/>|>)', 'xml'),
    # Placeholder style: [VARIABLE] or [[VARIABLE]]
    (r'\[\[?([A-Z_][A-Z0-9_]*)\]?\]', 'placeholder'),
]

# Instruction keywords that typically start instruction lines
INSTRUCTION_KEYWORDS = [
    'you are', 'you must', 'you should', 'you will', 'you can',
    'do not', "don't", 'never', 'always', 'ensure', 'make sure',
    'remember', 'note:', 'important:', 'warning:', 'caution:',
    'rule:', 'constraint:', 'requirement:', 'instruction:',
    'task:', 'goal:', 'objective:', 'purpose:',
    'format:', 'output:', 'respond', 'reply', 'answer',
    'think', 'analyze', 'consider', 'evaluate',
    'step 1', 'step 2', 'first,', 'then,', 'finally,', 'next,',
    '1.', '2.', '3.', '4.', '5.',
    '-', '*', '•',
]

# Role markers
ROLE_PATTERNS = [
    r'^(system|user|assistant|human|ai|bot):\s*',
    r'^<(system|user|assistant|human|ai)>',
    r'^\[(system|user|assistant|human|ai)\]',
]

# Example block patterns
EXAMPLE_PATTERNS = [
    r'^example\s*\d*:?\s*$',
    r'^input:\s*$',
    r'^output:\s*$',
    r'^expected:\s*$',
    r'^sample:\s*$',
    r'^```',  # Code blocks often contain examples
]


def detect_template_syntax(text: str) -> str:
    """Detect the primary template syntax used in a prompt."""
    syntax_counts = {
        'jinja2': len(re.findall(r'\{\{.*?\}\}|\{%.*?%\}', text)),
        'mustache': len(re.findall(r'\{\{\{?[^{].*?\}\}\}?', text)),
        'fstring': len(re.findall(r'\{[a-zA-Z_][a-zA-Z0-9_]*\}', text)),
        'shell': len(re.findall(r'\$[{a-zA-Z_]', text)),
        'xml': len(re.findall(r'<[A-Z_]+(?:\s*/>|>)', text)),
        'placeholder': len(re.findall(r'\[\[?[A-Z_]+\]?\]', text)),
    }

    if max(syntax_counts.values()) == 0:
        return 'plain'

    return max(syntax_counts, key=syntax_counts.get)


def extract_variables(text: str) -> list[tuple[str, str, int, int]]:
    """Extract all variables from text with their positions."""
    variables = []

    for pattern, syntax in VARIABLE_PATTERNS:
        for match in re.finditer(pattern, text):
            variables.append((
                match.group(1),  # Variable name
                syntax,          # Syntax type
                match.start(),   # Start position
                match.end(),     # End position
            ))

    # Sort by position
    variables.sort(key=lambda x: x[2])
    return variables


def is_instruction_line(line: str) -> bool:
    """Check if a line is an instruction."""
    line_lower = line.lower().strip()
    return any(line_lower.startswith(kw) for kw in INSTRUCTION_KEYWORDS)


def is_role_marker(line: str) -> tuple[bool, str | None]:
    """Check if a line is a role marker."""
    for pattern in ROLE_PATTERNS:
        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            return True, match.group(1).lower()
    return False, None


def is_example_marker(line: str) -> bool:
    """Check if a line marks the start of an example."""
    line_lower = line.lower().strip()
    return any(re.match(pattern, line_lower, re.IGNORECASE) for pattern in EXAMPLE_PATTERNS)


def parse_prompt(text: str) -> list[PromptElement]:
    """
    Parse a prompt template into semantic elements.

    Returns a list of PromptElement objects representing the
    semantic structure of the prompt.
    """
    elements = []
    lines = text.split('\n')
    syntax = detect_template_syntax(text)

    in_example = False
    in_code_block = False
    current_element_lines = []
    current_element_type = None
    element_start_line = 0

    def flush_element():
        nonlocal current_element_lines, current_element_type, element_start_line
        if current_element_lines:
            content = '\n'.join(current_element_lines)
            elements.append(PromptElement(
                type=current_element_type or PromptType.TEXT,
                content=content,
                line_start=element_start_line,
                line_end=element_start_line + len(current_element_lines) - 1,
                raw=content,
                metadata={'syntax': syntax},
            ))
            current_element_lines = []
            current_element_type = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check for code block toggle
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            if in_code_block:
                flush_element()
                element_start_line = i
                current_element_type = PromptType.EXAMPLE
            current_element_lines.append(line)
            if not in_code_block:
                flush_element()
            continue

        # Inside code block - treat as example
        if in_code_block:
            current_element_lines.append(line)
            continue

        # Check for role marker
        is_role, role_name = is_role_marker(stripped)
        if is_role:
            flush_element()
            elements.append(PromptElement(
                type=PromptType.ROLE,
                content=role_name,
                line_start=i,
                line_end=i,
                raw=line,
                metadata={'role': role_name},
            ))
            continue

        # Check for comment
        if stripped.startswith('#') or stripped.startswith('//'):
            flush_element()
            elements.append(PromptElement(
                type=PromptType.COMMENT,
                content=stripped.lstrip('#/ '),
                line_start=i,
                line_end=i,
                raw=line,
            ))
            continue

        # Check for example marker
        if is_example_marker(stripped):
            flush_element()
            in_example = True
            element_start_line = i
            current_element_type = PromptType.EXAMPLE
            current_element_lines.append(line)
            continue

        # Check for instruction
        if is_instruction_line(stripped) and not in_example:
            if current_element_type != PromptType.INSTRUCTION:
                flush_element()
                element_start_line = i
                current_element_type = PromptType.INSTRUCTION
            current_element_lines.append(line)
            continue

        # Check for empty line (ends current context)
        if not stripped:
            if current_element_lines:
                current_element_lines.append(line)
            else:
                # Skip leading empty lines or treat as separator
                if elements:
                    elements.append(PromptElement(
                        type=PromptType.WHITESPACE,
                        content='',
                        line_start=i,
                        line_end=i,
                        raw=line,
                    ))
            in_example = False
            continue

        # Default: text element
        if current_element_type is None:
            current_element_type = PromptType.TEXT
            element_start_line = i
        current_element_lines.append(line)

    # Flush any remaining element
    flush_element()

    # Now extract variables and annotate elements
    for element in elements:
        if element.type in (PromptType.TEXT, PromptType.INSTRUCTION, PromptType.EXAMPLE):
            vars = extract_variables(element.content)
            if vars:
                element.metadata['variables'] = [v[0] for v in vars]

    return elements


def get_all_variables(elements: list[PromptElement]) -> set[str]:
    """Get all variable names from parsed elements."""
    variables = set()
    for element in elements:
        if 'variables' in element.metadata:
            variables.update(element.metadata['variables'])
    return variables
