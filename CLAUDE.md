# Webcrawler — Claude Code Instructions

## Project Overview

A web crawler that calls a **crawl4ai Docker service** to extract and download images from URLs.
Currently a single-file CLI (`crawl_images.py`). Being restructured into a FastAPI API with
modular stealth/anti-detection features — see `task-01.md` for the full restructure plan.

### Key Components
- `crawl_images.py` — CLI entry point (calls crawl4ai API, downloads images)
- `docker-compose.yml` — runs the crawl4ai Docker service on port 11235
- `output/` — default image download directory (gitignored)

## Feature Preservation (CRITICAL)

A previous AI session on another project accidentally deleted an entire feature by rewriting
shared files without awareness of existing functionality. These rules prevent that.

### Rules

1. **Never delete or rename existing source files** without explicit user confirmation.
   If you believe a file should be removed, ask first.

2. **Never use the Write tool on shared files.** As the project grows, files that are
   modified by many features (e.g., `app/main.py`, router registrations, shared models)
   must only be edited with the Edit tool (additive changes, not full rewrites).

3. **When modifying shared files**, first Read the current file and preserve ALL existing
   imports, exports, route registrations, and endpoint definitions.

4. **When a `FEATURES.json` manifest exists**, follow these additional rules:
   - Run `python scripts/validate-features.py` before committing
   - Add entries for new features; remove entries before removing feature code
   - Never delete files listed in `critical_files` without user confirmation

5. **When a pre-commit hook is configured**, do not bypass it with `--no-verify`.
   If validation fails, stop and fix the issue.

## Defect Logging

GitHub Issues are the **primary tracker** for defects. Local defect files are supplementary.

When the user reports a bug, defect, or broken behavior:

1. **Get the next ID** from `defects/DEFECT_LOG.md` (see "Next ID" in Metrics).
2. **Create a GitHub issue first** using `gh issue create`:
   - **Title**: `DEF-{NNN}: <short description>`
   - **Labels**: `bug`
   - **Body**: Symptoms, Root Cause, Fix Plan (or "TBD"), Linked Defect path
3. **Create a local defect file** `defects/DEF-{NNN}.md` with the GitHub issue URL and key details.
   Use existing `DEF-*.md` files as format examples.
4. **Update `defects/DEFECT_LOG.md`**:
   - Add a row to the Recent Defects table with the GitHub issue link
   - Update the Metrics (total, open count, next ID)
   - If the table exceeds 5 entries, move the oldest to `defects/DEFECT_ARCHIVE.md`
5. **Status lifecycle**: OPEN → FIXED → VERIFIED → CLOSED
   - When status changes, comment on the GitHub issue and close it at CLOSED
6. When writing tests that cover a defect, update status to VERIFIED in both the local file and GitHub issue.

## Development Notes

- **Python version**: 3.12+ (uses `str | None` union syntax)
- **crawl4ai API**: runs at `http://localhost:11235` (configurable via `CRAWL4AI_API` env var)
- **Start crawl4ai**: `docker compose up -d`
- **Run CLI**: `python crawl_images.py <url> [--output-dir ./output] [--screenshot] [--proxy URL]`
