[简体中文](README.zh-CN.md) | English

# AI Life Management

A Chinese-first Codex skill that turns personal goals into small actions, reviewable evidence and continuity across local records.

## Value and project contribution

Planning assistants often generate more tasks without establishing what was actually done. This project separates **suggestions, user decisions and observed results**, so a later review can use recorded progress instead of rebuilding context from memory.

Project work by **Sean-xzx, with AI assistance**:

- Translated a long-form interview analysis into three operational lenses: cognition and options, sustainable energy, and autonomous action with correction.
- Mapped **18 AI-management topics and 24 reasoning principles** into task-specific workflows and traceable references.
- Delivered a compact skill with nine entry modes, eight application domains and an auditable, standard-library-only record helper.
- Validated record invariants and exercised ten isolated conversational scenarios; a mixed fact/inference record found during trial was corrected and retested.

The technical focus is **progressive resource loading, explicit evidence categories, revision checks and append-only history**, rather than a new model or a claim of scientific novelty. It supports daily planning, goal work, decisions, experiments and reviews. It is not an autonomous background service.

## Evidence at a glance

| Evidence | What it establishes |
| --- | --- |
| Automated CLI tests | Record transitions, retries, corrections and conflict handling |
| Ten earlier isolated scenarios | Immediate replies and file continuity; not long-term effectiveness |
| Retested writing scenario | User reports, hypotheses and action suggestions were saved separately |
| Core SHA-256 manifest | The eight original skill files were preserved during repository preparation |

See [verification and limits](docs/verification.md). No productivity, health or investment gains have been measured.

## Requirements

Python **3.12**, Git for cloning, and no third-party Python packages. Local verification used **Windows 11 / Python 3.12.14**. The public CI configuration targets Ubuntu and Windows with Python 3.12; a configuration is not a claim that a remote run has passed.

The command-line demo works offline and needs no account, model, dataset, GPU or API key. Using the conversational skill requires a compatible Codex host and its normal account/model access; host pricing and tool availability are outside this project.

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
python tools/package_skill.py
```

Success means all tests pass, `Project verification passed` appears, the demo ends with `Demo passed: revision=6, weekly_minutes=30, goal_status=paused, action_status=cancelled`, and `dist/ai-life-management.zip` is created. The demo uses a temporary directory and does not alter personal records.

## Skill usage

```sh
python tools/install_skill.py
```

This copies the skill into `$CODEX_HOME/skills` or `~/.codex/skills`. Identical files are accepted; a differing existing installation is left intact and reported. Load the skill in a compatible host and try:

```text
$ai-life-management 我今天只有20分钟，帮我确定下一步。
$ai-life-management 根据已有记录，做一次每周复盘。
```

For a direct helper invocation and event schema, see [the record guide](ai-life-management/references/records.md). Installation writes only skill files; user data is separate.

## Structure and data flow

```text
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
