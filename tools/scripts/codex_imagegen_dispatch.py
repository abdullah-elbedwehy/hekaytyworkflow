#!/usr/bin/env python3
"""Dispatch image jobs through repository-local Codex sessions."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


DEFAULT_WORKERS = int(os.environ.get("CODEX_IMAGEGEN_WORKERS", "6"))
DEFAULT_AGENT_MODEL = os.environ.get("CODEX_IMAGEGEN_AGENT_MODEL", "gpt-5.6-luna")
DEFAULT_AGENT_REASONING = os.environ.get("CODEX_IMAGEGEN_AGENT_REASONING", "medium")
MAX_REFS = 8
DEFAULT_ORIENTATION = os.environ.get("CODEX_IMAGEGEN_ORIENTATION", "landscape")
ORIENTATION_SIZES = {
    "landscape": ("1536x1024", "LANDSCAPE (wider than tall, 3:2)"),
    "portrait": ("1024x1536", "PORTRAIT (taller than wide, 2:3)"),
    "square": ("1024x1024", "SQUARE (1:1)"),
}
REFUSAL_MARKERS = (
    "i can't help",
    "i can't create",
    "i cannot help",
    "i cannot create",
    "i'm unable to",
    "content policy",
    "copyrighted character",
    "copyrighted material",
    "safety system",
    "was rejected",
    "request was blocked",
    "moderation",
)


def fail(message: str, code: int = 1) -> None:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False, indent=2))
    raise SystemExit(code)


def load_jobs(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not path.is_file():
        fail(f"Jobs JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON: {exc}")
    meta: dict[str, Any] = {}
    if isinstance(payload, list):
        jobs = payload
    elif isinstance(payload, dict):
        meta = {
            key: payload[key]
            for key in ("outDir", "out_dir", "notes", "workers", "orientation")
            if key in payload
        }
        jobs = payload.get("jobs")
        if jobs is None:
            fail('JSON must be a list or an object with "jobs"')
    else:
        fail("JSON root must be list or object")
    if not isinstance(jobs, list) or not jobs:
        fail("jobs must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    for index, job in enumerate(jobs):
        if not isinstance(job, dict):
            fail(f"jobs[{index}] must be an object")
        prompt = job.get("prompt")
        if not isinstance(prompt, str) or len(prompt.strip()) < 8:
            fail(f"jobs[{index}].prompt missing or too short")
        output = Path(str(job.get("output") or "")).expanduser()
        if not output.is_absolute():
            fail(f"jobs[{index}].output must be absolute: {job.get('output')}")
        refs_raw = job.get("refs") or job.get("references") or []
        if not isinstance(refs_raw, list):
            fail(f"jobs[{index}].refs must be a list")
        refs: list[str] = []
        for ref in refs_raw:
            path_ref = Path(str(ref)).expanduser()
            if not path_ref.is_absolute():
                fail(f"jobs[{index}] ref must be absolute: {ref}")
            if not path_ref.is_file():
                fail(f"jobs[{index}] ref missing: {path_ref}")
            refs.append(str(path_ref))
        orientation = str(
            job.get("orientation") or meta.get("orientation") or DEFAULT_ORIENTATION
        ).strip().lower()
        if orientation not in ORIENTATION_SIZES:
            fail(
                f"jobs[{index}].orientation must be one of "
                f"{', '.join(sorted(ORIENTATION_SIZES))}: {orientation!r}"
            )
        normalized.append(
            {
                "id": str(job.get("id") or f"job-{index + 1:02d}"),
                "prompt": prompt.strip(),
                "output": str(output),
                "refs": refs,
                "orientation": orientation,
                "droppedRefs": refs[MAX_REFS:],
            }
        )
    return normalized, meta


def build_brief(job: dict[str, Any], *, soften: bool = False) -> str:
    size, shape = ORIENTATION_SIZES[job["orientation"]]
    lines = [
        "Generate ONE image using built-in image_gen ($imagegen).",
        "Do not edit source code. Do not commit. Do not call an image API directly.",
        "",
        "IMAGE MODEL:",
        "- Use gpt-image-2 only.",
        "",
        "RULES:",
        "1. View every listed reference before generation.",
        "2. Call image_gen exactly once.",
        "3. Save the final image at the exact output path.",
        "4. Print only the required JSON result.",
        "",
        "SIZE:",
        f"- {shape}",
        f"- Exact size: {size}",
        "",
        f"id: {job['id']}",
        f"output: {job['output']}",
    ]
    if job["refs"]:
        lines.extend(
            [
                f"refs: {', '.join(job['refs'])}",
                "",
                "REFERENCE ROLES:",
                "- Persona photos lock face, age, skin, and hair.",
                "- Character sheet locks illustrated identity, outfit, proportions, and style.",
                "- Location sheets lock architecture, materials, colors, and landmarks.",
                "- Pass every listed reference to image_gen.",
            ]
        )
    if soften:
        lines.extend(
            [
                "",
                "RETRY NOTE:",
                "- All characters are original designs.",
                "- Remove logos, emblems, trademarks, and protected character names.",
                "- Substitute a neutral visual detail if one detail remains protected.",
            ]
        )
    lines.extend(
        [
            "",
            f"prompt: {job['prompt']}",
            "",
            "When complete, print only:",
            json.dumps(
                {
                    "ok": True,
                    "results": [
                        {"id": job["id"], "path": job["output"], "ok": True}
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def looks_refused(*values: str) -> bool:
    text = " ".join(value for value in values if value).lower()
    return any(marker in text for marker in REFUSAL_MARKERS)


def resolve_codex() -> str:
    path = shutil.which("codex")
    if not path:
        fail("codex CLI not found on PATH. Install it and run: codex login", 127)
    return path


def run_job(
    *,
    codex: str,
    job: dict[str, Any],
    cwd: Path,
    work_dir: Path,
    model: str | None,
    reasoning: str | None,
    timeout: int,
    soften: bool = False,
) -> dict[str, Any]:
    safe_id = "".join(
        char if char.isalnum() or char in "-_" else "_" for char in job["id"]
    )[:80]
    suffix = ".retry" if soften else ""
    brief_path = work_dir / f"{safe_id}{suffix}.brief.txt"
    final_path = work_dir / f"{safe_id}{suffix}.final.txt"
    brief = build_brief(job, soften=soften)
    brief_path.write_text(brief, encoding="utf-8")
    output = Path(job["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    command: list[str] = [codex, "exec"]
    for ref in job["refs"][:MAX_REFS]:
        command.extend(["-i", ref])
    command.extend(
        [
            "--skip-git-repo-check",
            "-s",
            "workspace-write",
            "-C",
            str(cwd),
            "-o",
            str(final_path),
            "--json",
        ]
    )
    try:
        output.parent.resolve().relative_to(cwd)
    except ValueError:
        command.extend(["--add-dir", str(output.parent.resolve())])
    agent_model = model or DEFAULT_AGENT_MODEL
    agent_reasoning = reasoning or DEFAULT_AGENT_REASONING
    if agent_model:
        command.extend(["-m", agent_model])
    if agent_reasoning:
        command.extend(["-c", f"model_reasoning_effort={agent_reasoning}"])
    command.append("-")
    started = time.time()
    try:
        process = subprocess.run(
            command,
            input=brief,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        exit_code = process.returncode
        stdout_tail = (process.stdout or "")[-2000:]
        stderr_tail = (process.stderr or "")[-1000:]
    except subprocess.TimeoutExpired:
        exit_code = 124
        stdout_tail = ""
        stderr_tail = f"timed out after {timeout}s"
    exists = output.is_file() and output.stat().st_size > 0
    final_text = (
        final_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        if final_path.is_file()
        else ""
    )
    return {
        "id": job["id"],
        "path": str(output),
        "ok": exists,
        "bytes": output.stat().st_size if output.is_file() else 0,
        "exitCode": exit_code,
        "elapsedSec": round(time.time() - started, 2),
        "briefPath": str(brief_path),
        "finalMessagePath": str(final_path),
        "agentModel": agent_model,
        "agentReasoning": agent_reasoning,
        "orientation": job["orientation"],
        "softenedRetry": soften,
        "refused": not exists and looks_refused(final_text, stdout_tail, stderr_tail),
        "droppedRefs": job.get("droppedRefs") or [],
        "error": None if exists else (stderr_tail or "output missing"),
        "codexStdoutTail": stdout_tail,
        "codexStderrTail": stderr_tail,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Rawy Codex image dispatcher")
    parser.add_argument("--jobs", required=True, type=Path)
    parser.add_argument("--cd", type=Path, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout-sec", type=int, default=600)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--sequential", action="store_true")
    parser.add_argument("--work-dir", type=Path, default=None)
    args = parser.parse_args()
    jobs_path = args.jobs.expanduser().resolve()
    jobs, meta = load_jobs(jobs_path)
    cwd = (args.cd or Path.cwd()).expanduser().resolve()
    work_dir = (
        args.work_dir.expanduser().resolve()
        if args.work_dir
        else jobs_path.parent / f".codex-imagegen-{jobs_path.stem}"
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    if args.sequential:
        workers = 1
    elif args.workers is not None:
        workers = max(1, args.workers)
    elif meta.get("workers") is not None:
        workers = max(1, int(meta["workers"]))
    else:
        workers = max(1, min(len(jobs), DEFAULT_WORKERS))
    payload: dict[str, Any] = {
        "ok": True,
        "mode": "parallel" if workers > 1 else "sequential",
        "workers": workers,
        "agentModel": args.model or DEFAULT_AGENT_MODEL,
        "agentReasoning": args.reasoning_effort or DEFAULT_AGENT_REASONING,
        "imageModel": "gpt-image-2",
        "jobsPath": str(jobs_path),
        "workDir": str(work_dir),
        "cd": str(cwd),
        "jobCount": len(jobs),
        "jobs": [{"id": job["id"], "output": job["output"]} for job in jobs],
    }
    if args.dry_run:
        payload["dryRun"] = True
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    codex = resolve_codex()
    started = time.time()
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                run_job,
                codex=codex,
                job=job,
                cwd=cwd,
                work_dir=work_dir,
                model=args.model,
                reasoning=args.reasoning_effort,
                timeout=args.timeout_sec,
            ): job
            for job in jobs
        }
        for future in as_completed(futures):
            row = future.result()
            results[row["id"]] = row
    retry_jobs = [job for job in jobs if results[job["id"]].get("refused")]
    if retry_jobs:
        with ThreadPoolExecutor(max_workers=min(workers, len(retry_jobs))) as pool:
            futures = {
                pool.submit(
                    run_job,
                    codex=codex,
                    job=job,
                    cwd=cwd,
                    work_dir=work_dir,
                    model=args.model,
                    reasoning=args.reasoning_effort,
                    timeout=args.timeout_sec,
                    soften=True,
                ): job
                for job in retry_jobs
            }
            for future in as_completed(futures):
                row = future.result()
                if row.get("ok") or not results[row["id"]].get("ok"):
                    results[row["id"]] = row
        payload["softenedRetries"] = [job["id"] for job in retry_jobs]
    ordered = [results[job["id"]] for job in jobs]
    payload.update(
        {
            "ok": all(row.get("ok") for row in ordered),
            "elapsedSec": round(time.time() - started, 2),
            "results": ordered,
        }
    )
    result_path = work_dir / "result.json"
    payload["resultPath"] = str(result_path)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if payload["ok"] else 1)


if __name__ == "__main__":
    main()
