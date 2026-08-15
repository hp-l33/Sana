"""Sol command line: run released presets; keep laboratory machinery internal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sol.catalog import Catalog, CatalogError, builtin_catalog
from sol.engine import Engine
from sol.evaluation import AcceptanceSpec
from sol.plan import PlanResolutionError, default_repo_root
from sol.preset import PresetError


_PROVENANCE_KEYS = {
    "SOL_PLAN_FINGERPRINT",
    "SOL_EXECUTION_FINGERPRINT",
    "SOL_PRESET",
}


def _root(raw: str | None) -> Path:
    return Path(raw).resolve() if raw else default_repo_root()


def _catalog(extra_paths: list[str]) -> Catalog:
    catalog = builtin_catalog()
    for path in extra_paths:
        catalog = catalog.merge(Catalog.from_toml(path))
    return catalog


def _parse_overrides(raw_items: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for raw in raw_items:
        if "=" not in raw:
            raise PresetError(f"--set expects KEY=VALUE, got {raw!r}")
        key, value = raw.split("=", 1)
        if not key:
            raise PresetError(f"--set key cannot be empty: {raw!r}")
        if key in _PROVENANCE_KEYS:
            raise PresetError(f"--set cannot override provenance key {key}")
        overrides[key] = value
    return overrides


def _doctor(engine: Engine) -> int:
    failures: list[str] = []
    inspected = 0
    for model in engine.models():
        entry = engine.catalog.require("models", model.id)
        profile = engine.repo_root / str(entry.get("profile", ""))
        if not profile.is_file():
            failures.append(f"{model.id}: missing profile {profile}")
            continue
        if model.status != "released":
            continue
        try:
            plugin = engine.plugin(model.id)
            if plugin.reference_names() != model.references:
                failures.append(
                    f"{model.id}: catalog references {model.references} do not match "
                    f"plugin {plugin.reference_names()}"
                )
            if plugin.backend_names() != model.backends:
                failures.append(
                    f"{model.id}: catalog backends {model.backends} do not match "
                    f"plugin {plugin.backend_names()}"
                )
            if plugin.preset_names() != model.presets:
                failures.append(
                    f"{model.id}: catalog presets {model.presets} do not match "
                    f"plugin {plugin.preset_names()}"
                )
        except Exception as exc:
            failures.append(f"{model.id}: cannot validate released plugin: {exc}")
            continue
        for name in model.presets:
            target = f"{model.id}:{name}"
            try:
                engine.inspect(target)
                inspected += 1
                acceptance = plugin.acceptance_path()
                if acceptance is None:
                    failures.append(f"{target}: plugin has no acceptance.toml")
                else:
                    AcceptanceSpec.from_toml(acceptance)
            except Exception as exc:
                failures.append(f"{target}: {exc}")
    print(
        f"catalog: {len(engine.models())} models, "
        f"{len(engine.catalog.entries('optimizations'))} optimizations"
    )
    print(f"presets: {inspected} inspected")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("status: healthy")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", help="Sol checkout root")
    parser.add_argument(
        "--catalog",
        action="append",
        default=[],
        metavar="PATH",
        help="merge a scoped extension catalog; collisions fail closed",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    models = commands.add_parser(
        "models", help="list model release status without importing plugins"
    )
    models.add_argument("--json", action="store_true")
    presets = commands.add_parser("presets", help="list released presets")
    presets.add_argument("model", nargs="?")
    commands.add_parser("optimizations", help="list optimization providers")
    commands.add_parser("doctor", help="validate built-in plugins and presets")

    inspect = commands.add_parser("inspect", help="resolve MODEL:PRESET without running")
    inspect.add_argument("target")
    inspect.add_argument("--json", action="store_true")

    space = commands.add_parser(
        "space", help="show integrated optimizations and their tuning axes"
    )
    space.add_argument("model")
    space.add_argument("--backend", default="auto")

    run = commands.add_parser("run", help="run a released MODEL:PRESET")
    run.add_argument("target")
    run.add_argument("--dry-run", action="store_true", help="prepare in memory only")
    run.add_argument("--print", dest="dry_run", action="store_true", help=argparse.SUPPRESS)
    run.add_argument("--persist", metavar="PATH", help="explicitly save the Run record")
    run.add_argument("--run-root", metavar="PATH", help="runtime artifact directory")
    run.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")

    return parser


def _print_plan(plan, as_json: bool) -> None:
    if as_json:
        print(plan.to_json())
        return
    print(f"preset       : {plan.preset_id}")
    print(f"model        : {plan.model_id} ({plan.model_spec})")
    print(f"capabilities : {', '.join(plan.capabilities)}")
    print(f"prepare      : {', '.join(plan.transform_order) or '-'}")
    print(f"runtime      : {', '.join(plan.runtime_order) or '-'}")
    print(f"launch       : {plan.launch_config}")
    print(f"fingerprint  : {plan.fingerprint}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        engine = Engine(catalog=_catalog(args.catalog), repo_root=_root(args.repo_root))
        if args.command == "models":
            if args.json:
                print(
                    json.dumps(
                        [
                            {
                                "id": model.id,
                                "status": model.status,
                                "references": list(model.references),
                                "backends": list(model.backends),
                                "default_backend": model.default_backend or None,
                                "presets": list(model.presets),
                                "provider": model.provider,
                            }
                            for model in engine.models()
                        ],
                        indent=2,
                        sort_keys=True,
                    )
                )
                return 0
            for model in engine.models():
                presets = ",".join(model.presets) or "-"
                references = ",".join(model.references) or "-"
                backends = ",".join(model.backends) or "-"
                print(
                    f"{model.id:24} status={model.status:12} "
                    f"reference={references:10} backends={backends:12} "
                    f"presets={presets}"
                )
            return 0
        if args.command == "presets":
            for preset in engine.presets(args.model):
                print(preset.id)
            return 0
        if args.command == "optimizations":
            for entry in engine.catalog.entries("optimizations"):
                print(f"{entry.id:24} {entry.get('kind', ''):20} {entry.provider.canonical}")
            return 0
        if args.command == "doctor":
            return _doctor(engine)
        if args.command == "inspect":
            _print_plan(engine.inspect(args.target), args.json)
            return 0
        if args.command == "space":
            print(
                json.dumps(
                    engine.space(args.model, backend=args.backend).as_dict(),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        overrides = _parse_overrides(args.set)
        run = engine.run(
            args.target,
            overrides=overrides,
            dry_run=args.dry_run,
            persist=args.persist,
            run_root=args.run_root,
        )
        if args.dry_run:
            print(run.to_json())
            print("status: planned in memory; nothing launched")
            return 0
        print(f"status: {run.status}")
        print(f"execution: {run.execution_fingerprint}")
        return int(run.returncode or 0)
    except (CatalogError, PresetError, PlanResolutionError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
