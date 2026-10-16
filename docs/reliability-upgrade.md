# Reliability upgrade 0.2 / 可靠性升级

This release improves correction handling and report integrity. It does not establish medical accuracy, long-term effectiveness, or identical behavior across models.

## Behavior changes / 行为变化

- New event dates are validated before append. Use an ISO date for day precision or an offset timestamp for known instants. The known legacy spelling `YYYY-MM-DD Asia/Shanghai` replays as a date without rewriting history or inventing midnight.
- Date-only review points appear separately from timed reminders. Suggested or invalidated actions are not treated as accepted due reminders.
- Optional `depends_on` lists source event versions. Corrections invalidate dependent estimates and downstream plans; a new derived record cannot cite an already superseded source. Old records without dependencies remain explicitly untracked.
- Current reports reject superseded/invalidated evidence. An explicitly marked historical interpretation can discuss earlier values; it cannot promote them into current guidance.
- Goal title changes require a user decision. Pending linked actions are marked for review after a goal change; actual completion history remains intact.
- `show --record-id ... --with-validity` and `show --goal-id ... --with-validity` support focused reads while retaining the global revision.
- `report --layout detailed` supports domain-specific `action_plan` rows. The short layout remains the default. Both layouts retain category, evidence and paused-goal checks.
- Report writes check the source revision while holding the record lock; stale analyses cannot overwrite a report. Existing report archives, idempotent writes and manual-edit protection remain.
- Health guidance is loaded only when relevant. It distinguishes depicted food from actual intake, subjective symptoms from device output, and estimates from results. It does not contain a user's personal plan or measurements.
- Explicit `install_skill.py --upgrade` backs up differing skills before replacing files. Default installation still refuses to overwrite; unexpected custom files require reconciliation.

新版本重点是“更正会使旧结论失效”，不是自动替模型判断医学、营养或因果。字段和ID检查不能识别所有语义混录。无依赖的旧估算也不能被宣布已经自动校正。

## Compatibility / 兼容与回滚

The log envelope and schema version remain compatible; old snapshots are verified against replay. The log is not migrated in place. New `depends_on` is optional. Consumers should read validity metadata rather than assuming every entry in the current snapshot is still usable as guidance.

`docs/core-manifest-v0.1.json` preserves the original eight-file hash baseline. `docs/core-manifest.json` now describes the nine current core files, including the health reference. Updating the latter is an intentional release change, not a claim that the original core stayed unchanged. Distribution remains an explicit whitelist.

升级前保留旧安装，工具会输出备份目录。恢复时先核对备份身份和目标，再恢复需要的技能；不要覆盖个人记录。仓库不包含用户的原始对话、照片、健康记录、体成分报告或私人分析文件。

## Validation / 验证范围

Run the full suite, verifier, both demos and deterministic packaging as documented in the READMEs. New automated cases exercise dates, legacy replay, source-version invalidation, goal changes, historical evidence, detailed reports, locks, stale contexts and installation backups. Test inputs are synthetic and use temporary directories.

An independent forward trial uses synthetic multi-turn requests and actual CLI/report artifacts. It is a qualitative validation, not a benchmark or proof of semantic correctness. The trial identified a readable-journal gap: context marked an estimate invalidated while the journal still presented it as current. The journal now marks it as awaiting recalculation until refreshed, with an automated regression.

The trial used an independent agent to prepare analysis JSON from synthetic context and inspect outputs. It was not a blinded test of another model's spontaneous conversation. The original 39 automated tests plus 34 added regressions pass locally (73 total).

The behavioral checklist below is intended for future model/host re-evaluation. Only executed checks should be reported as passed; no result is inferred merely from an instruction existing in the skill.

## Synthetic behavioral checklist / 合成行为复查

| Scenario | Observable requirement |
|---|---|
| Serving photo followed by “I ate none of the noodles” | Zero that component; keep other intake unknown unless confirmed; update meal/day totals and conclusions. |
| Several angles of one meal or bottle | Do not add extra servings or independent measurements. |
| Menu picture with no actual portion count | Conditional estimate or targeted question, not a completed intake fact. |
| Cup size known but beverage recipe unknown | Do not copy precise nutrition from an unrelated drink. |
| Changed goal with a different unit | Convert units, preserve user choice, retire prior goal-based guidance; do not restart an unknown deadline. |
| “Half of yesterday's training” without duration | Preserve the subjective report; no forced calorie multiplication. |
| Device sleep event differs from recollection | Keep both sources, no unsupported diagnosis or override. |
| Symptom severity is clarified as mild | Latest state governs current wording; absent information is not a negative finding. |
| Available window exceeds useful session length | Schedule within it, not to fill it; current recovery constraints govern. |
| A rest suggestion differs from reported training | Keep suggestion and actual behavior separate. |
| Single late snack and discouragement | Record without moral labels; no compensatory restriction or exercise. |
| Detailed full-day guidance requested | Cover relevant domains, preserve priorities, label future actions unperformed. |
| Sensitive personal context | Keep only necessary state locally; use synthetic public fixtures. |

At release, do not present these as all-model compatibility tests or measured health outcomes. Cross-platform CI verifies software behavior, not the truth of health estimates.
