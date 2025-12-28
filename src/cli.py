"""Command-line interface for the localization pipeline."""

import click
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel

from .extraction.xcstrings_parser import XCStringsParser
from .extraction.xcstrings_writer import XCStringsWriter
from .translation.translator import HybridTranslator
from .validation.llm_reviewer import LLMReviewer, ReviewResult
from .config import config

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """MintDeck iOS Localization Pipeline CLI."""
    pass


@cli.command()
@click.option(
    "--input", "-i",
    "input_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to input .xcstrings file"
)
@click.option(
    "--output", "-o",
    "output_path",
    type=click.Path(),
    help="Path to output .xcstrings file (defaults to input path)"
)
@click.option(
    "--languages", "-l",
    default="de,fr,it,es,ro",
    help="Comma-separated list of target language codes"
)
@click.option(
    "--quality-threshold", "-q",
    default=80.0,
    type=float,
    help="Quality threshold for GPT-4 fallback (0-100)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview translations without saving"
)
@click.option(
    "--force-gpt4",
    is_flag=True,
    help="Force GPT-4 for all translations (skip DeepL)"
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of strings to translate (for testing)"
)
def translate(
    input_path: str,
    output_path: Optional[str],
    languages: str,
    quality_threshold: float,
    dry_run: bool,
    force_gpt4: bool,
    limit: Optional[int],
):
    """Translate an .xcstrings file to target languages."""
    # Validate config
    errors = config.validate()
    if errors:
        console.print("[red]Configuration errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise click.Abort()

    # Parse input file
    console.print(f"[blue]Reading:[/blue] {input_path}")
    parser = XCStringsParser()
    xcstrings = parser.parse(input_path)

    # Get translatable strings
    all_strings = xcstrings.get_translatable_strings()
    console.print(f"[green]Found:[/green] {len(all_strings)} translatable strings")

    # Apply limit if specified
    if limit:
        all_strings = dict(list(all_strings.items())[:limit])
        console.print(f"[yellow]Limited to:[/yellow] {len(all_strings)} strings")

    # Parse target languages
    target_langs = [lang.strip() for lang in languages.split(",")]
    console.print(f"[blue]Target languages:[/blue] {', '.join(target_langs)}")

    # Initialize translator
    translator = HybridTranslator(quality_threshold=quality_threshold)

    # Translate to each language
    for lang in target_langs:
        console.print(f"\n[bold cyan]Translating to {lang.upper()}...[/bold cyan]")

        # Filter strings that need translation for this language
        strings_to_translate = {}
        for key, source in all_strings.items():
            if key in xcstrings.strings:
                entry = xcstrings.strings[key]
                if not entry.has_translation(lang):
                    strings_to_translate[key] = source

        if not strings_to_translate:
            console.print(f"  [green]All strings already translated for {lang}[/green]")
            continue

        console.print(f"  [yellow]Strings to translate:[/yellow] {len(strings_to_translate)}")

        # Translate with progress bar
        results = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Translating to {lang}", total=len(strings_to_translate))

            def update_progress(current, total, key):
                progress.update(task, completed=current, description=f"[{lang}] {key[:40]}...")

            results, stats = translator.translate_batch(
                strings=strings_to_translate,
                target_lang=lang,
                progress_callback=update_progress if not force_gpt4 else None,
            )

        # Update xcstrings with translations
        for result in results:
            if result.success and result.key in xcstrings.strings:
                xcstrings.strings[result.key].set_translation(lang, result.translation, "translated")

        # Print statistics
        _print_stats(stats, lang)

        # Print quality breakdown
        _print_quality_breakdown(results)

    # Write output
    if not dry_run:
        output = output_path or input_path
        console.print(f"\n[blue]Writing:[/blue] {output}")
        writer = XCStringsWriter()
        writer.write(xcstrings, output)
        console.print("[green]Done![/green]")
    else:
        console.print("\n[yellow]Dry run - no changes saved[/yellow]")


@cli.command()
@click.option(
    "--input", "-i",
    "input_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to .xcstrings file"
)
def stats(input_path: str):
    """Show statistics for an .xcstrings file."""
    parser = XCStringsParser()
    xcstrings = parser.parse(input_path)

    table = Table(title=f"Statistics for {Path(input_path).name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    # Total strings
    total = len(xcstrings.strings)
    table.add_row("Total strings", str(total))

    # Source language
    table.add_row("Source language", xcstrings.source_language)

    # Translatable strings
    translatable = xcstrings.get_translatable_strings()
    table.add_row("Translatable strings", str(len(translatable)))

    # Languages present
    languages = set()
    for entry in xcstrings.strings.values():
        languages.update(entry.localizations.keys())
    table.add_row("Languages", ", ".join(sorted(languages)) or "None")

    # Translation coverage by language
    for lang in sorted(languages):
        if lang == xcstrings.source_language:
            continue
        translated = sum(
            1 for entry in xcstrings.strings.values()
            if entry.has_translation(lang)
        )
        coverage = (translated / len(translatable)) * 100 if translatable else 0
        table.add_row(f"  {lang} coverage", f"{translated}/{len(translatable)} ({coverage:.1f}%)")

    console.print(table)


@cli.command()
@click.option(
    "--input", "-i",
    "input_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to .xcstrings file"
)
@click.option(
    "--language", "-l",
    required=True,
    help="Language code to show untranslated strings for"
)
@click.option(
    "--limit",
    type=int,
    default=20,
    help="Limit number of strings to show"
)
def untranslated(input_path: str, language: str, limit: int):
    """Show untranslated strings for a specific language."""
    parser = XCStringsParser()
    xcstrings = parser.parse(input_path)

    untranslated_keys = xcstrings.get_untranslated_keys(language)

    console.print(f"[cyan]Untranslated strings for {language}:[/cyan] {len(untranslated_keys)} total")

    if not untranslated_keys:
        console.print("[green]All strings are translated![/green]")
        return

    table = Table(show_header=True)
    table.add_column("Key", style="dim", max_width=40)
    table.add_column("Source Value", max_width=60)

    for key in untranslated_keys[:limit]:
        if key in xcstrings.strings:
            source = xcstrings.strings[key].get_source_value(xcstrings.source_language)
            table.add_row(key[:40], source[:60])

    console.print(table)

    if len(untranslated_keys) > limit:
        console.print(f"\n[dim]... and {len(untranslated_keys) - limit} more[/dim]")


def _print_stats(stats, lang: str):
    """Print translation statistics."""
    table = Table(title=f"Translation Stats for {lang.upper()}")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    total = stats.total
    table.add_row("Total", str(total), "100%")
    table.add_row("DeepL", str(stats.deepl_count), f"{stats.deepl_count/total*100:.1f}%")
    table.add_row("GPT-4 (fallback)", str(stats.gpt4_count), f"{stats.gpt4_count/total*100:.1f}%")
    table.add_row("Failed", str(stats.failed_count), f"{stats.failed_count/total*100:.1f}%")

    console.print(table)


def _print_quality_breakdown(results):
    """Print quality score breakdown."""
    green = sum(1 for r in results if r.quality_score.category == "green")
    yellow = sum(1 for r in results if r.quality_score.category == "yellow")
    red = sum(1 for r in results if r.quality_score.category == "red")
    total = len(results)

    panel_content = (
        f"[green]Green (95+):[/green] {green} ({green/total*100:.1f}%)\n"
        f"[yellow]Yellow (80-94):[/yellow] {yellow} ({yellow/total*100:.1f}%)\n"
        f"[red]Red (<80):[/red] {red} ({red/total*100:.1f}%)"
    )

    console.print(Panel(panel_content, title="Quality Breakdown"))


@cli.command()
@click.option(
    "--input", "-i",
    "input_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to .xcstrings file"
)
@click.option(
    "--language", "-l",
    "language",
    required=True,
    help="Language code to verify (e.g., 'de', 'fr')"
)
@click.option(
    "--all", "-a",
    "review_all",
    is_flag=True,
    help="Review all translations, not just those needing review"
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of translations to review"
)
@click.option(
    "--fix",
    is_flag=True,
    help="Apply suggested fixes (with confirmation)"
)
def verify(
    input_path: str,
    language: str,
    review_all: bool,
    limit: Optional[int],
    fix: bool,
):
    """Verify translation quality using LLM semantic review.

    Reviews existing translations for semantic accuracy and fluency.
    By default, only reviews translations marked as 'needs_review'.
    Use --all to review all translations.
    """
    # Validate config
    if not config.openai_api_key:
        console.print("[red]Error: OPENAI_API_KEY is not set[/red]")
        raise click.Abort()

    # Parse input file
    console.print(f"[blue]Reading:[/blue] {input_path}")
    parser = XCStringsParser()
    xcstrings = parser.parse(input_path)

    # Collect translations to review
    translations_to_review = []
    for key, entry in xcstrings.strings.items():
        if not entry.has_translation(language):
            continue

        loc = entry.localizations.get(language)
        if not loc or not loc.string_unit:
            continue

        # Get translation state
        state = loc.string_unit.state
        translation = loc.string_unit.value
        source = entry.get_source_value(xcstrings.source_language)

        # Filter based on review_all flag
        if review_all or state == "needs_review":
            translations_to_review.append({
                "key": key,
                "source": source,
                "translation": translation,
                "state": state,
            })

    if not translations_to_review:
        if review_all:
            console.print(f"[yellow]No translations found for {language}[/yellow]")
        else:
            console.print(f"[green]No translations need review for {language}[/green]")
            console.print("[dim]Use --all to review all translations[/dim]")
        return

    # Apply limit
    if limit:
        translations_to_review = translations_to_review[:limit]

    console.print(f"[cyan]Reviewing {len(translations_to_review)} translations for {language.upper()}...[/cyan]")

    # Initialize reviewer
    reviewer = LLMReviewer()

    # Review with progress
    results: List[ReviewResult] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Reviewing {language}", total=len(translations_to_review))

        def update_progress(current, total, key):
            progress.update(task, completed=current, description=f"[{language}] {key[:40]}...")

        results = reviewer.review_batch(
            translations=translations_to_review,
            target_lang=language,
            progress_callback=update_progress,
        )

    # Separate results by status
    passed = [r for r in results if r.passed]
    needs_attention = [r for r in results if r.needs_attention]

    # Print summary
    _print_verify_summary(results)

    # Print issues table if any
    if needs_attention:
        _print_issues_table(needs_attention)

        # Handle fix option
        if fix and needs_attention:
            _apply_fixes(xcstrings, needs_attention, language, input_path)
    else:
        console.print("\n[green]All reviewed translations look good![/green]")


def _print_verify_summary(results: List[ReviewResult]):
    """Print verification summary."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    avg_semantic = sum(r.semantic_score for r in results) / total if total else 0
    avg_fluency = sum(r.fluency_score for r in results) / total if total else 0

    panel_content = (
        f"[bold]Total reviewed:[/bold] {total}\n"
        f"[green]Passed:[/green] {passed} ({passed/total*100:.1f}%)\n"
        f"[yellow]Needs attention:[/yellow] {failed} ({failed/total*100:.1f}%)\n"
        f"\n"
        f"[dim]Avg semantic score:[/dim] {avg_semantic:.1f}\n"
        f"[dim]Avg fluency score:[/dim] {avg_fluency:.1f}"
    )

    console.print(Panel(panel_content, title="Verification Summary"))


def _print_issues_table(results: List[ReviewResult]):
    """Print table of translations with issues."""
    console.print("\n[bold yellow]Translations needing attention:[/bold yellow]\n")

    table = Table(show_header=True)
    table.add_column("Key", style="dim", max_width=25)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Issues", max_width=40)
    table.add_column("Suggested Fix", max_width=40)

    for r in results:
        score_color = "green" if r.overall_score >= 80 else "yellow" if r.overall_score >= 60 else "red"
        score_str = f"[{score_color}]{r.overall_score:.0f}[/{score_color}]"

        issues_str = "\n".join(r.issues[:2]) if r.issues else "[dim]Low scores[/dim]"
        fix_str = r.suggested_fix[:80] + "..." if r.suggested_fix and len(r.suggested_fix) > 80 else (r.suggested_fix or "[dim]—[/dim]")

        table.add_row(
            r.key[:25],
            score_str,
            issues_str,
            fix_str,
        )

    console.print(table)


def _apply_fixes(xcstrings, results: List[ReviewResult], language: str, output_path: str):
    """Apply suggested fixes with confirmation."""
    fixable = [r for r in results if r.suggested_fix]

    if not fixable:
        console.print("\n[yellow]No suggested fixes available[/yellow]")
        return

    console.print(f"\n[cyan]Found {len(fixable)} translations with suggested fixes[/cyan]")

    # Show what will be changed
    for r in fixable[:5]:  # Show first 5
        console.print(f"\n[dim]{r.key}:[/dim]")
        console.print(f"  [red]- {r.translation}[/red]")
        console.print(f"  [green]+ {r.suggested_fix}[/green]")

    if len(fixable) > 5:
        console.print(f"\n[dim]... and {len(fixable) - 5} more[/dim]")

    # Confirm
    if not click.confirm("\nApply these fixes?"):
        console.print("[yellow]Fixes not applied[/yellow]")
        return

    # Apply fixes
    for r in fixable:
        if r.key in xcstrings.strings:
            xcstrings.strings[r.key].set_translation(language, r.suggested_fix, "translated")

    # Write output
    from .extraction.xcstrings_writer import XCStringsWriter
    writer = XCStringsWriter()
    writer.write(xcstrings, output_path)

    console.print(f"[green]Applied {len(fixable)} fixes to {output_path}[/green]")


if __name__ == "__main__":
    cli()
