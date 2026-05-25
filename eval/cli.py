"""CLI for hebb evaluation benchmarks."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import click

from eval.benchmarks import BENCHMARKS
from eval.client import (
    HebbClient,
    clean_storage,
    start_server,
    stop_server,
    wait_for_server,
)
from eval.config import EvalMode, EvalSettings, load_eval_settings
from eval.datasets import ADAPTERS
from eval.judge import LLMJudge
from eval.reporting.renderer import render_json, render_markdown, render_summary_table

logger = logging.getLogger(__name__)

DATASET_NAMES = list(ADAPTERS.keys())
BENCHMARK_NAMES = list(BENCHMARKS.keys())
_RUNNABLE = [n for n in BENCHMARK_NAMES if n != "memoryarena"]


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _get_server_port(settings: EvalSettings) -> int:
    """Extract port from hebb_url."""
    from urllib.parse import urlparse
    parsed = urlparse(settings.hebb_url)
    return parsed.port or 8321


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """Hebb Mind evaluation benchmarks."""
    _setup_logging(verbose)


# ------------------------------------------------------------------
# download
# ------------------------------------------------------------------


@cli.command()
@click.option(
    "--dataset",
    type=click.Choice(DATASET_NAMES + ["all"]),
    default="all",
    help="Which dataset to download",
)
@click.option("--data-dir", type=click.Path(), default=None, help="Data directory")
def download(dataset: str, data_dir: str | None) -> None:
    """Download benchmark datasets."""
    settings = load_eval_settings()
    target_dir = Path(data_dir) if data_dir else settings.data_dir

    names = _RUNNABLE if dataset == "all" else [dataset]

    async def _download() -> None:
        for name in names:
            adapter_cls = ADAPTERS.get(name)
            if not adapter_cls:
                click.echo(f"Unknown dataset: {name}", err=True)
                continue
            adapter = adapter_cls()
            try:
                path = await adapter.download(target_dir)
                click.echo(f"[OK] {name} -> {path}")
            except NotImplementedError as e:
                click.echo(f"[SKIP] {name}: {e}")
            except Exception as e:
                click.echo(f"[FAIL] {name}: {e}", err=True)

    asyncio.run(_download())


# ------------------------------------------------------------------
# run
# ------------------------------------------------------------------


async def _fresh_server(settings: EvalSettings) -> subprocess.Popen:
    """Stop existing server, clean storage, start a fresh one."""
    port = _get_server_port(settings)
    click.echo("Stopping existing server...")
    stop_server(port)
    click.echo("Cleaning storage (db + knowledge graph)...")
    deleted = clean_storage(settings.project_root)
    if deleted:
        click.echo(f"  Deleted: {', '.join(Path(d).name for d in deleted)}")
    click.echo("Starting fresh server...")
    proc = start_server(settings.project_root)
    await wait_for_server(settings.hebb_url)
    click.echo(f"Server ready (PID {proc.pid})")
    return proc


@cli.command()
@click.option(
    "--dataset",
    type=click.Choice(_RUNNABLE + ["all"]),
    default="all",
    help="Which benchmark to run",
)
@click.option(
    "--mode",
    type=click.Choice(["raw", "consolidated"]),
    default=None,
    help="Evaluation mode: raw (no consolidation) or consolidated (with consolidation)",
)
@click.option("--url", default=None, help="Hebb Mind server URL")
@click.option("--top-k", default=None, type=int, help="Search top_k")
@click.option("--llm-model", default=None, help="LLM model for judge")
@click.option("--max-scenarios", default=None, type=int, help="Limit scenarios per dataset")
def run(
    dataset: str,
    mode: str | None,
    url: str | None,
    top_k: int | None,
    llm_model: str | None,
    max_scenarios: int | None,
) -> None:
    """Run evaluation benchmark(s) against a hebb instance."""
    settings = load_eval_settings()
    if url:
        settings.hebb_url = url
    if top_k:
        settings.search_top_k = top_k
    if llm_model:
        settings.llm_model = llm_model
    if mode:
        settings.mode = EvalMode(mode)

    names = _RUNNABLE if dataset == "all" else [dataset]

    async def _run() -> list:
        judge = LLMJudge(
            model=settings.llm_model,
            api_base=settings.llm_base_url,
            api_key=settings.llm_api_key,
            thinking=settings.llm_thinking,
            temperature=settings.llm_temperature,
            top_p=settings.llm_top_p,
        )

        # Use date-based subfolder for report isolation
        run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_dir = settings.reports_dir / run_ts
        run_dir.mkdir(parents=True, exist_ok=True)
        click.echo(f"Mode: {settings.mode.value}")
        click.echo(f"Reports: {run_dir}")

        server_proc = None
        all_results = []

        try:
            for name in names:
                adapter_cls = ADAPTERS.get(name)
                bench_cls = BENCHMARKS.get(name)
                if not adapter_cls or not bench_cls:
                    click.echo(f"Skipping unknown benchmark: {name}")
                    continue

                click.echo(f"\n{'='*60}")
                click.echo(f"Benchmark: {name} ({settings.mode.value})")
                click.echo(f"{'='*60}")

                # 1. Fresh server for each dataset
                server_proc = await _fresh_server(settings)

                adapter = adapter_cls()
                benchmark = bench_cls(settings)

                # 2. Download
                click.echo("Downloading dataset...")
                try:
                    data_path = await adapter.download(settings.data_dir)
                except Exception as e:
                    click.echo(f"Download failed: {e}", err=True)
                    continue

                # 3. Load
                click.echo("Loading dataset...")
                scenarios = adapter.load(data_path)
                if max_scenarios:
                    scenarios = scenarios[:max_scenarios]
                total_q = sum(len(s.questions) for s in scenarios)
                click.echo(f"Loaded {len(scenarios)} scenarios, {total_q} questions")

                async with HebbClient(settings.hebb_url) as client:
                    # 4. Ingest into mem_hippocampus
                    click.echo("Ingesting memories into mem_hebb...")
                    await benchmark.setup(client, scenarios)

                    # 5. Consolidation (if mode == consolidated)
                    consolidation_stats = None
                    if settings.mode == EvalMode.CONSOLIDATED:
                        click.echo("Triggering memory consolidation...")
                        consolidation_stats = await client.trigger_consolidation()
                        click.echo(
                            f"  Consolidation: {consolidation_stats.get('succeeded', 0)}"
                            f"/{consolidation_stats.get('processed', 0)} succeeded"
                        )

                    # 6. Run evaluation
                    click.echo("Running evaluation...")
                    result = await benchmark.run(client, scenarios, judge)
                    if consolidation_stats:
                        result.config["consolidation"] = consolidation_stats
                    all_results.append(result)

                    # 7. Report
                    json_path = run_dir / f"{name}.json"
                    md_path = run_dir / f"{name}.md"
                    render_json(result, json_path)
                    render_markdown(result, md_path)

                    click.echo(f"\nResults for {name}:")
                    click.echo(f"  Accuracy: {result.accuracy:.1%} ({result.correct}/{result.total_questions})")
                    click.echo(f"  Avg latency: {result.avg_latency_ms:.1f}ms")
                    if result.accuracy_by_category:
                        for cat, acc in sorted(result.accuracy_by_category.items()):
                            click.echo(f"  {cat}: {acc:.1%}")
                    click.echo(f"  Reports: {json_path}, {md_path}")

            # Summary
            if len(all_results) > 1:
                summary = render_summary_table(all_results)
                summary_path = run_dir / "summary.md"
                summary_path.write_text(summary)
                click.echo(f"\nSummary report: {summary_path}")
                click.echo(summary)

        finally:
            # Dump server stderr if there were issues
            if server_proc and server_proc.stderr:
                server_proc.stderr.close()
            port = _get_server_port(settings)
            stop_server(port)

        return all_results

    asyncio.run(_run())


# ------------------------------------------------------------------
# list
# ------------------------------------------------------------------


@cli.command("list")
def list_benchmarks() -> None:
    """List available benchmarks and download status."""
    settings = load_eval_settings()

    click.echo("Available benchmarks:")
    click.echo(f"{'Name':<15} {'Status':<12} {'Data Path'}")
    click.echo("-" * 60)
    for name in ADAPTERS:
        data_dir = settings.data_dir / name
        if data_dir.exists() and any(data_dir.iterdir()):
            status = "downloaded"
        else:
            status = "not downloaded"
        if name == "memoryarena":
            status = "stub"
        click.echo(f"{name:<15} {status:<12} {data_dir}")
