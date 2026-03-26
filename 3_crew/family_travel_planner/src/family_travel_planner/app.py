#!/usr/bin/env python
from __future__ import annotations

import os
import socket
from datetime import datetime
from pathlib import Path
from typing import List

import gradio as gr
from family_travel_planner.crew import FamilyTravelPlanner


TRANSPORT_MODES = ["car", "train", "air"]
PACE_CHOICES = ["relaxed", "balanced", "packed"]
AMENITY_CHOICES = ["kitchen", "parking", "washer", "crib", "quiet area", "near park", "near public transport"]


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
    project_root = Path(__file__).resolve().parents[2]
    repo_root = project_root.parents[1]
    _load_env_file(repo_root / ".env")
    _load_env_file(project_root / ".env")


def _parse_kids_ages(s: str) -> List[int]:
    ages: List[int] = []
    for part in s.split(","):
        p = part.strip()
        if not p:
            continue
        ages.append(int(p))
    return ages


def _format_markdown(p) -> str:
    # Gradio Markdown follows common Markdown rules; `~~text~~` renders as strikethrough.
    # We sanitize common strikethrough markers to avoid confusing UI rendering.
    def _sanitize(s: str) -> str:
        return (
            s.replace("~~", "~\u200b~")
            .replace("<s>", "&lt;s&gt;")
            .replace("</s>", "&lt;/s&gt;")
            .replace("<del>", "&lt;del&gt;")
            .replace("</del>", "&lt;/del&gt;")
        )

    lines: List[str] = []
    lines.append(_sanitize(f"# Family Trip Itinerary: {p.destination}"))
    lines.append(_sanitize(f"Dates: {p.start_date} to {p.end_date} ({p.n_days} days)"))
    lines.append(
        _sanitize(
            f"Group: {p.adults_count} adults + {p.kids_count} kids (ages: {', '.join(str(a) for a in p.kids_ages)})"
        )
    )
    lines.append("")
    lines.append(_sanitize(f"Origin: {p.origin}"))
    if getattr(p, "transport_modes", None):
        lines.append(_sanitize(f"Transport modes: {', '.join(p.transport_modes)}"))
    lines.append("")

    if getattr(p, "travel_options", None):
        lines.append("## Travel options (origin → destination)")
        for opt in p.travel_options:
            lines.append(_sanitize(f"- {opt}"))
        lines.append("")

    lines.append("## Top Airbnb options")
    for opt in p.top_airbnb_options:
        lines.append(_sanitize(f"- **{opt.name}**: {opt.link}"))
        lines.append(_sanitize(f"  - {opt.why_fit}"))
        if opt.bedrooms:
            lines.append(_sanitize(f"  - Bedrooms/Sleep: {opt.bedrooms}"))
        if opt.key_amenities:
            lines.append(_sanitize(f"  - Amenities: {opt.key_amenities}"))
    lines.append("")

    lines.append("## Nearby places")
    for pl in p.nearby_places:
        lines.append(_sanitize(f"- **{pl.name}** ({pl.category}) - Best for: {pl.best_for_ages}"))
        if pl.link:
            lines.append(_sanitize(f"  - {pl.link}"))
        lines.append(_sanitize(f"  - {pl.why_good_for_kids}"))
    lines.append("")

    lines.append("## Day-by-day plan")
    for day in p.daily_plans:
        lines.append(_sanitize(f"### Day {day.day_number} ({day.date})"))
        lines.append(_sanitize(f"- Morning: {day.morning}"))
        lines.append(_sanitize(f"- Midday break: {day.midday_break}"))
        lines.append(_sanitize(f"- Afternoon: {day.afternoon}"))
        lines.append(_sanitize(f"- Evening: {day.evening}"))
        lines.append(_sanitize(f"- Rain backup: {day.rainy_day_backup}"))
        if getattr(day, "distance_notes", None):
            lines.append(_sanitize(f"- Distances: {day.distance_notes}"))
        lines.append("")

    if getattr(p, "packing_list", None):
        lines.append("## Packing list")
        for item in p.packing_list:
            lines.append(_sanitize(f"- {item}"))
        lines.append("")

    if getattr(p, "travel_tips", None):
        lines.append("## Travel tips")
        for t in p.travel_tips:
            lines.append(_sanitize(f"- {t}"))
        lines.append("")

    return "\n".join(lines).strip()


def plan_trip(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    adults: int,
    kids: int,
    transport_modes: list[str],
    family_preferences: str,
    pace_preference: str,
    budget_per_night_gbp,
    must_have_amenities: list[str],
    kid_age_1: str | None,
    kid_age_2: str | None,
    kid_age_3: str | None,
    kid_age_4: str | None,
    kid_age_5: str | None,
    kid_age_6: str | None,
) -> str:
    _load_env()

    adults_i = int(adults)
    kids_i = int(kids)

    start_s = start_date.strip()
    end_s = end_date.strip()

    sd = datetime.strptime(start_s, "%Y-%m-%d").date()
    ed = datetime.strptime(end_s, "%Y-%m-%d").date()
    if ed < sd:
        raise ValueError("end_date must be on or after start_date")

    n_days = (ed - sd).days + 1

    # Collect kid ages only for the number of kids selected
    raw_ages = [kid_age_1, kid_age_2, kid_age_3, kid_age_4, kid_age_5, kid_age_6][:kids_i]
    ages: list[int] = []
    for a in raw_ages:
        if a is None or str(a).strip() == "":
            continue
        ages.append(int(a))
    if kids_i and len(ages) != kids_i:
        raise ValueError("Please select an age for each kid.")

    dest_norm = destination.strip().lower()
    if not dest_norm:
        raise ValueError("Destination is required.")
    # UK-only restriction (free text): require 'UK' or 'United Kingdom' somewhere in destination.
    if "uk" not in dest_norm and "united kingdom" not in dest_norm:
        raise ValueError("Destination must be in the UK. Example: 'Edinburgh, UK'.")

    modes = [m for m in (transport_modes or []) if m in TRANSPORT_MODES]
    if not modes:
        raise ValueError("Select at least one transport mode (car/train/air).")

    budget_val = ""
    if budget_per_night_gbp is not None and str(budget_per_night_gbp).strip() != "":
        try:
            budget_val = str(int(float(budget_per_night_gbp)))
        except Exception:
            budget_val = str(budget_per_night_gbp).strip()

    inputs = {
        "origin": origin.strip(),
        "destination": destination,
        "start_date": str(sd),
        "end_date": str(ed),
        "adults_count": adults_i,
        "kids_count": kids_i,
        "kids_ages": ages,
        "n_days": n_days,
        "transport_modes": ", ".join(modes),
        "family_preferences": (family_preferences or "").strip(),
        "pace_preference": pace_preference or "balanced",
        "budget_per_night_gbp": budget_val,
        "must_have_amenities": ", ".join(must_have_amenities or []),
    }

    res = FamilyTravelPlanner().crew().kickoff(inputs=inputs)
    p = res.pydantic
    if p is None:
        raise RuntimeError("Planner did not return structured itinerary output (pydantic).")

    md = _format_markdown(p)

    # Also save to disk for convenience
    project_root = Path(__file__).resolve().parents[2]
    outputs_dir = project_root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "itinerary.md").write_text(md, encoding="utf-8")

    # Keep JSON on disk for debugging/pipeline usage, but don't show in UI
    try:
        js = p.model_dump_json(indent=2) if hasattr(p, "model_dump_json") else p.json(indent=2)
        (outputs_dir / "itinerary.json").write_text(js, encoding="utf-8")
    except Exception:
        pass

    return md


def _update_kid_age_visibility(kids: int):
    k = int(kids or 0)
    vis = [k >= i for i in range(1, 7)]
    return [gr.update(visible=v) for v in vis]


def main() -> None:
    with gr.Blocks(title="Family Travel Planner (Kids-friendly)") as demo:
        gr.Markdown(
            "## Family Travel Planner\n"
            "Provide destination + dates + family counts. Generates a kid-friendly itinerary + Airbnb shortlist."
        )

        with gr.Row():
            origin = gr.Textbox(label="Trip origin (city/area)", value="London, UK")
            destination = gr.Textbox(label="Destination (UK only)", value="Edinburgh, UK")

        with gr.Row():
            start_date = gr.Textbox(label="Start date (YYYY-MM-DD)", value="2026-04-10")
            end_date = gr.Textbox(label="End date (YYYY-MM-DD)", value="2026-04-13")

        with gr.Row():
            adults = gr.Number(label="Adults", value=2, precision=0)
            kids = gr.Number(label="Kids", value=2, precision=0)

        transport_modes = gr.CheckboxGroup(
            label="Travel modes (origin → destination)",
            choices=TRANSPORT_MODES,
            value=["train"],
        )

        with gr.Accordion("Family profile (optional but recommended)", open=False):
            family_preferences = gr.Textbox(
                label="Preferences / constraints",
                lines=3,
                placeholder="Example: stroller-friendly, nap at 1pm, vegetarian food, avoid long walks, loves animals",
            )
            with gr.Row():
                pace_preference = gr.Dropdown(label="Pace", choices=PACE_CHOICES, value="balanced")
                budget_per_night_gbp = gr.Number(label="Budget per night (GBP)", precision=0)
            must_have_amenities = gr.CheckboxGroup(
                label="Must-have amenities",
                choices=AMENITY_CHOICES,
                value=[],
            )

        gr.Markdown("### Kids ages (select after setting number of kids)")
        with gr.Row():
            kid_age_1 = gr.Dropdown(label="Kid 1 age", choices=[str(i) for i in range(0, 18)], visible=True)
            kid_age_2 = gr.Dropdown(label="Kid 2 age", choices=[str(i) for i in range(0, 18)], visible=True)
            kid_age_3 = gr.Dropdown(label="Kid 3 age", choices=[str(i) for i in range(0, 18)], visible=False)
        with gr.Row():
            kid_age_4 = gr.Dropdown(label="Kid 4 age", choices=[str(i) for i in range(0, 18)], visible=False)
            kid_age_5 = gr.Dropdown(label="Kid 5 age", choices=[str(i) for i in range(0, 18)], visible=False)
            kid_age_6 = gr.Dropdown(label="Kid 6 age", choices=[str(i) for i in range(0, 18)], visible=False)

        kids.change(
            fn=_update_kid_age_visibility,
            inputs=[kids],
            outputs=[kid_age_1, kid_age_2, kid_age_3, kid_age_4, kid_age_5, kid_age_6],
        )

        run_btn = gr.Button("Generate plan", variant="primary")

        out_md = gr.Markdown(label="Itinerary")

        run_btn.click(
            fn=plan_trip,
            inputs=[
                origin,
                destination,
                start_date,
                end_date,
                adults,
                kids,
                transport_modes,
                family_preferences,
                pace_preference,
                budget_per_night_gbp,
                must_have_amenities,
                kid_age_1,
                kid_age_2,
                kid_age_3,
                kid_age_4,
                kid_age_5,
                kid_age_6,
            ],
            outputs=[out_md],
        )

    # Queue helps avoid issues when multiple requests come in
    demo.queue()
    preferred = int(os.environ.get("GRADIO_SERVER_PORT", "").strip() or "7860")
    server_name = "127.0.0.1"

    # Find a free port (preferred..preferred+24)
    actual_port = None
    for port in range(preferred, preferred + 25):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((server_name, port))
            actual_port = port
            break
        except OSError:
            continue
    if actual_port is None:
        raise OSError(f"No free port found in range {preferred}-{preferred + 24}.")

    url = f"http://{server_name}:{actual_port}"
    print(f"Starting FamilyTravelPlanner UI on {url}", flush=True)
    demo.launch(server_name=server_name, server_port=actual_port)


if __name__ == "__main__":
    main()

