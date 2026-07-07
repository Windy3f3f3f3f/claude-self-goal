# claude-self-goal

简体中文 · [English](./README.en.md)

让正在运行的 Claude Code 会话给自己设一个原生 `/goal`——不用人敲、不需要 tmux、也不走 `claude -p`,后台会话同样能用。

> Claude Code 的 `/goal <条件>`(v2.1.139 起)会让会话一直干到某个条件满足才停,中途每次想收工都由一个独立的判定器检查条件到了没有。这条命令平时只能人手动敲；claude-self-goal 把同样一行字从程序里送进会话，于是一个自主 agent 能给自己定目标。

在 Claude Code v2.1.202、Linux、root 下验证通过。

## 它解决什么问题

设置原生 `/goal` 没有任何程序化入口——没有 hook 字段，没有 `settings.json` 选项，没有环境变量，没有命令行参数，也没有 API。hook 被明确设计成不能触发 slash 命令，而 `claude -p "/goal ..."` 在 v2.1.202 上会卡死。要让原生的 goal 机制真正转起来，唯一的办法是把 `/goal <条件>` 这行文字送进会话的输入，跟人手敲进去一模一样。

如果会话跑在 tmux 里，这件事 `tmux send-keys` 就能做。难的是后台、不在 tmux 的会话——它根本没有一个窗格可以打字。claude-self-goal 把这两种情况都接上了。

## 它怎么工作

分两步。先顺着进程树往上找，定位到你所在的那个 Claude Code 进程，条件是它的标准输入和标准输出指向同一个 pts。这一步是“失败即停”的：找不到这样的 Claude 祖先进程，就直接拒绝，绝不会随便挑一个终端往里塞。找到之后，按环境自动选投递方式——在 tmux 里就用 `tmux send-keys` 发到你的窗格，不需要 root；不在 tmux 就用 `TIOCSTI` 把这行字塞进那个 pts，这条需要 root。

会话把它当成普通输入收下，于是真正的 `/goal` 生效：右下角的 `◎ /goal active` 计时标、独立的完成判定、以及不到目标不收工。要是你在会话正忙的时候设的，它会先排队，等当前这一轮结束再落地。

## 快速上手

```bash
# 在 Claude Code 会话的 Bash 工具里（或一个 skill 里）：
claude-self-goal "所有测试通过，并且构建是绿的"

# 计划变了，提前清掉：
claude-self-goal --clear

# 只想看看它会做什么，先不真的注入：
claude-self-goal --dry-run "迁移已经完成"
```

## 安装

```bash
git clone https://github.com/Windy3f3f3f3f/claude-self-goal.git
cd claude-self-goal
# 放进 PATH（用软链接，方便以后更新）：
sudo ln -s "$PWD/claude-self-goal" /usr/local/bin/claude-self-goal
```

需要 Python 3.6 以上和 Linux。tmux 那条路需要装 `tmux`；非 tmux 那条路需要 root（见“安全”一节）。

## 当成 Claude Code skill 用

把 `skill/SKILL.md` 拷到 `~/.claude/skills/self-goal/SKILL.md`（把里面的可执行文件路径改成你的）。装好之后，模型一步就能调用它给自己设目标。细节见 [`skill/SKILL.md`](skill/SKILL.md)。

## 用法

| 命令 | 作用 |
|---|---|
| `claude-self-goal "<条件>"` | 给当前会话设一个原生 `/goal` |
| `claude-self-goal --clear` | 清掉当前 goal（`/goal clear`） |
| `claude-self-goal --dry-run "<条件>"` | 只打印选中的方式和目标，什么都不注入 |
| `claude-self-goal --method tmux\|tiocsti\|auto` | 强制投递方式（默认 `auto`） |
| `claude-self-goal --unsafe-pts /dev/pts/N ... --i-understand-this-can-inject-keystrokes` | 注入到指定的 pts（危险，跳过自动发现） |

退出码：`0` 成功，`2` 用法错误，`3` 没找到 Claude 目标，`4` 非 root（tiocsti 路），`5` 注入失败，`6` 条件里有控制字符。

goal 条件会先过一道净化：任何控制字符（回车、换行、ESC 等）都会被拒，所以这行文字没法夹带第二条命令进会话。

## 需要什么、有哪些限制

只支持 Linux——自动发现靠 `/proc`，注入靠 Linux 的 `TIOCSTI`。非 tmux 那条路需要 root（或 `CAP_SYS_ADMIN`），tmux 那条不用。对着一个 headless 的 `claude -p` 会话不管用：它的标准输入是管道或 `/dev/null`，没有 pts 可以注入，而这种会话本来也跑不了交互式 `/goal`。它还跟 Claude Code 当前的输入处理绑得比较紧（在 v2.1.202 上验证过），将来界面或输入链路一变，可能就失效。

## 安全

这工具用到 `TIOCSTI`——一个内核默认收紧的“模拟键盘输入”特权操作。它是给你在自己控制的机器上、自动化你自己的 Claude Code 会话用的，不适合多用户或共享主机，也别拿去碰不属于你的会话。用之前请先读 [`SECURITY.md`](SECURITY.md)。

## 深入原理

交互式会话和后台会话在终端上的拓扑差别、为什么每一种“非注入”的办法都走不通、这套机制到底怎么成立，都写在 [`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md)。

## 以后想做的

给“新启动”的会话提供一条不需要 root 的路子：会话起来的时候就套一个小小的 pty 代理或 Unix socket wrapper，直接写 pty 的 master 端，从而绕开 `TIOCSTI`。这条覆盖不了已经在跑的会话（那正是现在这个版本管的事），但更安全、也更好移植。

## 测试

```bash
./run-tests.sh                            # 发现 + 负例（是 root 的话再加 primitive）
RUN_CLAUDE_INTEGRATION=1 ./run-tests.sh   # 再跑完整的端到端测试（需要 claude + root + 额度）
```

## 许可证

MIT，见 [`LICENSE`](LICENSE)。
