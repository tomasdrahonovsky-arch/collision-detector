# ↯ Cross-Domain Collision Detector

Agent, který každý den scrapuje RSS feedy z 10+ domén, analyzuje průniky pomocí Claude AI a navrhuje neobvyklá spojení jako základ podcastových epizod.

## Co to dělá

1. **Stáhne** aktuální články z RSS feedů (neurověda, sociologie, AI, FMCG, politika, urbanismus...)
2. **Pošle** obsah Claudovi s instrukcí pro cross-domain pattern matching
3. **Vygeneruje** HTML report s kolizemi, mechanismy průniku a návrhy epizod
4. **Publikuje** na GitHub Pages automaticky každý den v 8:30 CET

## Struktura projektu

```
collision-detector/
├── agent.py              # hlavní skript
├── feeds.yaml            # seznam RSS feedů s doménami
├── requirements.txt
├── .github/
│   └── workflows/
│       └── detect.yml    # GitHub Actions (denní spouštění)
└── docs/
    ├── index.html        # výstupní report (GitHub Pages)
    └── last_run.json     # raw JSON z posledního běhu
```

## Setup (5 minut)

### 1. Vytvoř GitHub repozitář

```bash
git init collision-detector
cd collision-detector
# zkopíruj soubory
git add .
git commit -m "init"
git remote add origin https://github.com/TVOJE_JMENO/collision-detector.git
git push -u origin main
```

### 2. Přidej API klíč jako Secret

GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**

- Name: `ANTHROPIC_API_KEY`
- Value: `sk-ant-...`

### 3. Zapni GitHub Pages

GitHub repo → **Settings → Pages**
- Source: `Deploy from a branch`
- Branch: `main` / folder: `/docs`
- Uložit

Report bude dostupný na: `https://TVOJE_JMENO.github.io/collision-detector/`

### 4. První spuštění

GitHub repo → **Actions → Collision Detector → Run workflow**

## Úpravy

### Přidat/odebrat feed

Edituj `feeds.yaml` — přidej záznam s `url`, `domain` a `label`.

Dostupné domény: `psychology`, `neuroscience`, `sociology`, `demography`, `urbanism`, `policy`, `politics`, `ai_ethics`, `ai_development`, `climate_migration`, `religion`, `fmcg`, `media`, `health`

### Změnit čas spouštění

V `.github/workflows/detect.yml` uprav cron:
```yaml
- cron: '30 6 * * *'   # 6:30 UTC = 8:30 CET
```

### Počet kolizí

V `agent.py` změň `COLLISIONS = 6` na požadované číslo.

## Lokální testování

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python agent.py
# Report: docs/index.html
```
