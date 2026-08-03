<div align="center">

# Scourgify

### 清理一新

**AI 编程结束后，把脏乱工作区安全交接。**

*在暂存、删除或移交之前，先弄清每一条变更。*

[English](./README.md) · [简体中文](./README.zh-CN.md)

[![Codex](https://img.shields.io/badge/Codex-111827?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/codex/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-D97757?style=for-the-badge)](https://code.claude.com/)
[![Cursor](https://img.shields.io/badge/Cursor-111111?style=for-the-badge)](https://cursor.com/)
![协议](https://img.shields.io/badge/协议-保守收尾-2F6FED?style=for-the-badge)
![扫描器](https://img.shields.io/badge/扫描器-只读-6D28D9?style=for-the-badge)
![许可证](https://img.shields.io/badge/许可证-MIT-D4A017?style=for-the-badge)

**面向 Codex、Claude Code、Cursor，以及每一次需要认真完成的交接。**

</div>

<p align="center">
  <img src="./assets/scourgify-hero-v1.png" alt="一张严格四色像素画：魔法棒在黑暗中施展清洁魔法" width="100%">
</p>

---

AI 编程很少在“代码跑通”时真正结束。它通常结束于一个脏乱工作树：源码改动旁边放着过期文档，生成文件混在真实工作里，没有可靠记录说明什么该保留、验证、暂存、忽略，什么必须原样留下。

Scourgify 不追求表面上空无一物的 `git status`。它要让仓库状态变得可理解：每一条变更都有归属、原因、下一步和证据。

## 它做什么

1. **先勘察仓库**：用一个零依赖、只读的扫描器建立事实底稿。
2. **先读本地规则**：理解仓库约定后，再判断每条路径意味着什么。
3. **分类每一条脏路径**：不会把生成产物、秘密文件和用户工作混为一谈。
4. **只同步已经改变的事实**：不会因为文档存在，就把所有文档重写一遍。
5. **如实记录验证**：包括跳过了哪些检查，以及为什么跳过。
6. **留下有边界的交接**：给开发者、下一个 agent、下一次提交或拉取请求。

## 收尾账本

行动前，Scourgify 会让每一条变更回答同一组问题：

| 字段 | 要回答的问题 | 常见取值 |
| --- | --- | --- |
| 归属 | 这是谁的工作？ | 当前任务、用户、另一个 agent、未知 |
| 原因 | 为什么会变脏？ | 实现、文档同步、生成产物、验证证据 |
| 下一步 | 接下来应该怎样处理？ | 保留、检查、忽略、移除、暂存、询问 |
| 证据 | 什么支持这个判断？ | diff、测试、构建、截图、仓库规则 |
| 授权 | 当前是否有权执行？ | 可以执行、需要审核、需要用户批准 |

扫描器只提供第一轮分类。最终行动前，agent 仍需检查仓库规则、diff 与当前任务上下文。

## 适合什么时候用

- AI 编程看似结束，但工作树还需要一次可信的收尾。
- 代码、文档、生成产物和验证证据可能已经互相脱节。
- 工作跨过多个聊天或 agent，需要在仓库里留下一个持久交接。
- 你希望为下一次提交或拉取请求划出安全边界。

## 不适合什么时候用

- 你真正需要的是重构、格式化或通用代码清理，而不是任务收尾。
- 你期待工具自动删除或暂存所有脏路径。
- 当前任务工作与无关用户工作还无法区分。

## 如何开始

```text
Scourgify!
```

也可以明确说：

```text
使用 $scourgify 审核这个仓库，同步关键文档，验证工作，并报告剩余脏文件。
```

skill 会先检查、再行动。破坏性清理、广泛暂存、提交与推送都不在默认边界内。

## 它不会做什么

- 不会读取或打印秘密文件的内容。
- 不会在脏仓库里使用宽泛的 `git add .`。
- 不会静默还原、删除、覆盖、暂存或提交无关用户工作。
- 除非真正更新了持久的事实来源，否则不会声称聊天或文档已经同步。

## 扫描器

在克隆后的 skill 目录中运行只读仓库扫描：

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository
```

运行自测：

```bash
python3 scripts/scourgify_scan.py --self-test
```

在 Windows 上，请用 `py -3` 替代 `python3`。

## 包含内容

- `SKILL.md`：保守的仓库收尾协议
- `scripts/scourgify_scan.py`：零依赖的仓库扫描器与自测
- `references/repo-doc-patterns.md`：事实来源文档的备用定位图
- `agents/openai.yaml`：Codex skill 元数据

## 安装

使用 Skills installer：

```bash
npx skills@latest add SEKKAIE/scourgify -g -a codex --copy --full-depth
```

或者直接克隆：

```bash
git clone https://github.com/SEKKAIE/scourgify.git ~/.codex/skills/scourgify
```

安装后新建一个 Codex 聊天，让 skill 列表重新加载。

## 名称说明

本项目只借用了“清洁魔法”的比喻，与 Harry Potter、Wizarding World、Warner Bros. Discovery 或 J.K. Rowling 没有关联。[HarryPotter.com](https://www.harrypotter.com/features/every-spell-we-wish-we-could-use-for-spring-cleaning-season) 将 `Scourgify` 用作清洁魔法的名称；由粉丝维护的 Harry Potter Wiki 将 [Scouring Charm](https://harrypotter.fandom.com/wiki/Scouring_Charm) 的咒语列为 `Scourgify`，其[简体中文页面](https://harrypotter.fandom.com/zh/wiki/%E9%99%A4%E5%9E%A2%E5%92%92)则列出 `清理一新` / `除垢咒`。
