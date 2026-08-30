#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


def store_root(platform=None, environment=None, home=None):
    platform = platform or sys.platform
    environment = environment or os.environ
    home = Path(home) if home is not None else Path.home()
    override = environment.get("CHANGE_ANALYSIS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if platform == "win32":
        base = environment.get("LOCALAPPDATA")
        return (Path(base) if base else home / "AppData" / "Local") / "change-analysis"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "change-analysis"
    base = environment.get("XDG_STATE_HOME")
    return (Path(base) if base else home / ".local" / "state") / "change-analysis"


def normalize_identity(value):
    value = value.strip().replace("\\", "/").rstrip("/")
    value = value.removesuffix(".git")
    scp = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(.+)", value)
    if scp and "://" not in value and not re.match(r"^[A-Za-z]:/", value):
        return f"{scp.group(1).lower()}/{scp.group(2).lstrip('/')}"
    parsed = urlsplit(value)
    if parsed.scheme and parsed.hostname:
        path = parsed.path.lstrip("/")
        host = parsed.hostname.lower()
        defaults = {"http": 80, "https": 443, "ssh": 22, "git": 9418}
        if parsed.port is not None and parsed.port != defaults.get(
            parsed.scheme.lower()
        ):
            host = f"{host}:{parsed.port}"
        return f"{host}/{path}"
    path = Path(value).expanduser().resolve()
    return f"path:{os.path.normcase(str(path))}"


def safe_slug(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "repository"


def repository_key(identity):
    normalized = normalize_identity(identity)
    tail = normalized.removeprefix("path:").rstrip("/").split("/")[-1]
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{safe_slug(tail)}-{digest}", normalized


def manifests(root):
    repositories = Path(root) / "v1" / "repositories"
    for path in sorted(repositories.glob("*/reports/*/manifest.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("schema_version") != 1:
            continue
        yield path, data


def matching_reports(root, repository=None):
    for path, data in manifests(root):
        key = data.get("repository", {}).get("key")
        if repository is None or key == repository:
            yield path, data


def resolve_report(root, selector, repository=None):
    candidate = Path(selector).expanduser()
    if candidate.exists():
        if candidate.is_file():
            candidate = candidate.parent
        manifest = candidate / "manifest.json"
        if not manifest.is_file():
            raise ValueError(f"no manifest.json in {candidate}")
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid manifest: {manifest}") from error
        if data.get("schema_version") != 1:
            raise ValueError(f"unsupported manifest schema: {manifest}")
        key = data.get("repository", {}).get("key")
        if repository is not None and key != repository:
            raise ValueError(f"report belongs to repository {key}, not {repository}")
        return candidate.resolve()

    reports = list(matching_reports(root, repository))
    if selector == "latest":
        if repository is None:
            raise ValueError("latest requires --repository")
        complete = [item for item in reports if item[1].get("status") == "complete"]
        if not complete:
            raise ValueError(f"no complete reports for repository {repository}")
        complete.sort(key=lambda item: item[1].get("created_at", ""), reverse=True)
        return complete[0][0].parent.resolve()

    matches = [
        path.parent for path, data in reports if data.get("report_id") == selector
    ]
    if not matches:
        raise ValueError(f"report not found: {selector}")
    if len(matches) > 1:
        joined = "\n".join(str(path.resolve()) for path in matches)
        raise ValueError(f"ambiguous report ID {selector}:\n{joined}")
    return matches[0].resolve()


def command_root(_args):
    print(store_root())


def command_repo_key(args):
    key, normalized = repository_key(args.identity)
    if args.json:
        print(json.dumps({"key": key, "identity": normalized}, indent=2))
    else:
        print(key)


def command_list(args):
    items = []
    for path, data in matching_reports(store_root(), args.repository):
        items.append(
            {
                "report_id": data.get("report_id"),
                "repository": data.get("repository", {}).get("key"),
                "created_at": data.get("created_at"),
                "status": data.get("status"),
                "path": str(path.parent.resolve()),
            }
        )
    print(json.dumps(items, indent=2))


def command_resolve(args):
    print(resolve_report(store_root(), args.selector, args.repository))


def command_next_iteration(args):
    report = resolve_report(store_root(), args.selector, args.repository)
    iterations = report / "iterations"
    numbers = []
    if iterations.is_dir():
        for path in iterations.iterdir():
            if path.is_dir() and re.fullmatch(r"[0-9]+", path.name):
                numbers.append(int(path.name))
    number = max(numbers, default=0) + 1
    print((iterations / f"{number:03d}").resolve())


def parser():
    result = argparse.ArgumentParser(
        description="Find persistent change-analysis reports."
    )
    commands = result.add_subparsers(dest="command", required=True)

    root = commands.add_parser("root", help="Print the platform-specific store root.")
    root.set_defaults(handler=command_root)

    key = commands.add_parser("repo-key", help="Generate a stable repository key.")
    key.add_argument(
        "identity", help="Primary remote URL or canonical repository path."
    )
    key.add_argument(
        "--json", action="store_true", help="Also print the normalized identity."
    )
    key.set_defaults(handler=command_repo_key)

    listing = commands.add_parser("list", help="List valid report manifests.")
    listing.add_argument("--repository", help="Limit results to one repository key.")
    listing.set_defaults(handler=command_list)

    resolve = commands.add_parser(
        "resolve", help="Resolve an ID, latest, or report path."
    )
    resolve.add_argument(
        "selector", help="Report ID, latest, or report directory path."
    )
    resolve.add_argument("--repository", help="Repository key; required with latest.")
    resolve.set_defaults(handler=command_resolve)

    iteration = commands.add_parser(
        "next-iteration", help="Print the next unused iteration directory."
    )
    iteration.add_argument(
        "selector", help="Report ID, latest, or report directory path."
    )
    iteration.add_argument("--repository", help="Repository key; required with latest.")
    iteration.set_defaults(handler=command_next_iteration)
    return result


def main():
    args = parser().parse_args()
    try:
        args.handler(args)
    except ValueError as error:
        print(f"change_reports.py: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
