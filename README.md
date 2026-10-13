[简体中文](README.zh-CN.md) | English

# AI Life Management

A Chinese-first life-management assistant: start with one pasted prompt, turn goals into small actions and review the day using recorded evidence.

## Start in a minute

Open [the complete startup prompt](ai-life-management-easy/assets/start.txt), paste it into a text-chat assistant and say: **“I only have 15 minutes today. Help me get started.”** This entry needs no installation and asks one necessary question at a time.

Say “record this,” “what now?”, “make it smaller,” “pause,” or “end today's session.” Daily reports have five short sections: overview, progress, explanation, tomorrow's next step and evidence coverage. They use the available full-day record and identify gaps.

The prompt is portable text; **every model/software combination has not been tested**. File continuity and live system time require host tools. Without them, the assistant uses the current conversation and confirms time only when needed. Automatic evening delivery requires a separately configured scheduler.

## Value and project contribution

Planning assistants often generate more tasks without establishing what was actually done. This project separates **suggestions, user decisions and observed results**, so a later review can use recorded progress instead of rebuilding context from memory.

Project work by **Sean-xzx, with AI assistance**:

- Translated a long-form interview analysis into three operational lenses: cognition and options, sustainable energy, and autonomous action with correction.
- Mapped **18 AI-management topics and 24 reasoning principles** into task-specific workflows and traceable references.
- Delivered a compact skill with nine entry modes, eight application domains and an auditable, standard-library-only record helper.
- Validated record invariants and exercised ten isolated conversational scenarios; a mixed fact/inference record found during trial was corrected and retested.

The technical focus is **progressive resource loading, explicit evidence categories, revision checks and append-only history**, rather than a new model or a claim of scientific novelty. It supports daily planning, goal work, decisions, experiments and reviews. It is not an autonomous background service.

The new daily interaction layer adds progressive onboarding, complete daily context, time checks and versioned reports; the original eight core files are unchanged.

## Evidence at a glance

| Evidence | What it establishes |
| --- | --- |
| 39 automated tests | Core records, full-day coverage, revisions and reminder boundaries |
| Ubuntu and Windows CI | Tests, project verification, demo and packaging passed on both runners |
| Ten earlier isolated scenarios | Immediate replies and file continuity; not long-term effectiveness |
| Retested writing scenario | User reports, hypotheses and action suggestions were saved separately |
| Core SHA-256 manifest | The eight original skill files were preserved during repository preparation |

See [verification and limits](docs/verification.md). No productivity, health or investment gains have been measured.

## Requirements

Python **3.12**, Git for cloning, and no third-party Python packages. Local verification used **Windows 11 / Python 3.12.14**. Ubuntu and Windows Python 3.12 CI jobs also passed; see the dated [verification record](docs/verification.md).

Both command-line demos work offline and needs no account, model, dataset, GPU or API key. The portable prompt needs a text-chat host; installing the skill needs a compatible Codex host; host pricing and tool availability are outside this project.

## Quick start

For the owner or authorized readers:

```sh
git clone https://github.com/Sean-xzx/AI-Life-Management.git
cd AI-Life-Management
python -m venv --without-pip .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# POSIX shell
. .venv/bin/activate
```

No dependency installation is needed. Run:

```sh
python -m unittest discover -s tests -v
python tools/verify_project.py
python examples/demo.py
python examples/daily_demo.py
python tools/package_skill.py
```

Success means all tests pass, `Project verification passed` appears, the demo ends with `Demo passed: revision=6, weekly_minutes=30, goal_status=paused, action_status=cancelled`, and `dist/ai-life-management.zip` is created. The demo uses a temporary directory and does not alter personal records.

## Skill usage

```sh
python tools/install_skill.py
```

This copies the skill into `$CODEX_HOME/skills` or `~/.codex/skills`. Identical files are accepted; a differing existing installation is left intact and reported. Load the skill in a compatible host and try:

```text
$ai-life-management-easy 我今天只有20分钟，帮我确定下一步。
$ai-life-management-easy 根据已有记录，做一次每周复盘。
```

For a direct helper invocation and event schema, see [the record guide](ai-life-management/references/records.md). Installation writes only skill files; user data is separate.

## Daily reports and time

Installation includes both the easy entry and the original core; use `$ai-life-management-easy` as the everyday entry. The original entry remains available. The adapter exports all events for the selected local date and relevant earlier context. A model interprets that context; the adapter validates references, categories and length before saving. Structural validation does not establish semantic correctness.

For existing synthetic or private records (keep personal data outside Git):

```sh
python ai-life-management-easy/scripts/daily.py clock --offset +08:00
python ai-life-management-easy/scripts/daily.py context --root ../life-records --date 2026-10-13 --offset +08:00
python ai-life-management-easy/scripts/daily.py next --root ../life-records --offset +08:00
```

Give the complete context to a model using [the analysis protocol](ai-life-management-easy/references/interaction.md), save its structured answer as `analysis.json`, then:

```sh
python ai-life-management-easy/scripts/daily.py report --root ../life-records --date 2026-10-13 --offset +08:00 --analysis-file analysis.json --write
```

Success creates `reports/2026-10-13.md` and `.json` under the data root. Regenerate after supplements; previous versions go to `reports/history/`. Omitting `--analysis-file` produces an explicitly labeled rule preview. An empty store can yield a chat report but cannot save before a real record store exists. UTC offset defaults to +08:00; set yours explicitly and update it for daylight-saving changes. `next` checks only accepted due actions and quiet preferences when invoked; it does not run in the background.

The new demo reports `events=4, idempotent=True, core_history_unchanged=True, mode=rules`. It verifies full-day coverage, repeat generation and unchanged core history. It is a **rule preview and does not call a model**.

## Structure and data flow

```text
ai-life-management-easy/ Portable prompt, easy entry, daily context and report adapter
ai-life-management/    Skill entry, Chinese references, UI metadata, record helper
examples/             Offline, synthetic record-lifecycle demo
tests/                Portable CLI and repository checks
tools/                Verification, packaging and non-overwriting installation
docs/                 Architecture, evidence, unchanged-core manifest
.github/workflows/    Automated checks
```

`SKILL.md` routes a request to the relevant workflow. The AI separates evidence and user preferences before proposing an action. The helper appends an event to `history.jsonl`, then generates `state.json` and the readable `journal.md`. A later request reads current goals and feedback. [Architecture](docs/architecture.md) explains this flow and the limits of structural validation.

## Configuration, testing and project status

No `.env` file is required. The helper requires an explicit `--root` data directory. Events are supplied through UTF-8 JSON files; stale revisions return exit code 2 instead of overwriting data. Do not commit real user records. No external training, inference or licensed dataset is needed for the demo.

This is a working prototype with local validation. Automatic reminders, account access and cross-device synchronization require separately available tools. History checks do not prove semantic truth, privacy completeness or recovery from every system crash. Conversational trials are not automatically repeatable model evaluations because model/host versions and tool contexts were not pinned. Medical and financial decisions remain outside the demo's scope.

Run the commands above after changes; see [verification](docs/verification.md) for what can be reproduced. Report bugs through [Issues](https://github.com/Sean-xzx/AI-Life-Management/issues), with Python/OS versions, a minimal synthetic event and the expected/actual result. Do not attach credentials or personal logs. Proposed modifications require owner permission; no maintenance cadence is promised.

## Rights and sources

**All rights reserved; no open-source license.** Public viewing does not authorize reuse or modification. GitHub's platform viewing/forking rights still apply. See [rights and provenance](RIGHTS.md), [theory](ai-life-management/references/theory.md) and [source index](ai-life-management/references/source-index.md). Original interview media and transcript files are not included.

The easy entry handles onboarding and natural language; the original skill supplies theory and record rules. The adapter reads history, exports context and saves derived reports without changing core history. See [interaction design, ten examples and delivery stages](docs/interaction-design.md).
