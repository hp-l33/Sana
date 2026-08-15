import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .adaptation import AdaptationManager, AdaptationStore
from .engine import Engine
from .errors import SolError


def _json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _manager(args: argparse.Namespace) -> AdaptationManager:
    root = Path(args.state_root) if getattr(args, "state_root", None) else None
    return AdaptationManager(AdaptationStore(root))


def _arguments(items: Sequence[str]) -> Sequence[str]:
    return items[1:] if items and items[0] == "--" else items


def _options(items: Sequence[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise SolError(f"optimization override must be KEY=VALUE, got {item!r}")
        key, raw = item.split("=", 1)
        if not key or key in result:
            raise SolError(f"invalid or duplicate optimization option {key!r}")
        try:
            result[key] = json.loads(raw)
        except json.JSONDecodeError:
            result[key] = raw
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sol", description="Produce and run optimized model plugins")
    sub = parser.add_subparsers(dest="command", required=True)

    models = sub.add_parser("models", help="list discovered model plugins")
    models.add_argument("--all", action="store_true", help="include draft plugins")
    models.add_argument("--json", action="store_true")

    doctor = sub.add_parser("doctor", help="validate the Engine and plugin manifests")
    doctor.add_argument("--json", action="store_true")

    space = sub.add_parser("space", help="inspect a target-specific optimization space")
    space.add_argument("model")
    space.add_argument("--backend", required=True)
    space.add_argument("--target", required=True)

    inspect_plan = sub.add_parser("inspect", help="resolve a release preset without executing it")
    inspect_plan.add_argument("model")
    inspect_plan.add_argument("--preset", required=True)
    inspect_plan.add_argument("--target", required=True)
    inspect_plan.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    inspect_plan.set_defaults(arguments=())

    run = sub.add_parser("run", help="execute a released model preset")
    run.add_argument("model")
    run.add_argument("--preset", required=True)
    run.add_argument("--target", required=True)
    run.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    run.set_defaults(arguments=())

    adapt = sub.add_parser("adapt", help="drive the deterministic model adaptation lifecycle")
    adapt_sub = adapt.add_subparsers(dest="adapt_command", required=True)

    start = adapt_sub.add_parser("start", help="start an adaptation run")
    start.add_argument("model")
    start.add_argument("--reference", required=True)
    start.add_argument("--backend", required=True)
    start.add_argument("--target", required=True)
    start.add_argument("--budget", type=int, required=True)
    start.add_argument("--repo-root", default=".")
    start.add_argument("--state-root")
    start.add_argument("--json", action="store_true")

    for name, help_text in (
        ("status", "show durable adaptation state"),
        ("next", "show the next bounded agent task"),
        ("scaffold", "create the model-owned plugin skeleton"),
    ):
        command = adapt_sub.add_parser(name, help=help_text)
        command.add_argument("run_id")
        command.add_argument("--state-root")
        command.add_argument("--json", action="store_true")

    submit = adapt_sub.add_parser("submit", help="validate evidence and advance one stage")
    submit.add_argument("run_id")
    submit.add_argument("--evidence", type=Path, required=True)
    submit.add_argument("--state-root")
    submit.add_argument("--json", action="store_true")

    approve = adapt_sub.add_parser("approve", help="record maintainer approval and release the manifest")
    approve.add_argument("run_id")
    approve.add_argument("--by", required=True)
    approve.add_argument("--state-root")
    approve.add_argument("--json", action="store_true")
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    raw = list(sys.argv[1:] if argv is None else argv)
    separator = raw.index("--") if "--" in raw else None
    engine_arguments = raw[separator + 1 :] if separator is not None else []
    parser_arguments = raw[:separator] if separator is not None else raw
    parser = build_parser()
    args = parser.parse_args(parser_arguments)
    if separator is not None and args.command not in {"inspect", "run"}:
        parser.error("-- model arguments are only valid for inspect and run")
    args.arguments = engine_arguments
    return args


def _adapt(args: argparse.Namespace) -> int:
    manager = _manager(args)
    if args.adapt_command == "start":
        state = manager.start(
            args.model,
            args.reference,
            args.backend,
            args.target,
            args.budget,
            Path(args.repo_root),
        )
        result = manager.status(state["id"])
    elif args.adapt_command == "status":
        result = manager.status(args.run_id)
    elif args.adapt_command == "next":
        result = manager.next(args.run_id)
    elif args.adapt_command == "scaffold":
        result = manager.scaffold(args.run_id)
    elif args.adapt_command == "submit":
        result = manager.submit(args.run_id, args.evidence)
    elif args.adapt_command == "approve":
        result = manager.approve(args.run_id, args.by)
    else:  # pragma: no cover - argparse enforces this
        raise AssertionError(args.adapt_command)

    if args.json:
        _json(result)
    elif args.adapt_command == "next":
        print(f"{result['stage']}: {result['title']} [{result['action']}]")
        print(result["instructions"])
    else:
        print(f"run:   {result['id']}")
        print(f"stage: {result['stage']}")
        print(f"next:  {result['next']['title']}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "adapt":
            return _adapt(args)
        engine = Engine()
        if args.command == "models":
            models = engine.models(include_drafts=args.all)
            if args.json:
                _json([item.to_dict() for item in models])
            elif not models:
                print("No model plugins installed.")
            else:
                for item in models:
                    print(f"{item.id}\t{item.status}\t{','.join(item.presets) or '-'}")
            return 0
        if args.command == "doctor":
            result: Dict[str, Any] = engine.doctor()
            _json(result) if args.json else print(
                f"healthy: {result['message']} ({result['model_plugins']} plugins)"
            )
            return 0
        if args.command == "space":
            _json(engine.search_space(args.model, args.backend, args.target))
            return 0
        if args.command == "inspect":
            _json(
                engine.inspect(
                    args.model,
                    args.preset,
                    args.target,
                    _arguments(args.arguments),
                    _options(args.set),
                ).to_dict()
            )
            return 0
        if args.command == "run":
            engine.run(
                args.model,
                args.preset,
                args.target,
                _arguments(args.arguments),
                _options(args.set),
            )
            return 0
        raise AssertionError(args.command)  # pragma: no cover
    except SolError as exc:
        print(f"sol: error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"sol: command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1
