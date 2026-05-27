"""CLI for hebb evaluation benchmarks."""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from pathlib import Path

import click

from eval.benchmarks import BENCHMARKS
from eval.client import (
    BENCHMARK_PORTS,
    HebbClient,
    clean_storage,
    prepare_workdir,
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

_RUN_DIR_RE = re.compile(r"^run-(\d+)$")


def _next_run_dir(version_dir: Path) -> Path:
    """Return ``{version_dir}/run-{N+1}`` where N is the highest existing run.

    Reports are layered as ``{reports_dir}/{benchmark}/{eval_version}/run-N/``
    so dataset and methodology versions stay sticky while multiple runs of the
    same protocol pile up as ``run-1``, ``run-2``, ... — no calendar dates in
    the path. Cleanup is the operator's call.
    """
    version_dir.mkdir(parents=True, exist_ok=True)
    used: list[int] = []
    for child in version_dir.iterdir():
        m = _RUN_DIR_RE.match(child.name)
        if m and child.is_dir():
            used.append(int(m.group(1)))
    next_n = (max(used) + 1) if used else 1
    return version_dir / f"run-{next_n}"


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _bench_base_url(port: int) -> str:
    """URL each benchmark's HebbClient connects to."""
    return f"http://localhost:{port}"


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


async def _fresh_server(workdir: Path, port: int) -> subprocess.Popen:
    """Stop server on ``port``, wipe the workdir's db, start a fresh one.

    Operates entirely inside ``workdir`` — the user's project-root
    ``hebb.json`` and ``hebb.db`` are never touched. The workdir
    itself is kept on disk between runs so a crashed benchmark can be
    inspected by opening ``workdir / "hebb.db"`` directly.
    """
    click.echo(f"Stopping any process on port {port}...")
    stop_server(port)
    click.echo(f"Cleaning workdir db (workdir={workdir.name})...")
    deleted = clean_storage(workdir)
    if deleted:
        click.echo(f"  Deleted: {', '.join(Path(d).name for d in deleted)}")
    click.echo(f"Starting fresh server on port {port}...")
    proc = start_server(workdir)
    await wait_for_server(_bench_base_url(port))
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
@click.option("--top-k", default=None, type=int, help="Search top_k")
@click.option("--llm-model", default=None, help="LLM model for judge")
@click.option("--max-scenarios", default=None, type=int, help="Limit scenarios per dataset")
@click.option(
    "--enable-rerank/--disable-rerank",
    default=None,
    help="Override rerank_enabled in workdir hebb.json (leaves project-root config untouched)",
)
@click.option(
    "--rerank-model",
    default=None,
    help="Override rerank_model (e.g. BAAI/bge-reranker-base, BAAI/bge-reranker-v2-m3)",
)
def run(
    dataset: str,
    mode: str | None,
    top_k: int | None,
    llm_model: str | None,
    max_scenarios: int | None,
    enable_rerank: bool | None,
    rerank_model: str | None,
) -> None:
    """Run evaluation benchmark(s) against an isolated hebb instance per dataset.

    Each benchmark gets its own port (see ``eval.client.BENCHMARK_PORTS``)
    and its own workdir under ``eval/workdirs/<name>/`` with a dedicated
    ``hebb.json`` and ``hebb.db``. Sequential — one server at a time.
    Workdirs are retained between runs for post-hoc inspection.
    """
    settings = load_eval_settings()
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

        click.echo(f"Mode: {settings.mode.value}")
        click.echo(f"Reports root: {settings.reports_dir}")

        server_proc = None
        active_port: int | None = None
        all_results = []
        run_dirs: list[Path] = []

        try:
            for name in names:
                adapter_cls = ADAPTERS.get(name)
                bench_cls = BENCHMARKS.get(name)
                if not adapter_cls or not bench_cls:
                    click.echo(f"Skipping unknown benchmark: {name}")
                    continue
                if name not in BENCHMARK_PORTS:
                    click.echo(
                        f"Skipping {name}: no port allocated in BENCHMARK_PORTS",
                        err=True,
                    )
                    continue

                click.echo(f"\n{'='*60}")
                click.echo(f"Benchmark: {name} ({settings.mode.value})")
                click.echo(f"{'='*60}")

                # 1. Stop the previous benchmark's server (if any) and
                #    spin up an isolated one for this dataset.
                if active_port is not None and active_port != BENCHMARK_PORTS[name]:
                    stop_server(active_port)
                workdir, port = prepare_workdir(
                    name, settings.workdir_root, settings.project_root
                )
                # Patch workdir hebb.json AFTER prepare_workdir so CLI
                # rerank overrides don't require mutating the user's
                # project-root config. Re-applied per benchmark in case a
                # future run targets multiple datasets.
                if enable_rerank is not None or rerank_model is not None:
                    import json as _json
                    cfg_path = workdir / "hebb.json"
                    cfg = _json.loads(cfg_path.read_text())
                    if enable_rerank is not None:
                        cfg["rerank_enabled"] = enable_rerank
                    if rerank_model is not None:
                        cfg["rerank_model"] = rerank_model
                    cfg_path.write_text(_json.dumps(cfg, indent=2))
                    click.echo(
                        f"Rerank override: enabled={cfg.get('rerank_enabled')} "
                        f"model={cfg.get('rerank_model')}"
                    )
                click.echo(f"Workdir: {workdir}  port: {port}")
                server_proc = await _fresh_server(workdir, port)
                active_port = port

                adapter = adapter_cls()
                benchmark = bench_cls(settings)
                version_dir = settings.reports_dir / name / benchmark.eval_version
                run_dir = _next_run_dir(version_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                run_dirs.append(run_dir)
                click.echo(f"Eval version: {benchmark.eval_version}  ->  {run_dir}")

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

                async with HebbClient(_bench_base_url(port)) as client:
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

            # Summary — when running multiple benchmarks, write a single
            # "latest cross-dataset summary" file. It always overwrites so
            # the directory layout stays date-free.
            if len(all_results) > 1:
                summary = render_summary_table(all_results)
                summary_path = settings.reports_dir / "summary-latest.md"
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                summary_path.write_text(summary)
                click.echo(f"\nSummary report: {summary_path}")
                click.echo(summary)

        finally:
            # Dump server stderr if there were issues
            if server_proc and server_proc.stderr:
                server_proc.stderr.close()
            # Only stop the LAST benchmark's server — earlier ones were
            # already stopped at the top of each loop iteration.
            if active_port is not None:
                stop_server(active_port)

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
