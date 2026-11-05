# 我自己的实验重做记录

这份文档用于已经配好环境的本人电脑，按 10 月实验时的终端截图、聊天中贴出的命令和当时的操作指南整理。覆盖正式作业 Task 1–5；保留原来的项目路径、启动方式和实验命令。

**不用重新安装、克隆项目或手动激活 Conda。** 原来的 `run_*.sh` 已指定本机 Ryu 环境。这份记录使用原项目 `sdn_assignment`，不是后来给搭档准备的 `publish/5101`。

命令逐条输入，不复制 `mininet>` 提示符。下面 `/tmp/` 日志名里的 `20261016` 沿用旧记录，只是文件名；再次执行会覆盖同名临时日志，已归档的历史实验结果仍在原项目目录里。

## 先记住两个窗口

- **终端 A：控制器。** 输入各节的 `bash ...` 命令，留着看 READY、BLOCK、LINK、ROUTE。
- **终端 B：MiniEdit 和 Mininet。** 打开 MiniEdit，点击 Run 后，回这个终端，在 `mininet>` 后输入测试命令。

### MiniEdit 从打开到开始实验

**1．终端 A 先启动本轮控制器。** 从下面对应任务选一条启动命令，例如正常基线使用 `run_baseline.sh`。只启动一个；`run_mesh_check.sh` 和 `run_baseline.sh` 属于不同轮次，不同时运行。如果本轮控制器已经启动，就保留窗口。

此时终端停在 `loading app` / `instantiating app` 附近、没有 READY，可以是在等待交换机连接。控制器不会替你打开 MiniEdit 或点击 Run，不能只在这个窗口一直等待。

**2．终端 B 打开 MiniEdit。** 使用以前的两条命令，逐条输入：

```bash
sudo service openvswitch-switch start
sudo miniedit
```

第一条启动虚拟交换机所需的 Open vSwitch 服务；第二条打开 MiniEdit 图形窗口。如果 MiniEdit 已打开，就沿用这个窗口。

**3．在 MiniEdit 图形窗口点击 File → Open。** 选择本人当时保存的文件：

```text
/home/robot/CEG5101/todo01/ca2-mesh-my.mn
```

打开后应看到 h1–h6、s1–s6 和 c0，以及已经连好的拓扑，无需重新画图。

**4．点击 Edit → Preferences。** 确认 **Start CLI** 已勾选，再确定关闭设置窗口。它让网络启动后，在终端 B 出现 `mininet>`，供我们输入 `net`、`pingall` 等命令。

**5．点击 MiniEdit 左下角 Run。** 这一步才真正创建虚拟主机、交换机和链路，并让交换机连接终端 A 的控制器。

**6．切回启动 MiniEdit 的终端 B。** 等待出现 `*** Starting CLI:` 和 `mininet>`。测试命令输入在这里，不是在控制器日志窗口里输入。

**7．按当前任务等待控制器就绪，再测试。** 正常基线等终端 A 出现 `BASELINE READY`；后续任务按各节的 READY 和预热要求执行。原 TODO1 连通性检查按下面记录等约 15 秒。然后在终端 B 逐条输入该任务的测试命令。

如果启动控制器后几分钟仍无 READY，先确认已经完成第 5 步 **Run**、终端 B 已出现 `mininet>`，并确认只启动了一个控制器。

### 换任务或结束实验

**换任务或重做一轮时，沿用原来的结束顺序：**

1. 终端 B 的 `mininet>` 输入 `exit`。
2. MiniEdit 点 **Stop**。
3. 终端 A 按 **Ctrl+C**，结束旧控制器。
4. 终端 A 启动下一节的控制器，再到 MiniEdit 点 **Run**。

这是结束上一轮实验、清掉上一轮封锁状态，不是重新安装环境。同一个端口只运行一个控制器。

## Task 1：打开原拓扑，检查全网互通（原 TODO1）

这一轮确认六台主机、六台交换机和保存的链路能正常工作。拓扑已经做好，直接打开保存的文件即可。

终端 A，沿用原指南中的工作目录和连通性检查入口：

```bash
CEGWORK="/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment"
cd "$CEGWORK"
bash "$CEGWORK/run_mesh_check.sh"
```

MiniEdit 点 **Run**，等约 15 秒供链路发现和流表安装。在终端 B 的 `mininet>` 逐条输入：

```text
net
pingall
h1 ping -c 5 -W 1 10.0.0.6
```

看什么：`net` 显示端口连线；`pingall` 检查所有主机互通，之前是 **30/30 received**；最后一条单独检查 h1→h6，之前是 **5 发 5 收**。保留完整拓扑和通信结果截图。

### `net` 里的 `eth0`、`eth1`、`eth2` 怎么读

它们是虚拟网络接口的名称编号，主机和交换机都有自己的接口。完整名称要一起看：`h1-eth0` 是 h1 的接口 0，`s1-eth2` 是 s1 的接口 2。**接口编号只属于本设备，不代表对面设备的编号。**

`net` 的每行先写设备名，随后用 `本端接口:对端接口` 列出连线。例如本人的实际输出：

| 输出片段 | 意思 |
|---|---|
| `h1 h1-eth0:s1-eth1` | h1 的接口 0 连接 s1 的接口 1 |
| `s1-eth2:s2-eth2` | s1 的接口 2 连接 s2 的接口 2 |
| `s1-eth3:s4-eth3` | s1 的接口 3 连接 s4 的接口 3；eth3 不代表 s3 |
| `s2-eth6:s6-eth4` | s2 的接口 6 连接 s6 的接口 4；链路两端编号不必相同 |

这张拓扑中，每台主机只接一条数据链路，所以 h1–h6 各只有一个这样的接口 `eth0`；交换机连接多台设备，所以有多个 `eth1`、`eth2` 等接口。本项目主机接口从 0 开始、交换机数据接口从 1 开始编号。

同一条连线会分别出现在两端设备的行里，不代表两条不同链路。`lo` 是本机回环接口，不是连接另一台主机或交换机的链路。这里的接口/交换机端口也与 iperf 的 UDP 端口 `5001` 是不同概念。

因此，流表中的 `actions=output:"s1-eth2"` 表示从 s1 的这个接口发出去；再结合 `net` 中的 `s1-eth2:s2-eth2`，才能知道下一跳是 s2。

## 正常路由和吞吐基线（原 TODO2）

这一轮记录没有异常时 h1→h6 走哪里、吞吐多少，供后面的异常实验比较。它是正式任务的准备步骤，不是额外的评分任务。

按前面的顺序结束旧轮次。终端 A：

```bash
bash "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/run_baseline.sh"
```

MiniEdit 点 **Run**，等终端 A 出现 **BASELINE READY**。终端 B 的 `mininet>`：

```text
pingall
h1 ping -c 5 -W 1 10.0.0.6
```

接着查看 h1→h6 在三台交换机上的输出端口：

```text
sh ovs-ofctl -O OpenFlow13 dump-flows s1 "ip,nw_src=10.0.0.1,nw_dst=10.0.0.6"
sh ovs-ofctl -O OpenFlow13 dump-flows s2 "ip,nw_src=10.0.0.1,nw_dst=10.0.0.6"
sh ovs-ofctl -O OpenFlow13 dump-flows s6 "ip,nw_src=10.0.0.1,nw_dst=10.0.0.6"
```

当时输出依次为 `s1-eth2`、`s2-eth6`、`s6-eth1`，结合 `net` 可还原 **h1→s1→s2→s6→h6**。交换机间基础代价是 **5+14=19**。

让 h6 接收数据，再让 h1 以 10 Mbps 发送 15 秒。接收端在这一轮只启动一次：

```text
h6 iperf -s -u -p 5001 -i 1 > /tmp/ceg5101-baseline-h6-20261016.log 2>&1 &
h1 iperf -c 10.0.0.6 -u -b 10000000 -t 15 -i 1 -p 5001
```

看末尾 **Server Report** 的接收吞吐和 `Lost/Total Datagrams`，当时约 10 Mbps、0% 丢包。截图保留 READY、流表输出和 Server Report；新一轮按实际结果记录。

## Task 2：检测异常源并封锁（原 TODO3）

这一轮看控制器能否区分正常低速通信与突发高率流量，并让合法 h1 继续通信。

**Task 2 仍然需要终端 A 和终端 B。** A 运行检测控制器，自动采集统计、维护 EMA、发现异常并下发封锁规则；B 运行 MiniEdit/Mininet，用来启动网络、产生流量和验证封锁。只启动 A 而不启动网络、发送流量，不能完成这个任务。

| 老师的要求 | 本轮由谁执行、看什么 |
|---|---|
| 用 ping 模拟正常流量、形成 EMA 基线 | B 执行 h2 的正常 ping；A 观察 pps、old_ema、new_ema、threshold |
| 用 hping3 产生异常流量 | B 执行下面原来的限时 ICMP flood；A 自动判断异常 |
| 检测后安装源 IP 防火墙规则 | A 的控制器通过 OpenFlow 自动向交换机下发源 IP drop 规则 |
| 验证异常流不再转发 | B 查看 s2 的 drop 规则及命中计数，再检查 h2 ping 被阻断、h1 ping 仍成功 |

这里“安装防火墙规则”指向交换机流表下发过滤规则。例如源为 h2 时，匹配 `ip,nw_src=10.0.0.2`，使用 `priority=5000` 和 `actions=drop`。现有代码向所有已连接交换机下发，h2 的流量首先在接入交换机 s2 被丢弃。这个动作由控制器自动完成；下面的 `dump-flows` 只是查看规则，不是安装规则。

结束旧轮次。终端 A：

```bash
bash "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/run_anomaly.sh"
```

终端 B 沿用前面已打开的 MiniEdit；若已关闭，按本文开头的 MiniEdit 步骤重新打开原拓扑。点 **Run**，等终端 A 出现 **BASELINE READY**、**DETECTION STARTED**，再等至少 **8 秒**预热。随后在终端 B 的 `mininet>` 输入正常流量命令：

```text
h2 ping -c 20 -i 0.5 -W 1 10.0.0.6
```

这让 h2 每秒发约 2 个请求。终端 A 应看到 `source=10.0.0.2` 的 `pps` 约 2、`blocked=False`。

接着执行当时的异常测试：先让 h1 持续 ping，再让本实验网络内的 h2 高速发包 8 秒：

```text
h1 ping -D -i 0.5 -W 1 10.0.0.6 > /tmp/ceg5101-todo03-h1-ping-20261016.log 2>&1 &
h2 timeout 8s hping3 -1 --flood 10.0.0.6 > /tmp/ceg5101-todo03-h2-flood-20261016.log 2>&1
```

其中 `-1` 与 `--icmp` 都表示 ICMP 模式，`--flood` 表示高速发包，`timeout 8s` 限定本轮发送 8 秒。控制器检测到异常时会自动封锁；8 秒后发包程序退出本身不能证明封锁成功，需要下面的规则和通信检查。

**原发包命令逐项解释：**

| 命令部分 | 做什么 |
|---|---|
| `h2` | Mininet 在虚拟主机 h2 的网络环境里执行后面的命令，流量从 h2 发出 |
| `timeout 8s` | 运行后面的程序，8 秒后终止本轮发包 |
| `hping3` | 构造并发送测试数据包的程序 |
| `-1` | 选择 ICMP 模式，与 `--icmp` 等价；这里发送回显请求 |
| `--flood` | 尽可能快地发包，使源速率大幅上升；没有指定固定 Mbps |
| `10.0.0.6` | 目标 IP，即 h6 |
| `> /tmp/ceg5101-todo03-h2-flood-20261016.log` | 将标准输出写入 Ubuntu 的这个日志文件；已有同名文件会被覆盖 |
| `2>&1` | 把标准错误（编号 2）也送到标准输出（编号 1）当前指向的日志文件 |

`2>&1` 中的 `&1` 表示引用输出通道 1，不是让程序后台运行。这条 flood 命令末尾没有单独的 `&`，所以终端 B 等待约 8 秒后返回提示符。相邻的 h1 ping 命令末尾有单独的 `&`，因此 h1 的合法流量在后台继续。

**控制器规则写在哪里：代码、下发消息、交换机流表是三个不同位置。**

| 文件和函数（原项目目录内） | 职责 |
|---|---|
| `run_anomaly.sh` | 启动 Ryu，加载 `anomaly_controller.py`；不产生异常流量 |
| `traffic_stats.py` → `FlowRates.sample()` | 用计数增量和实际时间间隔计算 pps/bps |
| `traffic_stats.py` → `SourceEMA.observe()` | 使用旧 EMA 和阈值判断，返回 `newly_blocked` |
| `anomaly_controller.py` → `AnomalyController.flow_stats()` | 收到交换机统计；发现 `newly_blocked` 后，对所有已连接交换机调用 `self.drop(dp, ip)` |
| `anomaly_controller.py` → `AnomalyController.drop()` | 构造 `OFPFlowMod`，再用 `dp.send_msg()` 发给交换机 |
| 各 Open vSwitch 交换机的流表 | 保存并执行收到的规则；日志文件不是规则生效的位置 |

`drop()` 在当前代码第 33 行开始：`priority=5000` 指定优先级，`eth_type=0x0800` 匹配 IPv4，`ipv4_src=ip` 匹配异常源。`OFPInstructionActions(..., [])` 使用空动作列表，同时没有输出或跳转下一表指令，因此匹配的包被丢弃。对 h2，交换机中显示为 `priority=5000,ip,nw_src=10.0.0.2 actions=drop`。

**控制器通过什么连接下发规则？**

MiniEdit 中 c0 的配置是远程控制器 `127.0.0.1:6653`。启动网络后，各 Open vSwitch 交换机会连接这个地址；终端 A 的 Ryu 正在这里监听 TCP。双方通过这条控制连接使用 OpenFlow 1.3 协议通信。图里的红色控制连接表示这种控制关系；h2→s2→s6→h6 则是承载实验数据包的路径。

可以把 OpenFlow 理解为控制器与交换机交换指令、统计的协议；`FlowMod` 是其中用于修改流表的消息。控制器下规则的具体过程是：

1. 交换机连接 Ryu 后，Ryu 为它建立一个 `Datapath` 对象，代码里简称 `dp`；这个对象关联该交换机的控制连接。
2. 控制器约每秒通过控制连接发送 `OFPFlowStatsRequest`，交换机返回统计回复和累计计数。控制器据此计算 h2 的速率，交给 EMA 检测器；正常业务包本身由交换机转发，不需要逐包经过控制器来计数。
3. 检测器判定 `10.0.0.2` 超阈值后，`flow_stats()` 对所有已连接交换机调用 `drop(dp, ip)`，构造 `OFPFlowMod` 消息。这里的 `ip` 就是 `10.0.0.2`。
4. `dp.send_msg()` 将消息序列化为 OpenFlow 字节，Ryu 的发送过程通过该 TCP 连接发送。交换机收到 FlowMod，解析其中的优先级、匹配条件和动作，在自己的流表中安装条目。随后由交换机直接处理匹配的数据包。

**为什么 h2→h6 会被封锁？沿一个实际请求包看：**

正常时，请求的源 IP 为 `10.0.0.2`，目的 IP 为 `10.0.0.6`，沿 `h2-eth0 → s2-eth1` 进入 s2。原来的 ICMP 请求规则把它从 `s2-eth6` 发到 s6，再由 s6 送到 h6，路径是 h2→s2→s6→h6。

封锁规则装好后，s2 的 table 0 中同时保留以下两类规则，与你原来的实际流表一致：

| 规则 | 匹配条件 | 对该请求的动作 |
|---|---|---|
| 原转发规则，priority 110 | ICMP 请求，源 `10.0.0.2`，目的 `10.0.0.6` | 从 `s2-eth6` 发给 s6 |
| 新封锁规则，priority 5000 | IPv4，源 `10.0.0.2`；目的地址不限 | drop，不从任何数据接口发出 |

这个 h2 请求同时满足两条规则，交换机选择**优先级更高的 5000**。因此它在 s2 被丢弃，既不到 s6，也不到 h6；h6 没收到该请求，就不会返回对应的 ping 回复，所以 h2 后续 ping 显示 0/3。

h1→h6 请求的源 IP 是 `10.0.0.1`，不满足封锁规则的 `源=10.0.0.2`，仍匹配自己的正常转发规则，所以此前 h1 后续 ping 为 3/3。**被封的是 h2 发出的 IPv4 流量，目的地址不限；不是断开 s2–s6 链路，也不是封锁 h6。** 其他源仍可使用这条链路访问 h6。

检测和下发需要时间，规则生效前部分异常包可能已经通过。你原来的截图同时有旧转发规则计数 44190 和新 drop 规则计数 478615；旧计数不会因封锁被清零。下一步 `dump-flows` 检查实际规则及丢弃计数，后续 ping 检查生效后的结果，不能仅凭控制器打印 BLOCK 就认定全部异常包从未被转发。

发包结束后，查看封锁规则并分别测试 h2、h1：

```text
sh ovs-ofctl -O OpenFlow13 dump-flows s2 "ip,nw_src=10.0.0.2"
h2 ping -c 3 -W 1 10.0.0.6
h1 ping -c 3 -W 1 10.0.0.6
```

看什么：控制器的 **BLOCK**；流表的 **priority=5000、actions=drop** 和非零计数；h2 被封锁，h1 仍通。当时分别是 h2 **0/3**、h1 **3/3**。保留这些截图。后台 h1 ping 会继续运行，完成后按前面的顺序结束本轮网络。

## Task 3：看链路代价随负载与异常变化（原 TODO4）

这一轮先验证代价计算，转发仍沿用静态路径。真正自动改道在下一节。

结束旧轮次。终端 A：

```bash
bash "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/run_costs.sh"
```

MiniEdit 点 **Run**。等 **COST MONITOR READY**，再等至少 **8 秒**。先看空闲的 `LINK s2->s6`：`base=14`、`penalty=0`、`cost` 约 14。

终端 B 的 `mininet>`，先做当时的 15 秒正常流量测试：

```text
h6 iperf -s -u -p 5001 -i 1 > /tmp/ceg5101-todo04-h6-20261016.log 2>&1 &
h1 iperf -c 10.0.0.6 -u -b 10000000 -t 15 -i 1 -p 5001
```

发送时看终端 A：负载项上升，`cost` 约 **15.3**，`penalty` 仍为 0。

保留这个网络和 h6 接收端，沿用当时的两条命令，连续执行：

```text
h1 iperf -c 10.0.0.6 -u -b 10000000 -t 60 -i 1 -p 5001 > /tmp/ceg5101-todo04-h1-continuous-20261016.log 2>&1 &
h2 timeout 8s hping3 -1 --flood 10.0.0.6 > /tmp/ceg5101-todo04-h2-flood-20261016.log 2>&1
```

观察 **BLOCK** 和 `penalty=60`：代价升至约 75–77。异常停止后让 h2 保持静默，等惩罚解除；h1 仍发送时代价约 15.3，h1 也结束后约 14。

终端 B 等 h1 完成，再读汇总：

```text
h1 wait
h1 tail -n 8 /tmp/ceg5101-todo04-h1-continuous-20261016.log
```

保留惩罚生效、解除的 LINK 行和 Server Report。当时 60 秒接收约 **9.99 Mbps**，丢包 **44/51024**；这是整轮汇总。

## Task 4：三种异常下的合法流量改道（原 TODO5）

沿用当时顺序，先 B，再 A、C。每个场景重新结束旧轮次、启动新控制器，避免继承已封锁源的状态。

### B：异常经过 s2–s6，观察实际改道

终端 A：

```bash
bash "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/run_rerouting.sh" B
```

MiniEdit 点 **Run**，等 **REROUTING READY**，再等至少 **8 秒**。终端 B 的 `mininet>` 输入当时截图里的三行：

```text
py __import__('sys').path.insert(0, "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment")
py __import__('importlib').reload(__import__('verify_rerouting'))
py __import__('student_task4_experiment').run(net)
```

第一行让 Python 找到原项目；第二行重新加载实验模块，是当时修正检查器后用过的命令；第三行在当前网络上运行完整实验。

程序自动完成：**0–12 秒正常流量 → 12–26 秒加入异常 → 随后观察恢复**，合法 h1→h6 流量持续约 60 秒。等待最终汇总，不用另外手动启动 iperf 或 flood。

保留控制器 **BLOCK、ROUTE** 和实验结束的 **PASS、Actual paths、吞吐/丢包** 截图。之前 B 的路径是：

```text
[1, 2, 6] → [1, 2, 3, 6] → [1, 2, 6]
```

### A、C：使用同一套操作，只更换场景

按原 Task 4 指南，把启动命令最后的 B 分别改为 A、C。每次都先 `exit` → MiniEdit **Stop** → 旧控制器 **Ctrl+C**。

A 的终端 A 命令：

```bash
bash "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/run_rerouting.sh" A
```

C 的终端 A 命令：

```bash
bash "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/run_rerouting.sh" C
```

**一次只运行一个场景。** 每次 Run、等 READY 和预热，再执行 B 小节的三行 `py` 命令。

| 场景 | 程序产生的异常流 | 观察的链路 | 之前 h1→h6 的结果 |
|---|---|---|---|
| A | h2→h3 | s2→s3 | 保持 `[1, 2, 6]` |
| B | h2→h6 | s2→s6 | 改到 `[1, 2, 3, 6]`，之后恢复 |
| C | h5→h6 | s5→s6 | 保持 `[1, 2, 6]` |

A、C 的异常链路不在合法流原路径上，保持原路符合当时结果。**C 沿用原实验设置：只把 h5→h6 测试对固定经过 s5→s6**；其自然最短路是 s5→s3→s6。演示时需说明，教师/TA 是否接受仍待确认。

每轮输出目录会打印在终端，位于原项目的 `todo05/run-场景-时间-随机后缀`，其中保存 `results.json`、`receiver.log`、`continuous-ping.log`、`events.jsonl` 和 `dataplane-samples.jsonl`。记录实际目录即可。

## Task 5：使用三场景数据做性能评价（原 TODO6）

你当时亲自做的补测，就是把 **B 场景再独立跑两轮**，累计三轮 B。每轮按上一节结束旧实验、运行同一条 B 启动命令、Run 和预热，再执行相同三行 `py` 命令。没有另外一套 Task 5 发包命令。

三类曲线是：**归一化链路代价、接收端丢包率、接收吞吐随时间变化**。当时由助手读取实验日志整理和绘图，不是你在终端又手动执行了一套新命令。

原来的最终图表和分析在 Windows 文件夹：

```text
D:\desktop\nus\CEG5101 Modern Computer Networking\sdn_assignment\todo06\task5-final-20261017
```

完整中英文报告在：

```text
D:\desktop\nus\CEG5101 Modern Computer Networking\sdn_assignment\report\review-20261105
```

这里的 2026-11-05 报告新增六张多链路策略图，两版各 24 页；第 5 页仍解释从发包到封锁。此前报告与原实验数据保留。现场讲已有结果可以直接打开这些文件。**新跑出的实验不会自动改写旧图表**；如果要用新数据更新图，需按新输出目录另做分析。

## 这些命令从哪里来

- Task 1 启动入口：原 `TODO01_GUIDE.md` 和原项目 `README.md`；通信命令也见本人当时截图。
- 正常基线、Task 2、Task 3：本人 2026-10-16 的终端截图和贴出的命令；对应 `TODO02_GUIDE.md`、`TODO03_GUIDE.md`、`TODO04_GUIDE.md`。
- Task 4：原 `TASK4_GUIDE.md` 的 B 启动及 A/C 参数切换；三行 `py` 来自本人 A/C/B 补测截图。
- Task 5：本人 2026-10-17 两次 B 补测截图及原 `TASK5_GUIDE.md`。
