# Prompt techniques cheat-sheet

This project uses **two** prompt techniques, deliberately, in different
places. This file gives a quick map.

## ReACT: Retrieval agent

File: `agents/prompts/retrieval_react.txt`

The retrieval agent must reason about *which* tool to call next, so we
use the explicit Thought → Action → Action Input → Observation loop.
We rely on `langgraph.prebuilt.create_react_agent` to drive it. The
prompt's one-shot example walks through an IOC lookup that hits three
tools sequentially.

## One-shot learning: everywhere structure matters

Each of the following prompts contains exactly one fully-worked
example so the LLM imitates the desired output structure:

| Prompt | Why one-shot? |
|---|---|
| `orchestrator.txt` | Force strict JSON shape for downstream routing |
| `validator.txt` | Force strict JSON `{valid, issues, feedback}` |
| `writer_summary.txt` | Force section structure (Summary / Indicators / Actions) |
| `writer_threat_actor.txt` | Force profile structure (Aliases / TTPs / Tooling) |
| `writer_ioc_report.txt` | Force Verdict line + comparison table |
| `writer_correlation.txt` | Force Confidence line + evidence chain |

## Why not chain-of-thought / few-shot / zero-shot?

- **Few-shot:** would bloat token counts on a local Qwen and offered
  little additional structure beyond what a single high-quality example
  already provides. Easy to upgrade later.
- **Pure zero-shot:** local LLMs frequently broke our JSON shape
  contracts; one-shot fixed this in our quick evals.
- **Chain-of-thought:** ReACT is a CoT-derivative; we get reasoning
  traces "for free" from the ReACT loop, made visible in the UI.
