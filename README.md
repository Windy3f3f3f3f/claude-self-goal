# claude-self-goal

简体中文 · [English](./README.en.md)

让正在运行的 Claude Code 会话给自己设一个原生 `/goal`——不用人敲，交互式、tmux、还是后台会话都能用。

> Claude Code 的 `/goal <条件>`(v2.1.139 起)会让会话一直干到某个条件满足才停，中途每次想收工都由一个独立的判定器检查条件到了没有。这条命令平时只能人手动敲；claude-self-goal 把同样一行字从程序里送进会话，于是一个自主 agent 能给自己定目标。

在 Claude Code v2.1.202、Linux 上验证通过。

## 它解决什么问题

设置原生 `/goal` 没有任何程序化入口——没有 hook 字段，没有 `settings.json` 选项，没有环境变量，没有命令行参数，也没有 API。hook 被明确设计成不能触发 slash 命令，而 `claude -p "/goal ..."` 在 v2.1.202 上会卡死。要让原生的 goal 机制真正转起来，唯一的办法是把 `/goal <条件>` 这行文字送进会话的输入，跟人手敲进去一模一样。

难点在于不同类型的会话，输入进去的通道不一样。claude-self-goal 会先认出你是哪种会话，再挑对的通道。

## 它怎么工作

它先顺着进程树往上找到**最近的**那个 Claude Code 进程——只认最近这一个，绝不越级到更上层的父会话——然后按它的类型自动选投递方式：

- 会话跑在 **tmux** 里：用 `tmux send-keys` 发到你的窗格，不需要 root；
- 会话是**普通交互式**（那个 pts 是它的控制终端）：用 `TIOCSTI` 把这行字塞进 pts，需要 root；
- 会话是 **daemon 托管的后台会话**（`claude --bg`、手机 remote 那套）：它的输入不走 pts、走一个 unix socket `rv/<会话id>.sock`，所以改用官方客户端 `claude attach <id>` 连上去注入；
- 会话是 **headless 的 `claude -p`**（标准输入是管道）：没有任何交互输入通道，直接拒绝。

选好通道后，会话把 `/goal <条件>` 当成普通输入收下，真正的 `/goal` 就生效了：右下角的 `◎ /goal active` 计时标、独立的完成判定、不到目标不收工。

## 快速上手

```bash
# 在 Claude Code 会话的 Bash 工具里（或一个 skill 里）。条件一定要用引号括起来：
claude-self-goal "所有测试通过，并且构建是绿的"

# 计划变了，提前清掉：
claude-self-goal --clear

# 只想看它会走哪条通道、先不真的注入：
claude-self-goal --dry-run "迁移已经完成"

# 给另一个后台会话设目标（一个调度者给 worker 下目标）：
claude-self-goal --session 994f658d "PR 的 CI 全绿"
```

## 安装

```bash
git clone https://github.com/Windy3f3f3f3f/claude-self-goal.git
cd claude-self-goal
sudo ln -s "$PWD/claude-self-goal" /usr/local/bin/claude-self-goal
```

需要 Python 3.6 以上和 Linux。tmux 那条路需要装 `tmux`；TIOCSTI 那条需要 root；attach 那条需要 `claude` 在 PATH 上。

## 当成 Claude Code skill 用

把 `skill/SKILL.md` 拷到 `~/.claude/skills/self-goal/SKILL.md`（把里面的可执行文件路径改成你的）。装好之后，模型一步就能调用它给自己设目标。细节见 [`skill/SKILL.md`](skill/SKILL.md)。

## 用法

| 命令 | 作用 |
|---|---|
| `claude-self-goal "<条件>"` | 给当前会话设一个原生 `/goal`（自动选通道） |
| `claude-self-goal --clear` | 清掉当前 goal（`/goal clear`） |
| `claude-self-goal --dry-run "<条件>"` | 只打印选中的通道和目标，什么都不注入 |
| `claude-self-goal --session <id> "<条件>"` | 给指定的 daemon 后台会话设目标（跨会话） |
| `claude-self-goal --method tmux\|tiocsti\|attach\|auto` | 强制某条通道（默认 `auto`） |
| `claude-self-goal --unsafe-pts /dev/pts/N ... --i-understand-this-can-inject-keystrokes` | 注入到指定 pts（危险，跳过自动发现，强制 tiocsti） |

退出码：`0` 成功，`2` 用法错误，`3` 没找到可注入的目标，`4` 非 root（tiocsti），`5` 注入失败，`6` 条件里有控制字符。

goal 条件会先过一道净化：任何控制字符（回车、换行、ESC 等）都会被拒，所以这行文字没法夹带第二条命令。命令行上的条件也**记得用引号括起来**——不然多词条件在 bash 里会被拆成多个参数、在 zsh 里行为还不一样。

设了环境变量 `CLAUDE_SELF_GOAL_DRY_RUN=1`，工具就只 dry-run、绝不注入——测试和 CI 用它当硬性保险。

## 需要什么、有哪些限制

只支持 Linux——发现靠 `/proc`，tiocsti 靠 Linux 的 `TIOCSTI` ioctl。TIOCSTI 那条需要 root（或 `CAP_SYS_ADMIN`，且内核/容器策略不拦），tmux 和 attach 那条不需要 root。headless 的 `claude -p`（标准输入是管道）没有交互输入通道，做不了。它还跟 Claude Code 当前的输入处理和 daemon 结构绑得比较紧（在 v2.1.202 上验证过），将来这些一变可能就失效。

## 安全

tiocsti 那条用到 `TIOCSTI`——一个内核默认收紧的特权键盘注入原语；attach 那条用的是官方客户端。两条都是"往会话注入输入"，都是给你在自己控制的机器上、自动化你自己的 Claude Code 会话用的，不适合多用户或共享主机，`--session` 也只该指向你自己的后台会话。用之前请先读 [`SECURITY.md`](SECURITY.md)。

## 深入原理

三类会话在终端/socket 上的拓扑差别、为什么 pts 注入对 daemon 会话无效、attach 怎么绕过、以及"只认最近祖先"为什么重要，都写在 [`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md)。

## 测试

```bash
./run-tests.sh                            # 发现 + 负例（是 root 再加 primitive）；bash/zsh/sh 都能跑
RUN_CLAUDE_INTEGRATION=1 ./run-tests.sh   # 再跑两条端到端集成（tiocsti 与 attach 路径，需要 claude + 额度）
```

## 许可证

MIT，见 [`LICENSE`](LICENSE)。
