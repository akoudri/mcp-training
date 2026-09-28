# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Lab kit for the training « Créer des agents IA avec MCP » (running scenario: PHAROS, a fictional port operator). Learners work in pairs (« binômes ») through LAB 0–14, building MCP servers (FastMCP 4) and an agent client. Everything — code, comments, docstrings, commit messages, make output — is written in **French**; keep it that way. Commits follow `type(scope): message` in French (e.g. `fix(lab14): …`, `docs(salle): …`, `chore: …`).

## Commands

Python 3.12, managed with `uv` (`uv sync`). Most make targets run inside Docker (`atelier` service, image `pharos/python:2`); `make construire` builds that image. `make` alone lists all targets (`## ` comments in `mk/*.mk`).

- Tests (host): `uv run pytest -q` — single test: `uv run pytest tests/test_depart.py::nom_du_test -q`
- Tests (container): `make test`
- DB-backed tests (marker `base_requise`, fixture `base_de_test`) are skipped unless `PHAROS_DSN_TEST` is set; they **reload** the database. Locally: `make lab8-base` then `PHAROS_DSN_TEST=postgresql://postgres:pharos-salle-2026@127.0.0.1:5433/pharos uv run pytest -q`
- `tests/solutions/test_labN.py` only run on the `solutions` branch (skipped when `solutions/labNN/` is absent).
- Environment: `make up`, `make lab0-up`, `make doctor` (`SANS_MODELE=1` to skip the LLM check); `make down`, `make logs S=<service>`.
- Per-lab targets live in `mk/labN.mk`: `labN-up`, `labN-scaffold`, `labN-verifier` (`SANS_MODELE=1` to skip model-dependent criteria), etc.
- Try a whole lab state end-to-end in Docker exactly like CI: `make essayer LAB=N` (uses committed HEAD; stops the `pharos` Compose stack).
- Call a tool manually: `make appeler URL=http://observateur:8101/mcp OUTIL=… ARGS='{…}'`.
- Regenerate corpus PDFs: `make fixtures`.

## Architecture

### Branch / checkpoint model (the key non-obvious part)
- `main`/`dev`: the kit — tooling, reference infra, and **gabarits** (starter templates), but no lab solutions.
- `solutions`: same tree plus `solutions/labNN/` snapshots (complete files to overlay).
- `etat/<checkpoint>-fin`: assembled lab states. `outils/construire_etats.py` (`make construire-etats`) builds `etat/<SORTIES[N]>` = base + for k=1..N: `gabarits/labkk/` copied without overwrite, then `solutions/labkk/` copied with overwrite; `solutions/` removed. One commit per state.
- `outils/labs.py` is the single table mapping each lab to its start checkpoint (`DEPARTS`), end checkpoint (`SORTIES`), make targets to start its services (`DEMARRAGE`) and ports to wait on (`PORTS_PRETS`). Update it when adding a lab.
- Learners run `make depart LAB=N` (`outils/depart.py`): creates `binome-<B>-labNN` from `origin/etat/<DEPARTS[N]>` and copies `gabarits/labNN/` **never overwriting**. `gabarits/labNN/` mirrors repo-root paths (e.g. `gabarits/lab08/serveurs/pharos_data/…` → `serveurs/pharos_data/…`).
- So files like `serveurs/pharos_docs`, `serveurs/pharos_data`, `serveurs/pharos_ops`, `client/pharos_client` do **not** exist on `main`; they appear only in lab states. Tooling and tests must tolerate their absence.
- Lab solutions go on the `solutions` branch, never on `main`.

### Code layout
- `src/pharos*` (on `PYTHONPATH`): shared libraries — `pharos` (DB DSNs, auth, tokens, journal, clock, OpenRouter, weather/channel clients), `pharos_docs` (document store/PDF extraction), `pharos_ops` (planning).
- `serveurs/`: reference servers present from the start — `pharos_legacy` (LAB 2–3), `pharos_quai` (LAB 6), `mocks` (external systems, LAB 10+), `salle` (LAB 14 classroom service run by the trainer).
- `labs/lab0/`: the LAB 0 demo server `pharos-docs-demo`; `labs/labN/` otherwise holds learner deliverables (markdown reports, configs).
- `outils/`: stdlib-only host scripts (`depart`, `labs`, `construire_etats`, `essayer` — run with plain `python3`, no venv) plus in-container tools (`doctor`, `client_test`, `banc`, `tokens_catalogue`, …).
- `outils/verifier/`: one module per lab (`make labN-verifier` → `python -m outils.verifier labN`). Framework in `commun.py`: one function per success criterion of the brief, in brief order; results are ✅/❌/👁/⏭; raise `Echec` with what to fix. `modele_simule.py` stands in for the LLM when `SANS_MODELE=1`.
- `donnees/`: fixture generators — PDF corpus (`donnees/documents/`, committed), PostgreSQL schema/data (`donnees/base`), legacy, quay, referential data.
- `compose.yaml` + every `compose/*.yaml` are merged by the Makefile (`DC`); `compose/commun/base.yaml` is the shared `python-base` service, kept in a subfolder so it isn't loaded as an overlay.

### Networking
All MCP servers listen on internal port 8000 at `/mcp` and are reached **only through the `observateur`** (mitmproxy reverse proxy, UI on http://localhost:7001, password `pharos`), which maps host ports 8100–8105, 8201, 8203, 8204 to each server; a 502 means the target server isn't running. Everything is published on 127.0.0.1 only (except the LAB 14 classroom service on 8300). PostgreSQL is on 5433. See `PORTS.md`.

### Secrets vs. classroom values
Values like `pharos-salle-2026`, `CLE_SERVEUR`, `METEO_CLE`, `CLE_ETAT` are deliberate classroom constants, not secrets. The real secret is `OPENROUTER_API_KEY` in `.env` (from `.env.example`, alongside `PHAROS_MODELE` and `PHAROS_BINOME`).

## CI
`.github/workflows/ci.yml`: `uv sync --frozen && uv run pytest -q` with a Postgres service (`PHAROS_DSN_TEST` set); a `socle` job that brings up LAB 0 and runs `make doctor SANS_MODELE=1`; and, on the `solutions` branch only, a matrix running `python3 -m outils.essayer N` for every lab.

## Other docs
- `PREPARATION.md` (learner machine setup), `INSTALLATION_SALLE.md` (trainer runbook), `docs/recette/` (acceptance/calibration notes per sub-project), `docs/decisions/` (design decisions, e.g. VS Code + OpenRouter as the graphical client).
- `.github/copilot-instructions.md` and `.github/agents/pharos.agent.md` are **lab content** for the VS Code agent used by learners (fixed date: Tuesday 6 October 2026, Europe/Paris; use MCP tools only) — not instructions for working on this repo.
