# cv-tailor

Tailors one master CV (JSON) to one or more job postings. For every job it produces a one-page, ATS-friendly PDF with identical formatting, then delivers it as local files, as a Telegram reply, or both.

The AI may only rephrase, reorder, and select existing content: the summary, skill items inside their groups, experience bullets, and the selection, order, and bullets of projects. Contact details, companies, roles, dates, project names, education, and certifications are always rendered straight from the master CV and never sent to the model. A deterministic guard rejects any tailored output that invents skills, ids, or numbers.

## Setup

Requires Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e . --no-deps
cp .env.example .env
cp data/master_cv.example.json data/master_cv.json
```

Edit `.env` (at minimum `GEMINI_API_KEY` and `GEMINI_MODEL`) and replace `data/master_cv.json` with your own CV. `data/master_cv.json`, `.env`, and `out/` are git-ignored.

Runtime only: `pip install -r requirements.txt`.

## Run locally

```bash
python -m cv_tailor --jobs-file data/jobs.example.json
python -m cv_tailor --jobs-file data/jobs.example.json --delivery both
```

Flags (the only two):

| Flag | Meaning |
| --- | --- |
| `--jobs-file PATH` | JSON list of jobs. Ignored when `JOBS_JSON` is set. |
| `--delivery local\|telegram\|both` | Overrides `DELIVERY`. |

Local delivery writes `OUT/{job_id}.pdf` and `OUT/{job_id}.tailored.json`.

Exit code is `0` only when every job succeeded, otherwise `1`. Successful jobs are still delivered when others fail. Configuration errors also exit with `1` before any API call.

## Input formats

Master CV: `contact` (`name`, `email`, `phone`, `location`, `links`), `summary`, `skills` (`[{group, items}]`), `experience` and `projects` (each with a stable string `id` and `bullets`), `education`, `certifications`. See `data/master_cv.example.json`.

Jobs: a JSON list of `{job_id, title, company, description, url?, score?, telegram_message_id?}`. `job_id` may contain only letters, digits, `_`, `-`, and `.` (it becomes a file name) and must not start with a dot. Duplicate ids are dropped and descriptions are truncated to `MAX_DESCRIPTION_CHARS`. See `data/jobs.example.json`.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `GEMINI_API_KEY` | required | |
| `GEMINI_MODEL` | required | No built-in default. |
| `GEMINI_TEMPERATURE` | `0.2` | |
| `GEMINI_TIMEOUT_SECONDS` | `120` | |
| `BATCH_SIZE` | `3` | Jobs per Gemini call. |
| `MAX_DESCRIPTION_CHARS` | `6000` | |
| `MAX_PROJECTS` | `3` | |
| `GUARD_RETRY_LIMIT` | `1` | Corrective single-job calls per job. |
| `DELIVERY` | `local` | `local`, `telegram`, or `both`. |
| `OUTPUT_DIR` | `out` | |
| `MASTER_CV_PATH` | `data/master_cv.json` | |
| `MASTER_CV_JSON` | unset | Inline JSON, overrides `MASTER_CV_PATH`. |
| `JOBS_JSON` | unset | Inline JSON, overrides `--jobs-file`. |
| `TELEGRAM_BOT_TOKEN` | unset | Required when delivery includes telegram. |
| `TELEGRAM_CHAT_ID` | unset | Required when delivery includes telegram. |

Empty variables are treated as unset.

## Telegram behavior

The PDF is sent with `sendDocument`, as a reply to the job's `telegram_message_id` when present. The file is named `{contact name}_CV_{company}.pdf` with every character outside `[A-Za-z0-9_.-]` replaced. The caption is `{title} @ {company}` followed by warnings, capped at 1024 characters. A CV that spills onto a second page is still delivered, with a warning in the caption. A failed job gets a short text reply with a fixed, sanitized reason. Bot tokens, CV content, and job descriptions are never logged.

## Tests and checks

```bash
ruff check .
ruff format --check .
mypy
pytest
```

Tests need no network. `tests/test_zero_comments.py` fails on any comment or docstring in `src/` and `tests/`.

## Planned: GitHub Actions

The same entry point (`python -m cv_tailor`) is intended to run from a `workflow_dispatch` workflow, with the master CV supplied through `MASTER_CV_JSON`, jobs through `JOBS_JSON`, and secrets through repository secrets. No workflow file exists yet.
