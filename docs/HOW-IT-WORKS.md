# 它到底怎么工作

简体中文 · [English](./HOW-IT-WORKS.en.md)

## 目标是什么

Claude Code 的 `/goal <条件>`(v2.1.139 起)记下一个完成条件。此后每当会话想结束一轮、停下来，一个独立的判定器会检查条件到了没有；没到，就把模型打回去继续干，直到满足为止。右下角的 `◎ /goal active` 标示它正生效。goal 存在会话自己的 transcript 里，天生按会话隔离。

我们想让一个自主会话给自己设上这个，全程不用人打字。

## 为什么不能直接“调用”它

原生 goal 没有任何程序化入口。hook 不行——它的每个输入输出字段都写明了不会被当作 slash 命令解析。settings、环境变量、命令行、API 也都设不了它。而 `claude -p "/goal ..."` 在 v2.1.202 上会卡死，哪怕后面接了真任务也一样。

所以，要让原生的机制真正转起来，唯一的办法是把 `/goal <条件>` 这行文字送进会话的输入，跟人手敲进去没有区别。难的是不同会话，"输入"进去的路不一样。

## 三类会话，三条输入通道

普通交互式会话（含 tmux）：`claude` 进程从它的控制终端（一个 pts）读输入，标准输入和标准输出都指向这个 pts。往这个 pts 的输入队列里放东西，就会被当成有人在打字。tmux 会话也属这类，只是那个 pts 是 tmux 窗格的 pty。

daemon 托管的后台会话（`claude --bg` 起的、或手机 remote 那套）：结构不一样。一个 supervisor（Claude Code 自己的 pty-host）给会话分一对 pty，会话的输出写到那个 pts、被 pty-host 抓去转给查看端；但它的输入不从 pts 读，而是走一个 listening 的 unix socket `rv/<会话id>.sock`——`claude attach`、手机 remote 这些客户端连上这个 socket 把按键送进来。关键判据是这类会话的进程没有控制终端，`/proc/<pid>/stat` 里 tty_nr 为 0，那个 pts 只是它开着的一个 fd、不是控制终端。

headless 的 `claude -p`：标准输入是一个管道或 `/dev/null`，没有任何交互输入通道。

对应地，投递方式也是三条：

- 交互式在 tmux 里 → `tmux send-keys` 写窗格的 pty（不需要 root）;
- 交互式不在 tmux → `TIOCSTI` 把字节塞进那个 pts 的输入队列（需要 root）;
- daemon 后台会话 → `claude attach <id>` 连上 `rv/<id>.sock`，替我们讲 daemon 的协议把输入送进去;
- headless → 没辙，直接拒绝。

## 为什么 daemon 会话不能用 pts 注入

因为它的输入根本不从 pts 读。往 pts 塞字节的 `TIOCSTI` 在 syscall 层会"成功"，但那个缓冲没人当输入读，字节等于扔进死信箱。所以早期只做 pts 注入的版本，在 daemon 会话上会假报成功却毫无效果。区分这两类的办法就是看那个 pts 是不是进程的控制终端：是，才是活的交互输入；不是，就是 daemon 空壳。

## TIOCSTI 与 attach

`TIOCSTI`（terminal I/O control: simulate terminal input）是一个 ioctl，把一个字节塞进某个 tty 的输入队列、效果等同于有人敲了它。有 `CAP_SYS_ADMIN`（root）就能按路径打开一个 pts 直接这么做。现代内核把老式的、不需特权的 `TIOCSTI` 关掉（`dev.tty.legacy_tiocsti=0`，往往整个编译掉）正因为它是键盘注入原语；root 仍能用，但一层 seccomp、user namespace 或容器策略可以连 root 都拦下来。

daemon 会话那条不碰这个原语，走的是官方客户端 `claude attach <id>`。它本来就是连 `rv/<id>.sock`、按协议转发按键的东西——所以我们不用逆向那个协议，把它跑在一个无头 pty 里、把 `/goal <条件>` 打进去、再 detach（会话继续跑）就行。

## 怎么找对目标（失败即停，且只认最近的）

注入到错误的终端会很糟，所以发现这一步很严，而且有一条容易被忽略但很关键的规则：只分类进程树上最近的那个 Claude 祖先，绝不越级。

想象一个从交互式前台 Claude 里派生出来的后台会话：最近的 Claude 是那个后台会话（无控制终端），但更上层还有一个前台 Claude（有真的控制终端 pts）。要是发现逻辑一路往上扫、找"任意一个有控制终端的 Claude"，就会扫到那个前台父会话、把 `/goal` 注进别人的会话。所以工具只取最近的 Claude 祖先，然后就地判定它这一个：

- 它的标准输入和标准输出是同一个 pts、且那个 pts 是它的控制终端 → 交互式，走 pts；
- 否则，从它自有的、恰好一个的 listening `rv/<id>.sock` 读出会话 id → daemon，走 attach；
- 两样都不是 → headless 或认不出，拒绝。

会话 id 的读法：把这个 Claude 进程的 socket fd inode 拿去 `/proc/net/unix` 里映射成路径，挑那个 listening 的 `rv/<id>.sock`，取出 `<id>`。只认 listening、且要求恰好一个，0 个或多个都 fail-closed，免得选错会话。

## 净化与保险

注入的是 `/goal <条件>`，条件先被净化：任何控制字符都会被拒，所以它没法夹带第二个回车去提交一条后面跟着的命令。另外有一个硬保险：环境变量 `CLAUDE_SELF_GOAL_DRY_RUN=1` 一旦设上，工具只 dry-run、绝不注入——测试套件一律带着它，这样任何测试即使写错，也不可能往跑测试的那条活会话里误注入 goal。

## 怎么端到端验证的

两条集成测试（`test/test_integration.py` 和 `test/test_integration_daemon.py`）分别覆盖两条真注入路径：一条在一个私有 pty 上起真的交互式 `claude`、让它对自己 TIOCSTI 注入；另一条起一个一次性的 `claude --bg`（真 daemon 会话）、再用工具的 `--session` 经 attach 注入。成败都用一个副作用判定：原生 goal 必须驱动会话建出一个证明文件。两条都不碰跑测试的那条会话。
