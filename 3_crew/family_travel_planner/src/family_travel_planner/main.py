#!/usr/bin/env python
import argparse
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

from family_travel_planner.crew import FamilyTravelPlanner

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def _load_env_file(path: Path) -> None:
    """Minimal .env loader (no dependency on python-dotenv)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        if k and (k not in os.environ or not os.environ.get(k)):
            os.environ[k] = v


def _load_env() -> None:
    # src/family_travel_planner/main.py -> project root: family_travel_planner/
    project_root = Path(__file__).resolve().parents[2]
    repo_root = project_root.parents[1]
    _load_env_file(repo_root / ".env")
    _load_env_file(project_root / ".env")


def _parse_kids_ages(s: str) -> list[int]:
    ages: list[int] = []
    for part in s.split(","):
        p = part.strip()
        if not p:
            continue
        ages.append(int(p))
    return ages

def run():
    """Run the travel planner crew with CLI inputs."""
    _load_env()

    parser = argparse.ArgumentParser(prog="family_travel_planner")
    parser.add_argument("--destination", required=True, type=str, help="City/area to plan the trip for.")
    parser.add_argument("--start-date", required=True, type=str, help="Trip start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", required=True, type=str, help="Trip end date (YYYY-MM-DD).")
    parser.add_argument("--adults", required=True, type=int, help="Number of adults.")
    parser.add_argument("--kids", required=True, type=int, help="Number of kids.")
    parser.add_argument(
        "--kids-ages",
        required=True,
        type=str,
        help="Comma-separated kids ages. Example: 4,7,12",
    )

    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    if end_date < start_date:
        raise ValueError("end-date must be on or after start-date")

    n_days = (end_date - start_date).days + 1
    kids_ages = _parse_kids_ages(args.kids_ages)

    inputs = {
        "destination": args.destination,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "adults_count": args.adults,
        "kids_count": args.kids,
        "kids_ages": kids_ages,
        "n_days": n_days,
    }

    try:
        result = FamilyTravelPlanner().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")

    # Persist output
    project_root = Path(__file__).resolve().parents[2]
    outputs_dir = project_root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    pyd = getattr(result, "pydantic", None)
    if pyd is None:
        print(result.raw)
        return

    json_path = outputs_dir / "itinerary.json"
    if hasattr(pyd, "model_dump_json"):
        json_path.write_text(pyd.model_dump_json(indent=2), encoding="utf-8")
    else:
        json_path.write_text(pyd.json(indent=2), encoding="utf-8")

    # Also generate a quick readable markdown file
    md_path = outputs_dir / "itinerary.md"
    lines: list[str] = []
    lines.append(f"# Family Trip Itinerary: {pyd.destination}")
    lines.append(f"Dates: {pyd.start_date} to {pyd.end_date} ({pyd.n_days} days)")
    lines.append(
        f"Group: {pyd.adults_count} adults + {pyd.kids_count} kids (ages: {', '.join(str(a) for a in pyd.kids_ages)})"
    )
    lines.append("")

    lines.append("## Top Airbnb options")
    for opt in pyd.top_airbnb_options:
        lines.append(f"- **{opt.name}**: {opt.link}")
        lines.append(f"  - {opt.why_fit}")
        if opt.bedrooms:
            lines.append(f"  - Bedrooms/Sleep: {opt.bedrooms}")
        if opt.key_amenities:
            lines.append(f"  - Amenities: {opt.key_amenities}")
    lines.append("")

    lines.append("## Nearby places")
    for pl in pyd.nearby_places:
        lines.append(f"- **{pl.name}** ({pl.category}) - Best for: {pl.best_for_ages}")
        if pl.link:
            lines.append(f"  - Link: {pl.link}")
        lines.append(f"  - {pl.why_good_for_kids}")
    lines.append("")

    lines.append("## Day-by-day plan")
    for day in pyd.daily_plans:
        lines.append(f"### Day {day.day_number} ({day.date})")
        lines.append(f"- Morning: {day.morning}")
        lines.append(f"- Midday break: {day.midday_break}")
        lines.append(f"- Afternoon: {day.afternoon}")
        lines.append(f"- Evening: {day.evening}")
        lines.append(f"- Rain backup: {day.rainy_day_backup}")
        lines.append("")

    if pyd.packing_list:
        lines.append("## Packing list")
        for item in pyd.packing_list:
            lines.append(f"- {item}")
        lines.append("")

    if pyd.travel_tips:
        lines.append("## Travel tips")
        for t in pyd.travel_tips:
            lines.append(f"- {t}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year)
    }
    try:
        FamilyTravelPlanner().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        FamilyTravelPlanner().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }

    try:
        FamilyTravelPlanner().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

def run_with_trigger():
    """
    Run the crew with trigger payload.
    """
    import json

    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")

    inputs = {
        "crewai_trigger_payload": trigger_payload,
        "topic": "",
        "current_year": ""
    }

    try:
        result = FamilyTravelPlanner().crew().kickoff(inputs=inputs)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the crew with trigger: {e}")
