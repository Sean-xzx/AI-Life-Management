# Verification and limits / 验证与限制

## Reproducible checks / 可复现检查

Run the four verification commands in either README. The automated suite invokes the real CLI in isolated temporary directories. It covers empty reads, Unicode, corrections, retries, stale revisions, invalid completion, pause, locks, snapshot conflicts, incomplete logs, custom records and skill-directory protection. The repository verifier checks links, the 42-topic mapping, README command parity and unchanged core hashes. Packaging is repeated and compared byte-for-byte.

按任一 README 的四条命令运行。测试在临时目录调用真实助手，覆盖读取、中文、纠正、重试、版本冲突、无效完成、暂停、锁、快照冲突、不完整日志、自建资料和技能目录保护。仓库验证还检查链接、42项映射、中英文命令一致性和核心哈希。打包重复执行并比较二进制一致性。

## Prior conversational evidence / 先前对话证据

Ten isolated scenarios were exercised during skill development: unclear start, low energy, learning without practice, career choice, a location constraint, stalled writing, pause, file-based continuation, correction and unavailable reminders. The first writing review mixed a user report with an AI hypothesis. A targeted retest separated report, estimate and suggestion, leaving the action planned. These observations informed the shipped guidance.

技能开发时试用了十个隔离场景：起步不明、低精力、学而不练、方向选择、地点底线、写作停滞、暂停、文件衔接、纠正和无提醒工具。首次写作复盘发生报告与假设混录；定向重测后分类分开，行动仍为计划。规则已吸收这一实际反馈。

Raw conversational traces are deliberately not published: they include local paths and temporary context. The scenarios are human-readable evidence, not a pinned model benchmark. They cannot be rerun identically without fixing the host, model, prompts, tool permissions and evaluation protocol. No long-term user study, medical outcome or financial return was verified.

原始轨迹包含本地路径和临时上下文，不公开上传。这些是定性证据，不是锁定版本的模型基准。严格复现还需固定宿主、模型、提示、工具权限和评估协议。尚未验证长期用户研究、医疗结果或金融回报。

## Platform and CI / 平台与自动检查

Local baseline: Windows 11, Python 3.12.14, clean virtual environment without system packages. On 2026-10-13, [CI run 38336649364](https://github.com/Sean-xzx/AI-Life-Management/actions/runs/38336649364) completed successfully for the publication baseline: both Ubuntu and Windows Python 3.12 jobs passed tests, verification, demo and packaging. The workflow uses standard runners with no paid runner, artifact upload or cache. macOS, other Python versions and real crash/power-loss injection are unverified.

本地基线为 Windows 11、Python 3.12.14，不使用系统包的干净虚拟环境。2026-10-13，[CI 运行 38336649364](https://github.com/Sean-xzx/AI-Life-Management/actions/runs/38336649364)在发布基线上成功完成：Ubuntu 与 Windows Python 3.12 作业的测试、验证、演示和打包均通过。采用标准 runner，不使用收费 runner、产物上传或缓存。macOS、其他 Python 版本和真实断电注入未验证。

## Boundaries / 边界

No silent correction of an inconsistent snapshot. No automatic removal of another writer's lock. No claims of semantic correctness, automatic reminders or cross-device synchronization. The unchanged helper's input guards are not a security sandbox against an adversarial filesystem; use a dedicated, trusted local data directory, and do not use symlinked locations. Keep sensitive records outside Git.

不静默修复不一致快照，不自动删除其他写入者的锁，不保证语义正确、后台提醒或跨设备同步。未改动助手的输入防护不是针对恶意文件系统的安全沙箱；请使用独立可信的本地资料目录，避免符号链接路径。敏感记录不进入 Git。
