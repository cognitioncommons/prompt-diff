"""
Command-line interface for prompt-diff.
"""

import sys
import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from .parser import parse_prompt, PromptType, get_all_variables
from .differ import (
    diff_prompts, format_unified_diff, format_side_by_side_diff,
    ChangeType, DiffResult
)

console = Console()


TYPE_COLORS = {
    PromptType.TEXT: "white",
    PromptType.VARIABLE: "cyan",
    PromptType.INSTRUCTION: "yellow",
    PromptType.EXAMPLE: "green",
    PromptType.ROLE: "magenta",
    PromptType.COMMENT: "dim",
    PromptType.WHITESPACE: "dim",
}

CHANGE_COLORS = {
    ChangeType.ADDED: "green",
    ChangeType.REMOVED: "red",
    ChangeType.MODIFIED: "yellow",
    ChangeType.UNCHANGED: "dim",
}


def format_element_type(ptype: PromptType) -> str:
    """Format element type for display."""
    return f"[{TYPE_COLORS.get(ptype, 'white')}]{ptype.value}[/]"


def format_change_type(ctype: ChangeType) -> str:
    """Format change type for display."""
    symbols = {
        ChangeType.ADDED: "+",
        ChangeType.REMOVED: "-",
        ChangeType.MODIFIED: "~",
        ChangeType.UNCHANGED: " ",
    }
    color = CHANGE_COLORS.get(ctype, 'white')
    return f"[{color}]{symbols[ctype]}[/]"


def print_semantic_diff(result: DiffResult, show_unchanged: bool = False):
    """Print semantic diff with rich formatting."""
    # Header
    console.print(Panel(
        f"[bold]Comparing:[/bold]\n"
        f"  [red]- {result.old_path}[/red]\n"
        f"  [green]+ {result.new_path}[/green]\n\n"
        f"Similarity: [cyan]{result.similarity:.1%}[/cyan]",
        title="Prompt Diff",
        border_style="blue",
    ))

    # Variable changes
    if result.added_variables or result.removed_variables:
        console.print("\n[bold]Variable Changes:[/bold]")
        if result.added_variables:
            for var in sorted(result.added_variables):
                console.print(f"  [green]+[/green] [cyan]{{{{{var}}}}}[/cyan]")
        if result.removed_variables:
            for var in sorted(result.removed_variables):
                console.print(f"  [red]-[/red] [cyan]{{{{{var}}}}}[/cyan]")

    # Element diffs
    console.print("\n[bold]Changes:[/bold]")

    for diff in result.element_diffs:
        if diff.change_type == ChangeType.UNCHANGED and not show_unchanged:
            continue

        marker = format_change_type(diff.change_type)
        type_label = format_element_type(diff.element_type)

        if diff.change_type == ChangeType.ADDED:
            console.print(f"\n{marker} {type_label} (line {diff.new_line + 1})")
            for line in diff.new_content.split('\n')[:5]:
                console.print(f"  [green]{line}[/green]")
            if diff.new_content.count('\n') > 5:
                console.print(f"  [dim]... ({diff.new_content.count(chr(10)) - 4} more lines)[/dim]")

        elif diff.change_type == ChangeType.REMOVED:
            console.print(f"\n{marker} {type_label} (line {diff.old_line + 1})")
            for line in diff.old_content.split('\n')[:5]:
                console.print(f"  [red]{line}[/red]")
            if diff.old_content.count('\n') > 5:
                console.print(f"  [dim]... ({diff.old_content.count(chr(10)) - 4} more lines)[/dim]")

        elif diff.change_type == ChangeType.MODIFIED:
            similarity = diff.details.get('similarity', 0)
            console.print(f"\n{marker} {type_label} (lines {diff.old_line + 1} → {diff.new_line + 1}) [{similarity:.0%} similar]")
            console.print("  [red]Old:[/red]")
            for line in diff.old_content.split('\n')[:3]:
                console.print(f"    [red]{line}[/red]")
            if diff.old_content.count('\n') > 3:
                console.print(f"    [dim]...[/dim]")
            console.print("  [green]New:[/green]")
            for line in diff.new_content.split('\n')[:3]:
                console.print(f"    [green]{line}[/green]")
            if diff.new_content.count('\n') > 3:
                console.print(f"    [dim]...[/dim]")

    # Summary
    summary = result.summary
    console.print(f"\n[bold]Summary:[/bold] "
                  f"[green]+{summary['added']}[/green] "
                  f"[red]-{summary['removed']}[/red] "
                  f"[yellow]~{summary['modified']}[/yellow]")


@click.group()
def main():
    """
    Diff and version control prompt templates with semantic awareness.

    Compares prompt templates and highlights changes in variables,
    instructions, examples, and other semantic elements.

    Examples:

        prompt-diff compare v1/system.txt v2/system.txt

        prompt-diff compare --format unified old.txt new.txt

        prompt-diff parse prompt.txt

        prompt-diff variables prompt.txt
    """
    pass


@main.command()
@click.argument("old_file", type=click.Path(exists=True))
@click.argument("new_file", type=click.Path(exists=True))
@click.option("--format", "-f", "output_format",
              type=click.Choice(["semantic", "unified", "side-by-side", "json"]),
              default="semantic", help="Output format")
@click.option("--show-unchanged", "-u", is_flag=True, help="Show unchanged elements")
@click.option("--context", "-c", default=3, type=int, help="Context lines for unified diff")
def compare(old_file: str, new_file: str, output_format: str, show_unchanged: bool, context: int):
    """
    Compare two prompt template files.

    Shows semantic differences including variable, instruction, and example changes.
    """
    old_text = Path(old_file).read_text()
    new_text = Path(new_file).read_text()

    if output_format == "unified":
        diff = format_unified_diff(old_text, new_text, old_file, new_file, context)
        if diff:
            console.print(Syntax(diff, "diff", theme="monokai"))
        else:
            console.print("[dim]No differences[/dim]")

    elif output_format == "side-by-side":
        lines = format_side_by_side_diff(old_text, new_text)
        table = Table(show_header=True, header_style="bold")
        table.add_column("", width=1)
        table.add_column(old_file, style="red")
        table.add_column(new_file, style="green")
        for marker, old_line, new_line in lines:
            if marker == ' ':
                table.add_row(marker, old_line, new_line)
            elif marker == '<':
                table.add_row("[red]<[/red]", f"[red]{old_line}[/red]", "")
            elif marker == '>':
                table.add_row("[green]>[/green]", "", f"[green]{new_line}[/green]")
            else:
                table.add_row("[yellow]|[/yellow]", f"[red]{old_line}[/red]", f"[green]{new_line}[/green]")
        console.print(table)

    elif output_format == "json":
        result = diff_prompts(old_text, new_text, old_file, new_file)
        output = {
            'old_path': result.old_path,
            'new_path': result.new_path,
            'similarity': result.similarity,
            'added_variables': list(result.added_variables),
            'removed_variables': list(result.removed_variables),
            'summary': result.summary,
            'changes': [
                {
                    'type': d.change_type.value,
                    'element_type': d.element_type.value,
                    'old_content': d.old_content,
                    'new_content': d.new_content,
                    'old_line': d.old_line,
                    'new_line': d.new_line,
                }
                for d in result.element_diffs
                if d.change_type != ChangeType.UNCHANGED or show_unchanged
            ],
        }
        console.print_json(json.dumps(output, indent=2))

    else:  # semantic
        result = diff_prompts(old_text, new_text, old_file, new_file)
        if result.has_changes:
            print_semantic_diff(result, show_unchanged)
        else:
            console.print("[dim]No differences[/dim]")


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--json-output", is_flag=True, help="Output as JSON")
def parse(file: str, json_output: bool):
    """
    Parse a prompt template and show its semantic structure.
    """
    text = Path(file).read_text()
    elements = parse_prompt(text)

    if json_output:
        output = [
            {
                'type': e.type.value,
                'content': e.content,
                'line_start': e.line_start,
                'line_end': e.line_end,
                'metadata': e.metadata,
            }
            for e in elements
        ]
        console.print_json(json.dumps(output, indent=2))
    else:
        table = Table(title=f"Prompt Structure: {file}")
        table.add_column("Lines", justify="right", style="dim")
        table.add_column("Type", style="cyan")
        table.add_column("Preview")
        table.add_column("Variables", style="green")

        for elem in elements:
            if elem.type == PromptType.WHITESPACE:
                continue

            lines = f"{elem.line_start + 1}-{elem.line_end + 1}" if elem.line_start != elem.line_end else str(elem.line_start + 1)
            preview = elem.content[:50].replace('\n', ' ')
            if len(elem.content) > 50:
                preview += "..."
            variables = ", ".join(elem.metadata.get('variables', []))

            table.add_row(
                lines,
                format_element_type(elem.type),
                preview,
                variables or "-",
            )

        console.print(table)


@main.command()
@click.argument("file", type=click.Path(exists=True))
def variables(file: str):
    """
    List all variables in a prompt template.
    """
    text = Path(file).read_text()
    elements = parse_prompt(text)
    vars = get_all_variables(elements)

    if vars:
        console.print(f"[bold]Variables in {file}:[/bold]")
        for var in sorted(vars):
            console.print(f"  [cyan]{{{{{var}}}}}[/cyan]")
        console.print(f"\n[dim]Total: {len(vars)} variables[/dim]")
    else:
        console.print("[dim]No variables found[/dim]")


if __name__ == "__main__":
    main()
