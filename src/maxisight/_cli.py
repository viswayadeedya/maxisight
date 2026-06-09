from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from maxisight.config import Configuration
from maxisight.crawler.greenhouse import GreenhouseSlugCrawler, MyGreenhouseCrawler
from maxisight.errors import AuthError, CrawlerError, StorageError
from maxisight.storage.job_dataset import JobDataset

app = typer.Typer(
    name="maxisight",
    help="Open source infrastructure for job automation.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Show the current version."""
    from importlib.metadata import version as pkg_version
    console.print(f"maxisight {pkg_version('maxisight')}")


@app.command()
def auth(
    source: str = typer.Argument(help="ATS to authenticate with: greenhouse"),
) -> None:
    """Log in to an ATS and save the session for future crawls."""
    if source == "greenhouse":
        _auth_greenhouse()
    else:
        console.print(f"[red]Auth not supported for '{source}'.[/red]")
        raise typer.Exit(1)


@app.command()
def crawl(
    source: str = typer.Option(..., help="ATS source: greenhouse"),
    query: Optional[str] = typer.Option(None, help="Job title / keyword search (MyGreenhouse)"),
    date_posted: str = typer.Option("past_24_hours", help="past_hour | past_24_hours | past_week | past_month"),
    work_type: Optional[list[str]] = typer.Option(None, help="remote | hybrid | in_person (repeatable)"),
    location: Optional[str] = typer.Option("United States", help="Location filter (default: United States)"),
    worldwide: bool = typer.Option(False, "--worldwide", help="Remove location filter — fetch all countries"),
    token: Optional[str] = typer.Option(None, help="Company slug for per-slug fallback"),
    output: Path = typer.Option(Path("./storage"), help="Output directory"),
) -> None:
    """Crawl job listings from an ATS and save to storage."""
    config = Configuration(output_dir=output)

    if source != "greenhouse":
        console.print(f"[red]Source '{source}' not yet supported.[/red]")
        raise typer.Exit(1)

    if query:
        _crawl_mygreenhouse(query, date_posted, work_type or [], config, None if worldwide else location)
    elif token:
        _crawl_greenhouse_slug(token, config)
    else:
        console.print("[red]Provide --query (cross-company search) or --token (per-company fallback).[/red]")
        raise typer.Exit(1)


@app.command()
def enrich(
    file: Path = typer.Option(..., help="Dataset JSON file from a previous crawl"),
    limit: Optional[int] = typer.Option(None, help="Only enrich first N jobs (for inspection)"),
    output: Path = typer.Option(Path("./storage"), help="Output directory"),
    score: bool = typer.Option(False, "--score", help="Run scorer after enrichment"),
    profile: Path = typer.Option(Path("storage/profiles/default.json"), "--profile", help="Scoring profile JSON"),
) -> None:
    """Fetch full job descriptions and add them to an existing dataset."""
    from maxisight.enricher.greenhouse import GreenhouseEnricher

    if not file.exists():
        console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    dataset = JobDataset(output_dir=output)

    try:
        jobs = dataset.load(file)
    except StorageError as e:
        console.print(f"[red]Storage error:[/red] {e}")
        raise typer.Exit(1) from e

    total = len(jobs)
    target = min(limit, total) if limit else total
    console.print(f"[bold]Enriching {target} of {total} jobs…[/bold] [dim](0.5s delay between requests)[/dim]")

    enricher = GreenhouseEnricher()
    enriched_jobs = enricher.enrich_sync(jobs, limit=limit)

    out_name = "enriched_" + file.stem
    try:
        out_file = dataset.save(enriched_jobs, source=file.parent.name, company_slug=out_name)
    except StorageError as e:
        console.print(f"[red]Storage error:[/red] {e}")
        raise typer.Exit(1) from e

    with_desc = sum(1 for j in enriched_jobs if j.description)
    console.print(f"[green]✓[/green] {with_desc}/{total} jobs have descriptions")
    console.print(f"[green]✓[/green] Saved to [dim]{out_file}[/dim]")

    if score:
        from maxisight.scorer.profile import ScoringProfile
        from maxisight.scorer.scorer import score_jobs

        if not profile.exists():
            console.print(f"[red]Profile not found:[/red] {profile}")
            raise typer.Exit(1)

        with console.status("[bold green]Scoring jobs…[/bold green]"):
            scoring_profile = ScoringProfile.load(profile)
            scored = score_jobs(enriched_jobs, scoring_profile)
            query_slug = file.stem.replace("enriched_", "").rsplit("_", 1)[0]
            scored_path = dataset.save_scored(scored, source="mygreenhouse", query=query_slug)

        table = Table(title=f"Top {min(10, len(scored))} Jobs", show_lines=False)
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", min_width=30)
        table.add_column("Company", min_width=20)
        table.add_column("Score", justify="right", width=7)
        table.add_column("T", justify="right", width=5)
        table.add_column("D", justify="right", width=5)
        table.add_column("F", justify="right", width=5)

        for i, s in enumerate(scored[:10], 1):
            table.add_row(
                str(i),
                s.job.title,
                s.job.company_name or "—",
                f"[bold]{s.score:.3f}[/bold]",
                f"{s.title_score:.2f}",
                f"{s.description_score:.2f}",
                f"{s.freshness_score:.2f}",
            )

        console.print(table)
        console.print(f"\n[green]✓[/green] {len(scored)} jobs passed threshold · saved → [dim]{scored_path}[/dim]")
        console.print(f"[dim]{total - len(scored)} jobs filtered out[/dim]")


# --- helpers ---

def _auth_greenhouse() -> None:
    from maxisight.auth.greenhouse import GreenhouseAuth
    auth = GreenhouseAuth()
    console.print("[bold]Opening Greenhouse login in your browser…[/bold]")
    console.print("[dim]Complete the login, then return here.[/dim]")
    try:
        auth.login()
    except AuthError as e:
        console.print(f"[red]Auth failed:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[green]✓[/green] Session saved to [dim]{auth.session_file}[/dim]")
    console.print("[dim]Run: maxisight crawl --source greenhouse --query \"Software Engineer\"[/dim]")


def _crawl_mygreenhouse(
    query: str,
    date_posted: str,
    work_types: list[str],
    config: Configuration,
    location: str | None = "United States",
) -> None:
    effective_work_types = work_types or ["remote", "hybrid", "in_person"]
    location_label = f", {location}" if location else ", worldwide"

    with console.status(f"[bold green]Searching MyGreenhouse for '{query}'{location_label} ({date_posted})…[/bold green]"):
        try:
            crawler = MyGreenhouseCrawler(user_agent=config.user_agent)
            jobs = crawler.fetch_sync(query, date_posted, effective_work_types, location=location)
        except AuthError as e:
            console.print(f"[red]Auth error:[/red] {e}")
            raise typer.Exit(1) from e
        except CrawlerError as e:
            console.print(f"[red]Crawler error:[/red] {e}")
            raise typer.Exit(1) from e

    if not jobs:
        console.print(f"[yellow]No jobs found for '{query}' ({date_posted}).[/yellow]")
        return

    slug = query.lower().replace(" ", "_")
    from datetime import date
    filename = f"{slug}_{date.today().isoformat()}"

    try:
        dataset = JobDataset(output_dir=config.output_dir)
        out_file = dataset.save(jobs, source="mygreenhouse", company_slug=filename)
    except StorageError as e:
        console.print(f"[red]Storage error:[/red] {e}")
        raise typer.Exit(1) from e

    console.print(
        f"[green]✓[/green] Fetched [bold]{len(jobs)}[/bold] jobs from MyGreenhouse "
        f"([cyan]{query}[/cyan], {date_posted})"
    )
    console.print(f"[green]✓[/green] Saved to [dim]{out_file}[/dim]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Title", style="white")
    table.add_column("Company", style="cyan")
    table.add_column("Location", style="dim")
    table.add_column("Type", style="dim")

    for job in jobs[:20]:
        table.add_row(job.title, job.company_name or "—", job.location or "—", job.work_type or "—")

    if len(jobs) > 20:
        table.add_row(f"… and {len(jobs) - 20} more", "", "", "")

    console.print(table)


def _crawl_greenhouse_slug(token: str, config: Configuration) -> None:
    with console.status(f"[bold green]Fetching jobs from Greenhouse ({token})…[/bold green]"):
        try:
            crawler = GreenhouseSlugCrawler(user_agent=config.user_agent)
            jobs = crawler.fetch_sync(token)
        except CrawlerError as e:
            console.print(f"[red]Crawler error:[/red] {e}")
            raise typer.Exit(1) from e

    if not jobs:
        console.print(f"[yellow]No jobs found for '{token}' on Greenhouse.[/yellow]")
        return

    try:
        dataset = JobDataset(output_dir=config.output_dir)
        out_file = dataset.save(jobs, source="greenhouse", company_slug=token)
    except StorageError as e:
        console.print(f"[red]Storage error:[/red] {e}")
        raise typer.Exit(1) from e

    console.print(
        f"[green]✓[/green] Fetched [bold]{len(jobs)}[/bold] jobs from Greenhouse ([cyan]{token}[/cyan])"
    )
    console.print(f"[green]✓[/green] Saved to [dim]{out_file}[/dim]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Title", style="white")
    table.add_column("Location", style="dim")
    table.add_column("URL", style="cyan", no_wrap=True)

    for job in jobs[:20]:
        table.add_row(job.title, job.location or "—", job.url)

    if len(jobs) > 20:
        table.add_row(f"… and {len(jobs) - 20} more", "", "")

    console.print(table)


cli = app
