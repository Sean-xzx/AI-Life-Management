简体中文 | [English](README.md)

# AI 人生管理

一个中文优先的人生管理助手：一句提示词开始，把目标变成小行动，用已有证据做简短复盘。

## 一分钟开始

打开[完整启动提示词](ai-life-management-easy/assets/start.txt)，复制全文到能够接受文本对话的 AI 软件，再说：**“我今天只有15分钟，帮我开始。”** 这个入口不需要安装，一次只问一个必要问题。

日常直接说“记一下”“现在做什么”“太难了，缩小一点”“先暂停”“今天结束了”。日报保持五个短模块：今日概览、实际进展、原因分析、明日一步、证据覆盖；结合可访问的全天记录，并说明遗漏。

提示词可跨平台复制，但**没有逐一验证所有模型和软件**。文件衔接、实时系统时间依赖宿主工具；没有工具时只依据当前对话，必要时确认时间。晚上自动推送需要另行配置调度器。

## 项目价值与贡献

规划助手容易不断生成任务，却说不清哪些事情实际完成了。本项目区分**建议、用户决定与实际结果**，让后续复盘能够依据已有进展，而不是凭记忆重新解释背景。

**Sean-xzx 在 AI 辅助下完成的项目工作：**

- 将长篇访谈分析转化为三个行动视角：认知与选择、持续精力、自主行动与纠错。
- 将 **18 项 AI 管理主题和 24 项认知原则**对应到具体流程与可追溯资料。
- 实现包含九种入口模式、八类应用领域的技能，以及仅依赖 Python 标准库的可审计记录助手。
- 验证记录规则，并开展十个隔离对话场景试用；试用发现事实与推断混录后，修正规则并定向复测。

技术重点是**按需加载参考、证据分类、版本检查与追加历史**。项目没有训练新模型，也不宣称科学创新。它辅助日常安排、目标、决定、试验与复盘，不是自动运行的后台服务。

新增日常交互层提供逐步引导、全天上下文导出、时间检查与版本化日报，当前核心增加更正依赖与日期校验，原八文件哈希基线单独归档。

## 成果证据

| 证据 | 能说明什么 |
| --- | --- |
| 自动化回归测试 | 核心记录、全天覆盖、日报修订与提醒边界 |
| Ubuntu 与 Windows CI | 两个平台的测试、项目验证、演示和打包均通过 |
| 先前十个隔离场景 | 当下回复与文件衔接，不证明长期效果 |
| 写作场景定向复测 | 用户报告、原因假设与行动建议分别保存 |
| 核心 SHA-256 清单 | 当前发布哈希与归档原基线可分别核验 |

见[验证与限制](docs/verification.md)。尚未测得效率、健康或投资收益改善。

## 环境要求

Python **3.12**；克隆项目需要 Git；不需要第三方 Python 包。已在 **Windows 11 / Python 3.12.14** 本地验证。Ubuntu 与 Windows 的 Python 3.12 CI 作业也已通过，见带日期的[验证记录](docs/verification.md)。

两个命令行演示均可离线运行，不需要账户、模型、数据集、GPU 或 API 密钥。通用提示词需要文本对话宿主；安装技能需要兼容的 Codex 环境；宿主费用与工具能力不由本项目决定。

## 快速开始

以下复现说明面向所有者或已取得许可的读者：

```sh
git clone https://github.com/Sean-xzx/AI-Life-Management.git
cd AI-Life-Management
python -m venv --without-pip .venv
```

激活环境：

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# POSIX shell
. .venv/bin/activate
```

无需安装依赖。运行：

```sh
python -m unittest discover -s tests -v
python tools/verify_project.py
python examples/demo.py
python examples/daily_demo.py
python tools/package_skill.py
```

成功标准：测试全部通过，出现 `Project verification passed`，演示最后输出 `Demo passed: revision=6, weekly_minutes=30, goal_status=paused, action_status=cancelled`，并生成 `dist/ai-life-management.zip`。演示使用临时目录，不修改个人记录。

## 使用技能

```sh
python tools/install_skill.py
```

安装到 `$CODEX_HOME/skills` 或 `~/.codex/skills`。相同文件可沿用；如果已有安装内容不同，则保留并报告，不覆盖。明确要求升级时使用 `--upgrade`，先备份再更新。在兼容宿主中加载技能后，可这样开始：

```text
$ai-life-management-easy 我今天只有20分钟，帮我确定下一步。
$ai-life-management-easy 根据已有记录，做一次每周复盘。
```

直接调用记录助手的方式与事件结构见[记录说明](ai-life-management/references/records.md)。安装只写技能文件，个人资料另行保存。

## 日报与时间

安装工具同时安装日常交互入口与原核心，建议使用 `$ai-life-management-easy`。原入口仍保留。日常交互先读取选定本地日期的完整记录及相关先前背景，再由模型分析；助手验证引用、分类和长度后保存。校验不证明模型推断在语义上正确。

对已有虚构或私人记录执行（私人记录放在 Git 之外）：

```sh
python ai-life-management-easy/scripts/daily.py clock --offset +08:00
python ai-life-management-easy/scripts/daily.py context --root ../life-records --date 2026-10-13 --offset +08:00
python ai-life-management-easy/scripts/daily.py next --root ../life-records --offset +08:00
```

按[分析协议](ai-life-management-easy/references/interaction.md)将完整上下文交给模型，保存其结构化答复为 `analysis.json`，再执行：

```sh
python ai-life-management-easy/scripts/daily.py report --root ../life-records --date 2026-10-13 --offset +08:00 --analysis-file analysis.json --write
```

成功后资料目录出现 `reports/2026-10-13.md` 与 `.json`；补充记录后重做日报，旧版本归档到 `reports/history/`。省略 `--analysis-file` 时明确输出规则预览；空资料库可在聊天中给出日报，但建立真实记录库前不能保存。UTC 偏移默认 +08:00，请明确设置自己的偏移，夏令时变更也需更新。`next` 只在调用时检查用户已接受的到期行动及免打扰偏好，不在后台运行。

新增演示的成功标志为 `events=4, idempotent=True, core_history_unchanged=True, mode=rules`。它验证全天汇总、重复生成与核心日志不变，是**规则预览，不调用模型**。

## 结构与数据流

```text
ai-life-management-easy/ 通用提示词、日常入口、全天上下文与日报助手
ai-life-management/    技能入口、中文参考、界面信息和记录助手
examples/             离线的虚构记录生命周期演示
tests/                可移植的命令行和仓库检查
tools/                验证、打包及不覆盖已有内容的安装工具
docs/                 架构、证据和核心不变校验清单
.github/workflows/    自动检查
```

`SKILL.md` 将请求引导到相关流程。AI 区分证据与个人偏好，再提出行动。助手追加 `history.jsonl`，随后生成 `state.json` 和可读的 `journal.md`。下次任务读取当前目标与反馈。[架构说明](docs/architecture.md)进一步解释流程与结构校验的边界。

## 配置 验证与项目状态

无需 `.env`。记录助手要求明确的 `--root` 数据目录，以 UTF-8 JSON 文件输入事件；过时版本返回退出码 2，不覆盖资料。不要提交真实用户记录。演示无需外部训练、推理或受许可限制的数据集。

项目是经过本地验证的可用原型。主动提醒、账户读取与跨设备同步需要另外可用的工具。历史检查不能证明语义真实、隐私完整或任意崩溃都能恢复。对话试用未锁定模型、宿主与工具版本，因此不能当作自动可重复的模型评测。演示不涉及医疗和金融决定。

修改后运行上述命令；可复现范围见[验证说明](docs/verification.md)。通过 [Issues](https://github.com/Sean-xzx/AI-Life-Management/issues)反馈问题，提供系统与 Python 版本、最小虚构事件和预期/实际结果；不要上传凭据或个人日志。代码修改建议需取得所有者许可，不承诺维护周期。

## 权利与来源

**保留所有权利，不添加开源许可证。** 公开查看不授权使用或修改；GitHub 平台的查看与 fork 权利仍适用。见[权利及来源](RIGHTS.md)、[理论说明](ai-life-management/references/theory.md)和[来源索引](ai-life-management/references/source-index.md)。仓库不包含原访谈媒体或逐字稿文件。

日常交互入口负责引导与自然语言，原技能提供理论及记录规则；新增助手读取日志、输出上下文并保存派生日报，不修改核心历史。详见[交互设计、十个示例与交付阶段](docs/interaction-design.md)。

## 更正后的日报与详细建议

[0.2可靠性升级](docs/reliability-upgrade.md)增加旧日期只读兼容、已声明来源版本的依赖失效和含各领域行动建议的详细日报；默认仍为短版。结构校验不证明语义或医学正确。个人记录和私人试用轨迹不进入分发包。

```sh
python tools/install_skill.py --upgrade
python ai-life-management-easy/scripts/daily.py report --root ../life-records --date 2030-04-03 --offset +08:00 --layout detailed --analysis-file analysis.json --write
```

资料目录须实际存在且已获授权，使用真实证据ID；日期仅为格式示例。升级备份位置由工具输出。
