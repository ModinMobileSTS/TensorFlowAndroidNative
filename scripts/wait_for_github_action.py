#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def run_command(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            "command failed ({code}): {cmd}\nstdout:\n{stdout}\nstderr:\n{stderr}".format(
                code=result.returncode,
                cmd=" ".join(args),
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
            )
        )
    return result.stdout


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def infer_repo_slug(repo_root: Path) -> str:
    remote = run_command(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=repo_root,
    ).strip()
    if remote.endswith(".git"):
        remote = remote[:-4]
    if remote.startswith("git@github.com:"):
        return remote.split("git@github.com:", 1)[1]
    if remote.startswith("https://github.com/"):
        return remote.split("https://github.com/", 1)[1]
    raise RuntimeError(f"unsupported remote.origin.url: {remote}")


def infer_head_sha(repo_root: Path) -> str:
    return run_command(["git", "rev-parse", "HEAD"], cwd=repo_root).strip()


def gh_json(args: list[str], cwd: Path | None = None) -> Any:
    output = run_command(["gh", *args], cwd=cwd)
    return json.loads(output)


def fetch_run_by_id(repo: str, run_id: int) -> dict[str, Any]:
    return gh_json(
        [
            "run",
            "view",
            str(run_id),
            "--repo",
            repo,
            "--json",
            "databaseId,status,conclusion,url,workflowName,displayTitle,headBranch,headSha,event,createdAt,updatedAt",
        ]
    )


def find_matching_run(
    repo: str,
    *,
    commit: str | None,
    branch: str | None,
    workflow: str | None,
    event: str | None,
) -> dict[str, Any] | None:
    args = [
        "run",
        "list",
        "--repo",
        repo,
        "--limit",
        "20",
        "--json",
        "databaseId,status,conclusion,url,workflowName,displayTitle,headBranch,headSha,event,createdAt,updatedAt",
    ]
    if commit:
        args.extend(["--commit", commit])
    if branch:
        args.extend(["--branch", branch])
    if workflow:
        args.extend(["--workflow", workflow])
    if event:
        args.extend(["--event", event])

    runs = gh_json(args)
    return runs[0] if runs else None


def format_summary(run: dict[str, Any]) -> str:
    return (
        f"run_id={run['databaseId']} "
        f"status={run['status']} "
        f"conclusion={run.get('conclusion') or ''} "
        f"workflow={run.get('workflowName') or ''} "
        f"title={run.get('displayTitle') or ''} "
        f"branch={run.get('headBranch') or ''} "
        f"sha={run.get('headSha') or ''} "
        f"url={run.get('url') or ''}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Block until a GitHub Actions run completes, then print the result."
    )
    parser.add_argument("--repo", help="GitHub repo slug, for example owner/repo")
    parser.add_argument("--run-id", type=int, help="Specific run id to wait for")
    parser.add_argument("--commit", help="Commit SHA to match when locating a run")
    parser.add_argument("--branch", help="Branch filter when locating a run")
    parser.add_argument("--workflow", help="Workflow name filter when locating a run")
    parser.add_argument("--event", help="Event filter when locating a run")
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="Polling interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.0,
        help="Maximum wait time in seconds, 0 means no timeout",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final run payload as JSON instead of a plain-text summary",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Watch the latest matching run instead of defaulting to the current HEAD commit",
    )
    parser.add_argument(
        "--cwd",
        help="Repository directory used for inferring repo slug and HEAD commit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = find_git_root(Path(args.cwd or Path.cwd()))

    if not args.repo:
        if repo_root is None:
            raise RuntimeError("could not infer repo slug outside a git repository; pass --repo")
        args.repo = infer_repo_slug(repo_root)

    if not args.run_id and not args.latest and not args.commit and repo_root is not None:
        args.commit = infer_head_sha(repo_root)

    start = time.monotonic()
    announced_waiting_for_run = False
    last_error: str | None = None
    last_status: str | None = None
    target_run_id = args.run_id

    while True:
        if args.timeout and time.monotonic() - start > args.timeout:
            print("timed out while waiting for GitHub Actions run", file=sys.stderr)
            return 124

        run: dict[str, Any] | None
        try:
            if target_run_id is not None:
                run = fetch_run_by_id(args.repo, target_run_id)
            else:
                run = find_matching_run(
                    args.repo,
                    commit=args.commit,
                    branch=args.branch,
                    workflow=args.workflow,
                    event=args.event,
                )
                if run is None:
                    if not announced_waiting_for_run:
                        print(
                            "waiting for matching run: repo={repo} commit={commit} branch={branch} workflow={workflow} event={event}".format(
                                repo=args.repo,
                                commit=args.commit or "",
                                branch=args.branch or "",
                                workflow=args.workflow or "",
                                event=args.event or "",
                            ),
                            flush=True,
                        )
                        announced_waiting_for_run = True
                    time.sleep(args.interval)
                    continue
                target_run_id = int(run["databaseId"])
        except RuntimeError as exc:
            message = str(exc)
            if message != last_error:
                print(f"transient gh error, retrying: {message}", file=sys.stderr, flush=True)
                last_error = message
            time.sleep(args.interval)
            continue

        last_error = None

        status = run["status"]
        if status != last_status:
            print(format_summary(run), flush=True)
            last_status = status

        if status == "completed":
            if args.json:
                print(json.dumps(run, ensure_ascii=False, indent=2))
            return 0 if run.get("conclusion") == "success" else 1

        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
