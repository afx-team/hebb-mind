"""Report generation: JSON + Markdown."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from eval.benchmarks.base import BenchmarkResult

logger = logging.getLogger(__name__)


def render_json(result: BenchmarkResult, output_path: Path) -> Path:
    """Write benchmark result as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = asdict(result)
    # Trim individual results for readability — keep summary fields only
    for r in data.get("individual_results", []):
        r.pop("retrieved_memories", None)

    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    logger.info("JSON report saved to %s", output_path)
    return output_path


def render_markdown(result: BenchmarkResult, output_path: Path) -> Path:
    """Write benchmark result as a Markdown report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    config = result.config
    lines: list[str] = []
    lines.append(f"# Hippocampus Evaluation Report: {result.dataset_name}")
    lines.append("")
    lines.append(f"**Date**: {result.timestamp}")
    eval_mode = config.get('mode', 'raw')
    lines.append(f"**Mode**: {eval_mode}")
    lines.append(f"**Model (judge)**: {config.get('llm_model', 'N/A')}")
    thinking = config.get('llm_thinking')
    if thinking is not None:
        lines.append(f"**Thinking**: {'enabled' if thinking else 'disabled'}")
    lines.append(f"**Temperature**: {config.get('llm_temperature', 'N/A')}")
    lines.append(f"**Top-p**: {config.get('llm_top_p', 'N/A')}")
    lines.append(f"**Search top_k**: {config.get('search_top_k', 'N/A')}")
    lines.append(f"**Concurrency**: {config.get('concurrency', 'N/A')}")
    num_scenarios = config.get('num_scenarios')
    if num_scenarios is not None:
        lines.append(f"**Scenarios**: {num_scenarios}")
    lines.append("")

    # Consolidation stats (consolidated mode)
    consolidation = config.get('consolidation')
    if consolidation:
        lines.append("## Consolidation")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Processed | {consolidation.get('processed', 0)} |")
        lines.append(f"| Succeeded | {consolidation.get('succeeded', 0)} |")
        lines.append(f"| Failed | {consolidation.get('failed', 0)} |")
        lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Questions | {result.total_questions} |")
    lines.append(f"| Correct | {result.correct} |")
    lines.append(f"| **Accuracy** | **{result.accuracy:.1%}** |")
    lines.append(f"| Avg Latency | {result.avg_latency_ms:.1f}ms |")
    # Total wall-clock time estimate
    total_time_s = result.avg_latency_ms * result.total_questions / 1000
    if total_time_s > 60:
        lines.append(f"| Est. Total Time | {total_time_s / 60:.1f}min |")
    else:
        lines.append(f"| Est. Total Time | {total_time_s:.1f}s |")
    lines.append("")

    # Accuracy by category
    if result.accuracy_by_category:
        lines.append("## Accuracy by Category")
        lines.append("")
        lines.append("| Category | Accuracy |")
        lines.append("|----------|----------|")
        for cat, acc in sorted(result.accuracy_by_category.items()):
            lines.append(f"| {cat} | {acc:.1%} |")
        lines.append("")

    # Retrieval metrics
    if result.retrieval_metrics:
        lines.append("## Retrieval Quality")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for metric, value in sorted(result.retrieval_metrics.items()):
            lines.append(f"| {metric} | {value:.3f} |")
        lines.append("")

    # Error analysis — sample wrong answers
    wrong = [r for r in result.individual_results if not r.is_correct]
    if wrong:
        lines.append("## Error Analysis")
        lines.append("")
        lines.append(f"Total errors: {len(wrong)} / {result.total_questions}")
        lines.append("")
        # Show up to 5 sample errors
        for r in wrong[:5]:
            lines.append(f"### {r.question_id} ({r.category})")
            lines.append(f"- **Q**: {r.question}")
            lines.append(f"- **Expected**: {r.ground_truth}")
            lines.append(f"- **Generated**: {r.generated_answer}")
            lines.append("")

    # Config
    lines.append("## Configuration")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(result.config, indent=2))
    lines.append("```")
    lines.append("")

    output_path.write_text("\n".join(lines))
    logger.info("Markdown report saved to %s", output_path)
    return output_path


def render_summary_table(results: list[BenchmarkResult]) -> str:
    """Generate a combined summary table for multiple benchmark runs."""
    lines: list[str] = []
    lines.append("# Hippocampus Evaluation Summary")
    lines.append("")
    mode = results[0].config.get("mode", "raw") if results else "raw"
    lines.append(f"**Mode**: {mode}")
    lines.append("")
    lines.append("| Benchmark | Questions | Correct | Accuracy | Avg Latency |")
    lines.append("|-----------|-----------|---------|----------|-------------|")
    for r in results:
        lines.append(
            f"| {r.dataset_name} | {r.total_questions} | {r.correct} "
            f"| {r.accuracy:.1%} | {r.avg_latency_ms:.1f}ms |"
        )
    lines.append("")
    return "\n".join(lines)
