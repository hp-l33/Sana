"""Command-line frontend for the experimental Sol-Engine control plane."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from sol_engine import _toml
from sol_engine.catalog import Catalog, CatalogError, builtin_catalog
from sol_engine.plan import PlanResolutionError, default_repo_root, resolve_recipe
from sol_engine.recipe import Recipe, RecipeError


_PROVENANCE_KEYS = {
    "SOL_ENGINE_PLAN_FINGERPRINT",
    "SOL_ENGINE_EXECUTION_FINGERPRINT",
    "SOL_ENGINE_RECIPE_ID",
}


def _root(raw: str | None) -> Path:
    return Path(raw).resolve() if raw else default_repo_root()


def _catalog(extra_paths: list[str]) -> Catalog:
    catalog = builtin_catalog()
    for path in extra_paths:
        catalog = catalog.merge(Catalog.from_toml(path))
    return catalog


def _list_entries(kind: str, catalog) -> int:
    for entry in catalog.entries(kind):
        detail = entry.get("profile", entry.get("kind", ""))
        print(f"{entry.id:24} {str(detail):32} {entry.provider.canonical}")
    return 0


def _resolve(recipe_path: str, repo_root: str | None, catalog):
    recipe = Recipe.from_toml(recipe_path)
    return resolve_recipe(recipe, catalog=catalog, repo_root=_root(repo_root))


def _execution_metadata(plan, raw_overrides: list[str]) -> tuple[dict[str, str], str]:
    overrides: dict[str, str] = {}
    for raw in raw_overrides:
        if "=" not in raw:
            raise RecipeError(f"--set expects KEY=VALUE, got: {raw}")
        key, value = raw.split("=", 1)
        if not key:
            raise RecipeError(f"--set key cannot be empty: {raw}")
        if key in _PROVENANCE_KEYS:
            raise RecipeError(f"--set cannot override provenance key {key}")
        overrides[key] = value
    payload = {
        "plan_fingerprint": plan.fingerprint,
        "overrides": dict(sorted(overrides.items())),
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return overrides, fingerprint


def _doctor(repo_root: str | None, catalog) -> int:
    root = _root(repo_root)
    failures: list[str] = []
    for entry in catalog.entries("models"):
        profile = (root / str(entry.get("profile", ""))).resolve()
        try:
            profile.relative_to(root)
        except ValueError:
            failures.append(f"model {entry.id}: profile escapes repository: {profile}")
            continue
        if not profile.is_file():
            failures.append(f"model {entry.id}: missing profile {profile}")
            continue
        try:
            profile_data = _toml.load(profile)
            if str(profile_data.get("id", "")) != entry.id:
                failures.append(
                    f"model {entry.id}: profile id {profile_data.get('id')!r} does not match"
                )
        except Exception as exc:
            failures.append(f"model {entry.id}: cannot read profile {profile}: {exc}")
    recipe_paths = sorted((root / "recipes").glob("*/*.toml"))
    for path in recipe_paths:
        try:
            recipe = Recipe.from_toml(path)
            catalog.require("models", recipe.model)
            launch = (root / recipe.launch_config).resolve()
            launch.relative_to(root)
            if not launch.is_file():
                raise ValueError(f"missing launch_config {launch}")
            for request in recipe.optimizations:
                entry = catalog.require("optimizations", request.id)
                if entry.provider != request.provider:
                    raise ValueError(
                        f"provider mismatch for {request.id!r}: catalog pins "
                        f"{entry.provider.canonical!r}, recipe pins "
                        f"{request.provider.canonical!r}"
                    )
        except Exception as exc:
            failures.append(f"recipe {path}: {exc}")
    print(f"catalog: {len(catalog.entries('models'))} models, "
          f"{len(catalog.entries('optimizations'))} optimizations")
    print(f"recipes: {len(recipe_paths)} parsed")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("status: metadata healthy; providers remain unloaded")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", help="Sol-Engine checkout root")
    parser.add_argument(
        "--catalog",
        action="append",
        default=[],
        metavar="PATH",
        help="merge a scoped extension catalog; repeatable, collisions are errors",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("models", help="list model metadata without importing model code")
    sub.add_parser(
        "optimizations", help="list optimization metadata without importing providers"
    )
    sub.add_parser("doctor", help="validate catalog/profile/recipe metadata")

    plan = sub.add_parser("plan", help="resolve and validate a release recipe")
    plan.add_argument("recipe")
    plan.add_argument("--json", action="store_true", help="print the resolved plan as JSON")

    run = sub.add_parser("run", help="validate a recipe, then delegate to the existing launcher")
    run.add_argument("recipe")
    run.add_argument("--print", dest="print_only", action="store_true")
    run.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog = _catalog(args.catalog)
        if args.command == "models":
            return _list_entries("models", catalog)
        if args.command == "optimizations":
            return _list_entries("optimizations", catalog)
        if args.command == "doctor":
            return _doctor(args.repo_root, catalog)

        plan = _resolve(args.recipe, args.repo_root, catalog)
        if args.command == "plan":
            if args.json:
                print(plan.to_json())
            else:
                print(f"recipe      : {plan.recipe_id}")
                print(f"model       : {plan.model_id} ({plan.model_spec})")
                print(f"capabilities: {', '.join(plan.capabilities)}")
                print(f"transforms  : {', '.join(plan.transform_order) or '-'}")
                print(f"techniques  : {', '.join(plan.technique_order) or '-'}")
                print(f"launch      : {plan.launch_config}")
                print(f"fingerprint : {plan.fingerprint}")
            return 0

        root = _root(args.repo_root)
        if not plan.runtime_ready:
            raise PlanResolutionError(
                f"model adapter {plan.model_provider!r} can validate recipes but "
                "cannot compile them to runtime config; implement render_runtime_env"
            )
        overrides, execution_fingerprint = _execution_metadata(plan, args.set)
        command = [
            sys.executable,
            str(root / "scripts" / "run.py"),
            str(root / plan.launch_config),
        ]
        if args.print_only:
            command.append("--print")
        for key, value in sorted(plan.runtime_env.items()):
            command.extend(["--set", f"{key}={value}"])
        for key, value in sorted(overrides.items()):
            command.extend(["--set", f"{key}={value}"])
        provenance = {
            "SOL_ENGINE_PLAN_FINGERPRINT": plan.fingerprint,
            "SOL_ENGINE_EXECUTION_FINGERPRINT": execution_fingerprint,
            "SOL_ENGINE_RECIPE_ID": plan.recipe_id,
        }
        for key, value in provenance.items():
            command.extend(["--set", f"{key}={value}"])
        print(f"validated plan: {plan.fingerprint}", flush=True)
        print(f"execution     : {execution_fingerprint}", flush=True)
        return subprocess.run(command, cwd=root).returncode
    except (CatalogError, RecipeError, PlanResolutionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
