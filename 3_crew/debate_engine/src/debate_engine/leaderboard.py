"""Gradio leaderboard for debate_engine results (reads outputs/debate_results.json)."""

from __future__ import annotations

import html
import json
import os
import socket
from pathlib import Path
from typing import Any

# Theme: courtroom / legal — deep slate, amber gold, prosecution crimson, defense sapphire
# High-contrast text so labels / table stay readable on dark fills (Gradio + embedded HTML).
_LEADERBOARD_CSS = """
:root {
  --bg-deep: #0c1222;
  --bg-card: #151d32;
  --border: #3d4f7a;
  --text: #f8fafc;
  --muted: #cbd5e1;
  --gold: #fcd34d;
  --gold-dim: #d97706;
  --pros: #fca5a5;
  --pros-bg: rgba(220, 38, 38, 0.18);
  --def: #93c5fd;
  --def-bg: rgba(37, 99, 235, 0.2);
}
.leader-root {
  font-family: "DM Sans", "Segoe UI", system-ui, sans-serif;
  color: var(--text);
  max-width: 1200px;
  margin: 0 auto;
}
.leader-header {
  text-align: center;
  margin-bottom: 1.25rem;
  padding: 1rem 1.25rem;
  background: linear-gradient(145deg, #1a2540 0%, #121a2e 100%);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}
.leader-header h1 {
  margin: 0 0 0.35rem 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: #fde047;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.85);
}
.leader-header p { margin: 0; color: var(--muted); font-size: 0.95rem; }
.stats-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
  margin-bottom: 1rem;
}
.stat-pill {
  padding: 0.5rem 1rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text);
}
.stat-pill.pros { color: #fecaca; border-color: rgba(248, 113, 113, 0.45); }
.stat-pill.def { color: #bfdbfe; border-color: rgba(96, 165, 250, 0.45); }
.stat-pill.neutral { color: #fde68a; border-color: rgba(252, 211, 77, 0.45); }
table.leader {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--border);
  font-size: 0.88rem;
  color: var(--text);
}
table.leader thead th {
  background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
  color: #fde047;
  padding: 0.65rem 0.5rem;
  text-align: left;
  font-weight: 600;
  letter-spacing: 0.02em;
  border-bottom: 2px solid var(--gold-dim);
}
table.leader tbody td {
  padding: 0.55rem 0.5rem;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
  color: #e2e8f0;
}
table.leader tbody tr:nth-child(even) { background: rgba(15, 23, 42, 0.55); }
table.leader tbody tr:hover { background: rgba(30, 41, 59, 0.75); }
.rank {
  font-weight: 700;
  color: #94a3b8;
  width: 2.5rem;
  text-align: center;
}
.cell-pros {
  color: #fecaca;
  background: var(--pros-bg);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.cell-def {
  color: #bfdbfe;
  background: var(--def-bg);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.cell-conf {
  color: #e2e8f0;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.badge {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.badge-prosecution {
  background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%);
  color: #fecaca;
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.3);
}
.badge-defense {
  background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 100%);
  color: #dbeafe;
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.35);
}
.motion { color: #f1f5f9; max-width: 220px; }
.ts { color: #cbd5e1; font-size: 0.8rem; white-space: nowrap; }
.empty {
  text-align: center;
  padding: 2rem;
  color: #cbd5e1;
  border: 1px dashed var(--border);
  border-radius: 12px;
}
.section-title {
  color: #fde047;
  font-size: 1.05rem;
  font-weight: 700;
  margin: 1.25rem 0 0.6rem 0;
  letter-spacing: 0.02em;
}
table.models {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--border);
  font-size: 0.82rem;
  margin-bottom: 0.5rem;
}
table.models thead th {
  background: linear-gradient(180deg, #1e3a5f 0%, #0f172a 100%);
  color: #93c5fd;
  padding: 0.55rem 0.45rem;
  text-align: left;
  font-weight: 600;
}
table.models tbody td {
  padding: 0.5rem 0.45rem;
  border-bottom: 1px solid var(--border);
  color: #e2e8f0;
  vertical-align: middle;
}
table.models tbody tr:nth-child(even) { background: rgba(15, 23, 42, 0.5); }
table.models tbody tr:hover { background: rgba(30, 58, 95, 0.35); }
.cell-model {
  font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
  font-size: 0.78rem;
  color: #c4b5fd;
  max-width: 200px;
  word-break: break-word;
}
.cell-metric { font-variant-numeric: tabular-nums; }
"""

# Gradio shell: dark page + light text (fixes invisible labels / markdown on dark block fill)
_GRADIO_SHELL_CSS = """
.gradio-container {
  color: #f1f5f9 !important;
}
label span, .label-wrap label, label {
  color: #e2e8f0 !important;
}
.prose, .prose p, .prose li, .prose h1, .prose h2, .prose h3, .prose h4 {
  color: #f1f5f9 !important;
}
input, textarea, select {
  color: #f8fafc !important;
}
"""

_CSS = _LEADERBOARD_CSS + "\n" + _GRADIO_SHELL_CSS


def _default_results_path() -> Path:
    """Project root: debate_engine/ (parent of src/)."""
    return Path(__file__).resolve().parent.parent.parent / "outputs" / "debate_results.json"


def load_debates(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _fmt_num(x: Any) -> str:
    if isinstance(x, (int, float)):
        if isinstance(x, float) and x == int(x):
            return str(int(x))
        return f"{x:.2f}".rstrip("0").rstrip(".")
    return str(x)


def _side_total(scores: dict[str, Any], side: str) -> float:
    try:
        return float((scores.get(side) or {}).get("total", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def compute_model_stats(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Per LLM (advocate) model: how often it argued, wins, avg judge total for its side,
    and role-specific averages when it was prosecutor vs defense.
    """
    acc: dict[str, dict[str, Any]] = {}

    def ensure(name: str) -> dict[str, Any]:
        if name not in acc:
            acc[name] = {
                "debates": 0,
                "wins": 0,
                "score_sum": 0.0,
                "prosecution_n": 0,
                "prosecution_sum": 0.0,
                "defense_n": 0,
                "defense_sum": 0.0,
            }
        return acc[name]

    for r in records:
        models = r.get("models") or {}
        pro_m = str(models.get("prosecutor") or models.get("prosecution") or "").strip()
        def_m = str(models.get("defense") or models.get("defender") or "").strip()
        winner = str(r.get("winner") or "").lower()
        scores = r.get("scores") or {}

        if pro_m:
            d = ensure(pro_m)
            d["debates"] += 1
            st = _side_total(scores, "prosecution")
            d["score_sum"] += st
            d["prosecution_n"] += 1
            d["prosecution_sum"] += st
            if winner == "prosecution":
                d["wins"] += 1

        if def_m:
            d = ensure(def_m)
            d["debates"] += 1
            st = _side_total(scores, "defense")
            d["score_sum"] += st
            d["defense_n"] += 1
            d["defense_sum"] += st
            if winner == "defense":
                d["wins"] += 1

    out: list[dict[str, Any]] = []
    for model, d in acc.items():
        deb = int(d["debates"])
        if deb == 0:
            continue
        pn = int(d["prosecution_n"])
        dn = int(d["defense_n"])
        out.append({
            "model": model,
            "debates": deb,
            "wins": int(d["wins"]),
            "win_rate": d["wins"] / deb,
            "avg_score": d["score_sum"] / deb,
            "avg_prosecution": (d["prosecution_sum"] / pn) if pn else None,
            "avg_defense": (d["defense_sum"] / dn) if dn else None,
        })

    out.sort(
        key=lambda x: (x["win_rate"], x["avg_score"], x["debates"]),
        reverse=True,
    )
    return out


def _format_optional_avg(x: float | None) -> str:
    return _fmt_num(x) if x is not None else "—"


def _enriched(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in records:
        sp = r.get("scores", {}).get("prosecution", {}).get("total", 0)
        sd = r.get("scores", {}).get("defense", {}).get("total", 0)
        try:
            spf = float(sp)
            sdf = float(sd)
        except (TypeError, ValueError):
            spf = sdf = 0.0
        out.append({
            **r,
            "_combined": spf + sdf,
            "_margin": spf - sdf,
            "_pro_total": spf,
            "_def_total": sdf,
        })
    return out


def _sort_records(records: list[dict[str, Any]], sort_mode: str) -> list[dict[str, Any]]:
    enriched = _enriched(records)
    if sort_mode == "Newest first":
        return sorted(enriched, key=lambda x: x.get("timestamp", ""), reverse=True)
    if sort_mode == "Highest combined score":
        return sorted(enriched, key=lambda x: x["_combined"], reverse=True)
    if sort_mode == "Largest prosecution margin":
        return sorted(enriched, key=lambda x: x["_margin"], reverse=True)
    if sort_mode == "Largest defense margin":
        return sorted(enriched, key=lambda x: -x["_margin"], reverse=True)
    return enriched


def _build_model_rankings_html(records: list[dict[str, Any]]) -> str:
    stats = compute_model_stats(records)
    if not stats:
        return (
            '<h2 class="section-title">Model rankings</h2>'
            '<p class="empty">No advocate model data yet. Each debate needs a '
            "<code>models</code> object (prosecutor / defense) in debate_results.json.</p>"
        )

    body: list[str] = []
    for i, s in enumerate(stats, start=1):
        m = html.escape(str(s["model"]))
        wr_pct = float(s["win_rate"]) * 100.0
        body.append(f"""
<tr>
  <td class="rank">{i}</td>
  <td class="cell-model">{m}</td>
  <td class="cell-metric">{s["debates"]}</td>
  <td class="cell-metric">{s["wins"]}</td>
  <td class="cell-metric">{wr_pct:.0f}%</td>
  <td class="cell-metric">{_fmt_num(s["avg_score"])}</td>
  <td class="cell-metric">{_format_optional_avg(s["avg_prosecution"])}</td>
  <td class="cell-metric">{_format_optional_avg(s["avg_defense"])}</td>
</tr>""")

    return f"""
<h2 class="section-title">Model rankings (advocate performance)</h2>
<p style="color:#cbd5e1;font-size:0.85rem;margin:0 0 0.75rem 0;">
  Sorted by win rate, then average judge score for that model&rsquo;s side when it argued.
  <strong>Avg Σ</strong> is the mean of prosecution or defense totals across that model&rsquo;s appearances.
</p>
<table class="models">
  <thead>
    <tr>
      <th>#</th>
      <th>Model</th>
      <th>Debates</th>
      <th>Wins</th>
      <th>Win %</th>
      <th>Avg Σ</th>
      <th>Avg Σ (Pro)</th>
      <th>Avg Σ (Def)</th>
    </tr>
  </thead>
  <tbody>
    {"".join(body)}
  </tbody>
</table>
"""


def build_html(records: list[dict[str, Any]], sort_mode: str) -> str:
    rows = _sort_records(records, sort_mode)
    pros_wins = sum(1 for r in records if r.get("winner") == "prosecution")
    def_wins = sum(1 for r in records if r.get("winner") == "defense")
    n = len(records)

    header = f"""
<div class="leader-root">
  <div class="leader-header">
    <h1>Debate Engine Leaderboard</h1>
    <p>Judged debates &mdash; model rankings and scores from debate_results.json</p>
  </div>
  <div class="stats-row">
    <span class="stat-pill neutral">Total debates: {n}</span>
    <span class="stat-pill pros">Prosecution wins: {pros_wins}</span>
    <span class="stat-pill def">Defense wins: {def_wins}</span>
  </div>
"""

    if n == 0:
        return (
            f"<style>{_LEADERBOARD_CSS}</style>"
            + header
            + '<p class="empty">No debate records found. Run the crew to populate outputs/debate_results.json.</p></div>'
        )

    model_block = _build_model_rankings_html(records)

    body_rows = []
    for i, r in enumerate(rows, start=1):
        winner = r.get("winner", "")
        badge = (
            '<span class="badge badge-prosecution">Prosecution</span>'
            if winner == "prosecution"
            else '<span class="badge badge-defense">Defense</span>'
        )
        ts = str(r.get("timestamp", ""))[:19].replace("T", " ")
        motion = html.escape(str(r.get("motion", "—")))
        sp = r.get("scores", {}).get("prosecution", {})
        sd = r.get("scores", {}).get("defense", {})
        conf = r.get("confidence")
        conf_s = f"{float(conf) * 100:.0f}%" if conf is not None else "—"
        models = r.get("models") or {}
        pro_model = html.escape(
            str(models.get("prosecutor") or models.get("prosecution") or "—")
        )
        def_model = html.escape(
            str(models.get("defense") or models.get("defender") or "—")
        )

        body_rows.append(f"""
<tr>
  <td class="rank">{i}</td>
  <td class="ts">{ts}</td>
  <td class="motion">{motion}</td>
  <td class="cell-model">{pro_model}</td>
  <td class="cell-model">{def_model}</td>
  <td>{badge}</td>
  <td class="cell-pros">{_fmt_num(sp.get("total"))}</td>
  <td class="cell-def">{_fmt_num(sd.get("total"))}</td>
  <td class="cell-conf">{conf_s}</td>
</tr>""")

    table = f"""
<h2 class="section-title">Debate history</h2>
<table class="leader">
  <thead>
    <tr>
      <th>#</th>
      <th>When</th>
      <th>Motion</th>
      <th>Prosecutor model</th>
      <th>Defense model</th>
      <th>Winner</th>
      <th>Prosecution Σ</th>
      <th>Defense Σ</th>
      <th>Confidence</th>
    </tr>
  </thead>
  <tbody>
    {"".join(body_rows)}
  </tbody>
</table>
</div>
"""
    return f"<style>{_LEADERBOARD_CSS}</style>" + header + model_block + table


def _preferred_port(explicit: int | None) -> int:
    env = os.environ.get("GRADIO_SERVER_PORT", "").strip()
    if env:
        return int(env)
    return explicit if explicit is not None else 7860


def _pick_free_port(host: str, preferred: int, span: int = 24) -> int:
    """Bind-test successive ports starting at preferred (default Gradio range 7860+)."""
    for port in range(preferred, preferred + span):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(
        f"No free port in range {preferred}-{preferred + span - 1} on {host}. "
        "Close other apps using those ports or set GRADIO_SERVER_PORT to a free port."
    )


def get_leaderboard_url(
    server_name: str | None = None,
    server_port: int | None = None,
) -> str:
    """
    Base URL for the Gradio leaderboard (same defaults as launch()).
    The running app may use the next free port if this one is busy; check the
    console when starting `uv run debate_leaderboard`.
    """
    host = (
        server_name
        or os.environ.get("GRADIO_SERVER_NAME", "").strip()
        or "127.0.0.1"
    )
    port = _preferred_port(server_port)
    return f"http://{host}:{port}"


def launch(
    results_path: str | None = None,
    server_name: str = "127.0.0.1",
    server_port: int | None = None,
    share: bool = False,
) -> None:
    import gradio as gr

    path = results_path or os.environ.get("DEBATE_RESULTS_JSON", str(_default_results_path()))
    _sort_mode = "Newest first"

    def refresh() -> str:
        data = load_debates(path)
        return build_html(data, _sort_mode)

    theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.amber,
        secondary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.slate,
        font=[gr.themes.GoogleFont("DM Sans"), "ui-sans-serif", "system-ui", "sans-serif"],
    ).set(
        body_background_fill="#0c1222",
        body_text_color="#f1f5f9",
        body_text_color_dark="#f1f5f9",
        body_text_color_subdued="#cbd5e1",
        body_text_color_subdued_dark="#cbd5e1",
        block_background_fill="#151d32",
        block_border_color="#3d4f7a",
        block_label_text_color="#e2e8f0",
        block_label_text_color_dark="#e2e8f0",
        block_title_text_color="#f8fafc",
        block_title_text_color_dark="#f8fafc",
        input_background_fill="#1e293b",
        input_border_color="#475569",
        input_border_color_dark="#475569",
        input_placeholder_color="#94a3b8",
        input_placeholder_color_dark="#94a3b8",
        button_primary_background_fill="#b45309",
        button_primary_background_fill_hover="#d97706",
        button_primary_text_color="#0f172a",
        button_primary_text_color_dark="#0f172a",
    )

    with gr.Blocks(title="Debate Leaderboard") as demo:
        gr.Markdown(
            "### Debate & model leaderboard\n"
            "See **which LLM wins** and average judge scores per model; debate log shows prosecutor vs defense models per round."
        )
        refresh_btn = gr.Button("Refresh", variant="primary")
        html_out = gr.HTML(value=refresh())

        refresh_btn.click(refresh, outputs=html_out)

        demo.load(refresh, outputs=html_out)

    preferred = _preferred_port(server_port)
    actual_port = _pick_free_port(server_name, preferred)
    if actual_port != preferred:
        print(
            f"Port {preferred} in use; starting debate leaderboard on {actual_port} instead.",
            flush=True,
        )

    demo.launch(
        server_name=server_name,
        server_port=actual_port,
        share=share,
        theme=theme,
        css=_CSS,
    )


def main() -> None:
    launch()


if __name__ == "__main__":
    main()
