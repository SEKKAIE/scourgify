<div align="center">

# Scourgify

### 除垢咒

**Scourgify 是一套面向 Codex、带授权边界的仓库收尾协议：它为脏乱的 Git 工作树建立快照，用五字段账本对账每一条范围内路径，并在宣布工作完成前机械验证交接。**

[English](./README.md) · [简体中文](./README.zh-CN.md)

[![Codex skill](https://img.shields.io/badge/Codex-skill-111827?logo=openai&logoColor=white)](#快速开始)
[![CI](https://github.com/SEKKAIE/scourgify/actions/workflows/ci.yml/badge.svg)](https://github.com/SEKKAIE/scourgify/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/SEKKAIE/scourgify?display_name=tag&sort=semver)](https://github.com/SEKKAIE/scourgify/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-D4A017.svg)](./LICENSE)

</div>

<p align="center">
  <img src="./assets/scourgify-hero-v1.png" alt="一张严格四色像素画：魔法棒在黑暗中施展清洁魔法" width="860">
</p>

AI 编程很少在“代码跑通”时真正结束。它通常结束于这样的现场：源码改动旁边放着过期文档，生成文件混在真实工作里，却没有可靠记录说明什么该保留、验证、暂存、忽略，什么必须原样留下。

Scourgify 不追求表面上空无一物的 `git status`。它让范围内的仓库状态变得可理解，保护无关用户工作，并区分“账本结构已经完整”和“工作确实可以继续”这两件事。

## 快速开始

### 1. 安装

将经审阅的 `v1.1.0` 版本安装到 Codex skill 目录：

```bash
git clone --branch v1.1.0 --depth 1 \
  https://github.com/SEKKAIE/scourgify.git \
  ~/.codex/skills/scourgify
```

Windows PowerShell 请运行：

```powershell
git clone --branch v1.1.0 --depth 1 `
  https://github.com/SEKKAIE/scourgify.git `
  "$env:USERPROFILE\.codex\skills\scourgify"
```

内置扫描器与验证器需要 Python 3.10 或更高版本，以及 Git。

### 2. 验证 CLI

```bash
python3 ~/.codex/skills/scourgify/scripts/scourgify_scan.py --self-test
```

Windows PowerShell 请运行：

```powershell
py -3 "$env:USERPROFILE\.codex\skills\scourgify\scripts\scourgify_scan.py" --self-test
```

预期结果：

```text
self-test: ok
```

### 3. 调用

新建一个 Codex 任务，输入：

```text
使用 $scourgify 收尾这个脏仓库，对账每一条范围内路径，并报告仍需授权的事项。
```

### 4. 确认结果

第一次报告应当说明准确的仓库根目录、分支、上游、快照范围、候选文档与每一条范围内路径。它不应静默删除、还原、暂存、提交或推送任何内容。

完成的收尾应给出经过验证的 before/after/expected/ledger 数量。`complete: yes` 表示账本结构对账成功；如果仍有操作需要授权，`work ready: no` 依然是诚实且有效的结果。

## 工作方式

1. **确认范围。** 明确仓库、分支、上游、对象边界与允许执行的操作。
2. **冻结底稿。** 在目标仓库之外保存一份只依赖标准库、只读的 JSON 快照。
3. **先读本地规则。** 理解适用的指令与持久状态，再解释路径含义。
4. **建立账本。** 为每一条范围内路径记录归属、原因、下一步、证据与授权状态。
5. **只同步已经改变的事实。** 仅更新确实发生漂移的最小持久文档表面。
6. **安全验证。** 把发现的命令视为不可信候选项，并如实记录跳过的检查。
7. **机械对账。** 用账本验证前后快照的并集。
8. **完成交接。** 报告哪些工作已经就绪、哪些仍然脏，以及哪些准确的路径 ID 还需要决策。

| 账本字段 | 要回答的问题 |
| --- | --- |
| `owner` | 这是谁的工作？ |
| `reason` | 为什么路径会变脏或新出现？ |
| `next_action` | 下一步有边界的处置是什么？ |
| `evidence` | 什么测试、diff、规则或观察支持它？ |
| `permission` | 当前操作是否获得授权？ |

扫描器只提供第一轮分类。最终行动前，agent 仍需检查仓库规则、diff、证据与任务上下文。

## 完整示例

[`examples/worked-closeout`](./examples/worked-closeout/README.md) 包含一组人工合成的前后快照，以及一份完整的授权感知账本。

在仓库根目录运行：

```bash
python3 scripts/validate_closeout.py \
  --before examples/worked-closeout/before.json \
  --after examples/worked-closeout/after.json \
  --ledger examples/worked-closeout/ledger.json
```

预期摘要：before 有两条路径，after 有两条路径，并集包含三个稳定路径 ID；三个 ID 都恰好对应一条账本记录，验证器同时报告 `complete: yes` 与 `work ready: yes`。

## 范围与局限

- 确定性扫描器用于 Git 仓库。非 Git 回退只是一项单独限定范围的名称盘点，不能等同于经过验证的 Git 收尾。
- “每一条范围内路径”是指前后快照中非忽略路径的并集；只有前后两份快照都显式使用 `--include-ignored`，才会额外纳入忽略项元数据。
- 符号链接与 gitlink/子模块会被报告为对象边界；父仓库扫描不会检查其目标或嵌套内容。
- 分类是启发式判断。任何类别都不会自动授予删除、忽略、暂存、提交或推送的权限。
- 秘密文件内容不会被读取或复制到账本中，但快照仍包含仓库绝对路径、文件名等元数据；公开分享前，请清理私有路径与标识符。
- 建议的测试、构建或 lint 命令，在检查仓库指令与命令的准确定义之前，都只是不可信候选项。
- 有效账本只证明结构完成对账，不证明其中的证据真实，也不代表未决操作已经获得授权。

## 兼容性与证据

| 运行环境 | 与证据匹配的状态 |
| --- | --- |
| Codex | `v1.1.0` 的 skill 元数据与确定性 CLI 行为，已通过 skill 校验、扫描器自测、完整 unittest 套件和可运行示例验证。这不代表在每一个仓库上都能保证完全相同的模型行为。 |
| Claude Code | 仅目录与格式兼容：仓库遵循其文档所述的个人 Agent Skills 目录与顶层 `SKILL.md` 格式；不声称完成 live-host 冒烟测试。详见 [Claude Code skills 文档](https://code.claude.com/docs/en/skills)。 |
| Cursor | 仅目录与格式兼容：仓库遵循其文档所述的用户 Agent Skills 目录与顶层 `SKILL.md` 格式；不声称完成 live-host 冒烟测试。详见 [Cursor Agent Skills 文档](https://cursor.com/docs/skills)。 |

## CLI 参考

在克隆后的 skill 目录中运行人类可读报告：

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository
```

把 JSON 快照保存在目标仓库之外：

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository --format json > /tmp/scourgify-before.json
```

在不读取忽略文件内容的前提下，显式纳入忽略项元数据：

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository --include-ignored
```

验证完整的收尾包：

```bash
python3 scripts/validate_closeout.py \
  --before /tmp/scourgify-before.json \
  --after /tmp/scourgify-after.json \
  --ledger /tmp/scourgify-ledger.json
```

## 仓库结构

- [`SKILL.md`](./SKILL.md)：授权感知型收尾协议
- [`scripts/scourgify_scan.py`](./scripts/scourgify_scan.py)：只读的人类/JSON 仓库扫描器
- [`scripts/validate_closeout.py`](./scripts/validate_closeout.py)：确定性的快照与账本对账器
- [`agents/openai.yaml`](./agents/openai.yaml)：Codex skill 元数据
- [`references/closeout-ledger.md`](./references/closeout-ledger.md)：账本契约与模板
- [`references/repo-doc-patterns.md`](./references/repo-doc-patterns.md)：持久仓库文档的备用定位图
- [`examples/worked-closeout`](./examples/worked-closeout/README.md)：可运行的合成示例包
- [`evals/trigger-cases.json`](./evals/trigger-cases.json)：预期触发与不触发案例，不是行为基准测试结果
- [`tests`](./tests) 与 [`ci.yml`](./.github/workflows/ci.yml)：真实 Git fixtures 与跨平台验证矩阵

## 贡献与安全

本地验证命令与拉取请求要求见 [`CONTRIBUTING.md`](./CONTRIBUTING.md)。安全漏洞请按照 [`SECURITY.md`](./SECURITY.md) 中的流程私下报告；不要在公开 issue 中附上未清理的快照、账本、秘密信息或私有仓库材料。

## 许可证

[MIT](./LICENSE)

## 名称说明

Scourgify 是一个因清洁隐喻而命名的非官方项目；不声称获得任何关联或背书。
