#!/usr/bin/env python3
"""
Cross-Domain Collision Detector
Scrapuje RSS feedy, analyzuje průniky mezi doménami pomocí Claude API
a generuje HTML report na GitHub Pages.
"""

import os
import json
import yaml
import feedparser
import anthropic
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
import time
import re

# ── Config ─────────────────────────────────────────────────────────────────
FEEDS_FILE   = Path("feeds.yaml")
OUTPUT_DIR   = Path("docs")
OUTPUT_FILE  = OUTPUT_DIR / "index.html"
MAX_ARTICLES = 6     # max článků na feed
MAX_CHARS    = 400   # max znaků z každého článku pro kontext
COLLISIONS   = 6     # počet kolizí v reportu
MODEL        = "claude-opus-4-5"

# ── RSS Scraper ─────────────────────────────────────────────────────────────
def fetch_feeds(config: dict) -> dict[str, list[dict]]:
    """Stáhne RSS feedy, vrátí dict {domain: [articles]}."""
    by_domain: dict[str, list[dict]] = defaultdict(list)

    for feed_cfg in config["feeds"]:
        url    = feed_cfg["url"]
        domain = feed_cfg["domain"]
        label  = feed_cfg.get("label", url)

        try:
            parsed = feedparser.parse(url)
            entries = parsed.entries[:MAX_ARTICLES]
            if not entries:
                print(f"  ⚠  {label}: prázdný feed")
                continue

            for entry in entries:
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))
                # Strip HTML tags
                summary = re.sub(r"<[^>]+>", " ", summary).strip()
                summary = re.sub(r"\s+", " ", summary)[:MAX_CHARS]
                link    = entry.get("link", "")
                pub     = entry.get("published", "")

                if title:
                    by_domain[domain].append({
                        "title":   title,
                        "summary": summary,
                        "link":    link,
                        "pub":     pub,
                        "source":  label,
                    })

            print(f"  ✓  {label}: {len(entries)} článků [{domain}]")
            time.sleep(0.3)  # politeness delay

        except Exception as e:
            print(f"  ✗  {label}: {e}")

    return dict(by_domain)


# ── Claude Analyzer ─────────────────────────────────────────────────────────
def build_prompt(articles_by_domain: dict[str, list[dict]], n_collisions: int) -> str:
    lines = []
    for domain, articles in articles_by_domain.items():
        lines.append(f"\n### DOMÉNA: {domain.upper()} ({len(articles)} článků)")
        for a in articles:
            lines.append(f"- [{a['source']}] {a['title']}")
            if a["summary"]:
                lines.append(f"  → {a['summary'][:200]}")

    content_block = "\n".join(lines)

    return f"""Jsi expert na cross-domain pattern matching. Analyzuješ aktuální zpravodajství z různých domén a hledáš neočekávaná spojení a kolize.

AKTUÁLNÍ OBSAH Z RSS FEEDŮ:
{content_block}

---

ÚKOL: Najdi {n_collisions} NEOBVYKLÝCH KOLIZÍ — momentů, kdy se jevy z různých domén začínají překrývat nebo zesilovat. Vycházej VÝHRADNĚ z výše uvedených článků — každá kolize musí být ukotvená v konkrétním obsahu, který jsi četl.

Vrať POUZE validní JSON (bez markdown, bez backticks, bez komentářů):
{{
  "collisions": [
    {{
      "title": "Provokativní název kolize (max 12 slov)",
      "domains": ["Doména 1", "Doména 2", "Doména 3"],
      "tension_score": 87,
      "core_pattern": "Co se skutečně děje — jaký hlubší vzorec propojuje tyto domény? (2-3 věty)",
      "collision_mechanism": "Jak přesně se domény střetávají? Jaký je mechanismus průniku? (2-3 věty)",
      "evidence": ["Konkrétní článek nebo signál z feedů #1", "Konkrétní článek nebo signál #2", "Konkrétní článek nebo signál #3"],
      "episode_hook": "Provokativní otázka nebo teze pro podcastovou epizodu. (1-2 věty)"
    }}
  ],
  "meta": {{
    "domains_analyzed": {len(articles_by_domain)},
    "articles_analyzed": {sum(len(v) for v in articles_by_domain.values())},
    "strongest_signal": "Jedna věta o nejsilnějším trendu, který z dat vyplývá"
  }}
}}

PRAVIDLA:
- tension_score 0–100: vyšší = neočekávanější, aktuálnější, napínavější spojení
- evidence musí odkazovat na konkrétní titulky nebo zdroje z dat výše
- Hledej trojúhelníkové/čtyřúhelníkové kolize (3-4 domény)
- Vyhýbej se klišé (AI bere práci, klimatická krize obecně apod.)
- episode_hook musí být tak silný, že posluchač řekne "to chci slyšet"
"""


def analyze_collisions(articles_by_domain: dict, client: anthropic.Anthropic) -> dict:
    """Pošle obsah feedů Claude a vrátí JSON s kolizemi."""
    prompt = build_prompt(articles_by_domain, COLLISIONS)

    print(f"\n→ Posílám {sum(len(v) for v in articles_by_domain.values())} článků z {len(articles_by_domain)} domén Claudovi...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip possible markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ── HTML Generator ──────────────────────────────────────────────────────────
def render_html(data: dict, articles_by_domain: dict, generated_at: datetime) -> str:
    collisions = data.get("collisions", [])
    meta       = data.get("meta", {})
    ts_str     = generated_at.strftime("%-d. %-m. %Y, %H:%M UTC")

    # Domain coverage sidebar data
    domain_counts = {d: len(a) for d, a in articles_by_domain.items()}

    cards_html = ""
    for i, c in enumerate(collisions):
        domains  = c.get("domains", [])[:3]
        evidence = c.get("evidence", [])
        score    = c.get("tension_score", 0)
        score_color = "#e8ff00" if score >= 75 else "#ff9500" if score >= 50 else "#888"

        dom_badges = "".join(
            f'<span class="db db{j+1}">{d}</span>' for j, d in enumerate(domains)
        )
        ev_items = "".join(f'<li>{e}</li>' for e in evidence)

        cards_html += f"""
        <article class="card" style="animation-delay:{i*0.07}s">
          <div class="card-top">
            <div class="card-left">
              <div class="idx">0{i+1}</div>
              <div>
                <div class="domains">{dom_badges}</div>
                <h2>{c.get('title','')}</h2>
              </div>
            </div>
            <div class="score-wrap">
              <div class="score-label">Napětí</div>
              <div class="score-val" style="color:{score_color}">{score}</div>
            </div>
          </div>
          <div class="card-body">
            <div class="block">
              <div class="blabel">Hlubší vzorec</div>
              <p>{c.get('core_pattern','')}</p>
            </div>
            <div class="block">
              <div class="blabel">Mechanismus průniku</div>
              <p>{c.get('collision_mechanism','')}</p>
            </div>
            <div class="block">
              <div class="blabel">Ukotvení v datech</div>
              <ul class="evidence">{ev_items}</ul>
            </div>
            <div class="hook">
              <div class="blabel hook-label">↯ Návrh epizody</div>
              <p class="hook-text">{c.get('episode_hook','')}</p>
            </div>
          </div>
        </article>"""

    domain_rows = "".join(
        f'<div class="dr"><span class="dn">{d}</span><span class="dc">{n}</span></div>'
        for d, n in sorted(domain_counts.items(), key=lambda x: -x[1])
    )

    strongest = meta.get("strongest_signal", "")

    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Collision Detector — {ts_str}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
:root{{
  --bg:#0a0a08;--surface:#111110;--border:#222220;
  --accent:#e8ff00;--accent2:#ff4d1c;--text:#e8e6df;--muted:#666660;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'Space Mono',monospace;min-height:100vh}}
body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(232,255,0,.03) 1px,transparent 1px),linear-gradient(90deg,rgba(232,255,0,.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0}}
.wrap{{max-width:960px;margin:0 auto;padding:40px 24px 80px;position:relative;z-index:1}}
header{{margin-bottom:40px;padding-bottom:28px;border-bottom:1px solid var(--border)}}
.tag{{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);margin-bottom:10px;display:flex;align-items:center;gap:8px}}
.tag::before{{content:'';width:20px;height:1px;background:var(--accent)}}
h1{{font-family:'Syne',sans-serif;font-weight:800;font-size:clamp(26px,5vw,46px);line-height:1.05;letter-spacing:-.02em}}
h1 span{{color:var(--accent)}}
.meta-row{{display:flex;gap:24px;margin-top:14px;flex-wrap:wrap}}
.meta-item{{font-size:11px;color:var(--muted)}}
.meta-item strong{{color:var(--text)}}
.signal-banner{{background:rgba(232,255,0,.06);border:1px solid rgba(232,255,0,.2);border-radius:2px;padding:14px 18px;margin-bottom:32px;font-size:12px;line-height:1.6;color:#d0ce9f}}
.signal-banner strong{{color:var(--accent);font-size:10px;letter-spacing:.15em;text-transform:uppercase;display:block;margin-bottom:6px}}
.layout{{display:grid;grid-template-columns:1fr 200px;gap:24px;align-items:start}}
@media(max-width:700px){{.layout{{grid-template-columns:1fr}}}}
.cards{{}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:2px;margin-bottom:16px;overflow:hidden;animation:fu .4s ease both}}
@keyframes fu{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
.card-top{{padding:18px 20px 14px;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;gap:14px;justify-content:space-between}}
.card-left{{display:flex;gap:14px;align-items:flex-start;flex:1}}
.idx{{font-family:'Syne',sans-serif;font-size:26px;font-weight:800;color:var(--border);line-height:1;min-width:32px}}
.domains{{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px}}
.db{{font-size:9px;letter-spacing:.12em;text-transform:uppercase;padding:3px 7px;border-radius:1px;font-weight:700}}
.db1{{background:rgba(232,255,0,.15);color:var(--accent)}}
.db2{{background:rgba(255,77,28,.15);color:var(--accent2)}}
.db3{{background:rgba(100,200,255,.12);color:#64c8ff}}
h2{{font-family:'Syne',sans-serif;font-size:15px;font-weight:700;line-height:1.3;color:var(--text)}}
.score-wrap{{text-align:right;min-width:52px}}
.score-label{{font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}}
.score-val{{font-family:'Syne',sans-serif;font-size:24px;font-weight:800}}
.card-body{{padding:18px 20px}}
.block{{margin-bottom:14px}}
.blabel{{font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:5px}}
p{{font-size:12px;line-height:1.75;color:#b8b6af}}
.evidence{{font-size:11px;color:#888;padding-left:16px;line-height:1.8}}
.hook{{background:rgba(232,255,0,.05);border-left:2px solid var(--accent);padding:12px 14px;margin-top:14px;border-radius:0 2px 2px 0}}
.hook-label{{color:var(--accent);opacity:.7}}
.hook-text{{color:var(--text)!important;font-style:italic}}
.sidebar{{}}
.sidebar-box{{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:16px;margin-bottom:16px}}
.sblabel{{font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:12px}}
.dr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}}
.dn{{font-size:10px;color:#888}}
.dc{{font-size:10px;font-weight:700;color:var(--accent)}}
.ts{{font-size:10px;color:var(--muted);margin-top:10px;line-height:1.6}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="tag">Cross-Domain Intelligence Agent</div>
    <h1>Collision<br><span>Detector</span></h1>
    <div class="meta-row">
      <div class="meta-item">Vygenerováno: <strong>{ts_str}</strong></div>
      <div class="meta-item">Domény: <strong>{meta.get('domains_analyzed','?')}</strong></div>
      <div class="meta-item">Článků: <strong>{meta.get('articles_analyzed','?')}</strong></div>
      <div class="meta-item">Kolizí: <strong>{len(collisions)}</strong></div>
    </div>
  </header>

  {f'<div class="signal-banner"><strong>↯ Nejsilnější signál</strong>{strongest}</div>' if strongest else ''}

  <div class="layout">
    <div class="cards">
      {cards_html}
    </div>
    <div class="sidebar">
      <div class="sidebar-box">
        <div class="sblabel">Sledované domény</div>
        {domain_rows}
      </div>
      <div class="sidebar-box">
        <div class="sblabel">O nástroji</div>
        <p class="ts">Agent scrapuje {len(articles_by_domain)} domén, analyzuje průniky pomocí Claude AI a hledá neobvyklá spojení jako základ podcastových epizod.<br><br>Spouští se automaticky přes GitHub Actions.</p>
      </div>
    </div>
  </div>
</div>
</body>
</html>"""


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    print("╔══════════════════════════════════════╗")
    print("║   Cross-Domain Collision Detector    ║")
    print("╚══════════════════════════════════════╝\n")

    # Load config
    with open(FEEDS_FILE) as f:
        config = yaml.safe_load(f)
    print(f"Načteno {len(config['feeds'])} feedů z {FEEDS_FILE}\n")

    # Fetch RSS
    print("📡 Stahuji RSS feedy...")
    articles_by_domain = fetch_feeds(config)
    total = sum(len(v) for v in articles_by_domain.values())
    print(f"\n→ Celkem {total} článků z {len(articles_by_domain)} domén\n")

    if total < 5:
        print("⚠ Příliš málo článků, kontroluj RSS feedy.")
        return

    # Analyze
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY není nastaven!")

    client = anthropic.Anthropic(api_key=api_key)
    data   = analyze_collisions(articles_by_domain, client)

    n = len(data.get("collisions", []))
    print(f"✓ Claude vrátil {n} kolizí")

    # Render HTML
    OUTPUT_DIR.mkdir(exist_ok=True)
    generated_at = datetime.now(timezone.utc)
    html = render_html(data, articles_by_domain, generated_at)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"✓ Report uložen: {OUTPUT_FILE}")

    # Save raw JSON for debugging
    (OUTPUT_DIR / "last_run.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("✓ JSON uložen: docs/last_run.json")
    print("\n✅ Hotovo!")


if __name__ == "__main__":
    main()
