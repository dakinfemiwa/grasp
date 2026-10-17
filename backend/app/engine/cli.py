"""Generate and validate question instances from the command line.

Usage (from backend/):
  python -m app.engine.cli list
  python -m app.engine.cli generate QUAD-RECT-AREA --count 20 --seed 1 [--scenario SCN-…] [--show] [--save]

--save persists the instances (the catalogue must be seeded first: python -m app.seed).
"""

import argparse
import sys

from app.engine import all_templates, generate, get_template
from app.engine.base import EngineError
from app.engine.scenarios import compatible_scenarios, get_scenario


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # ², × on Windows consoles
    parser = argparse.ArgumentParser(prog="python -m app.engine.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list registered templates")
    gen = sub.add_parser("generate", help="generate and validate instances")
    gen.add_argument("template_id")
    gen.add_argument("--version", type=int, default=None)
    gen.add_argument("--scenario", default=None, help="scenario id; default: picked from each seed")
    gen.add_argument("--count", type=int, default=20)
    gen.add_argument("--seed", type=int, default=1, help="first seed; instances use seed, seed+1, ...")
    gen.add_argument("--show", action="store_true", help="print each prompt and answer")
    gen.add_argument("--save", action="store_true", help="persist instances to the database")
    args = parser.parse_args(argv)

    if args.command == "list":
        for t in all_templates():
            refs = ", ".join(t.spec_refs)
            print(f"{t.id} v{t.version}  [{t.review_status}]  {t.domain}  {t.title}  (spec {refs})")
            for sc in compatible_scenarios(t):
                print(f"    {sc.id} v{sc.version}  [{sc.review_status}]  {sc.title}")
        return 0

    template = get_template(args.template_id, args.version)
    scenario = get_scenario(args.scenario) if args.scenario else None
    failures = 0
    generated = []
    for seed in range(args.seed, args.seed + args.count):
        try:
            q = generate(template, seed, scenario)
        except EngineError as exc:
            failures += 1
            print(f"seed {seed}: INVALID\n{exc}")
            continue
        generated.append(q)
        print(f"seed {seed}: ok  {q.scenario_id}  {len(q.validation)} checks  difficulty {q.difficulty}  {q.parameters}")
        if args.show:
            print(f"  {q.prompt}\n  answer: {q.expected_answer}")

    if args.save:
        from app.db.session import SessionLocal
        from app.services.practice import get_or_create_instance

        with SessionLocal() as db:
            ids = [get_or_create_instance(db, q).id for q in generated]
        print(f"saved instance ids: {ids}")

    print(f"{len(generated)}/{args.count} valid instances of {template.id} v{template.version}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
