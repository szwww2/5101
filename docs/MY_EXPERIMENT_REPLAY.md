# 我自己的实验重做记录

这份文档用于已经配好环境的本人电脑，按 10 月实验时的终端截图、聊天中贴出的命令和当时的操作指南整理。覆盖正式作业 Task 1–5；保留原来的项目路径、启动方式和实验命令。

**不用重新安装、克隆项目或手动激活 Conda。** 原来的 `run_*.sh` 已指定本机 Ryu 环境。这份记录使用原项目 `sdn_assignment`，不是后来给搭档准备的 `publish/5101`。

命令逐条输入，不复制 `mininet>` 提示符。下面 `/tmp/` 日志名里的 `20261016` 沿用旧记录，只是文件名；再次执行会覆盖同名临时日志，已归档的历史实验结果仍在原项目目录里。

## 先记住两个窗口

- **终端 A：控制器。** 输入各节的 `bash ...` 命令，留着看 READY、BLOCK、LINK、ROUTE。
- **终端 B：MiniEdit 和 Mininet。** 打开 MiniEdit，点击 Run 后，回这个终端，在 `mininet>` 后输入测试命令。

MiniEdit 关掉后，在终端 B 用以前的命令打开：

```bash
sudo service openvswitch-switch start
sudo miniedit
```

File → Open，打开本人当时保存的文件：

```text
/home/robot/CEG5101/todo01/ca2-mesh-my.mn
```

确认 Edit → Preferences 中勾选 **Start CLI**。先启动本轮控制器，再点 MiniEdit **Run**。如果窗口已经打开，就沿用它。

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

结束旧轮次。终端 A：

```bash
bash "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/run_anomaly.sh"
```

MiniEdit 点 **Run**。等 **BASELINE READY**、**DETECTION STARTED** 出现，再等至少 **8 秒**预热。终端 B 的 `mininet>`：

```text
h2 ping -c 20 -i 0.5 -W 1 10.0.0.6
```

这让 h2 每秒发约 2 个请求。终端 A 应看到 `source=10.0.0.2` 的 `pps` 约 2、`blocked=False`。

接着执行当时的异常测试：先让 h1 持续 ping，再让本实验网络内的 h2 高速发包 8 秒：

```text
h1 ping -D -i 0.5 -W 1 10.0.0.6 > /tmp/ceg5101-todo03-h1-ping-20261016.log 2>&1 &
h2 timeout 8s hping3 -1 --flood 10.0.0.6 > /tmp/ceg5101-todo03-h2-flood-20261016.log 2>&1
```

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
D:\desktop\nus\CEG5101 Modern Computer Networking\sdn_assignment\report\review-20261017
```

现场讲已有结果可以直接打开这些文件。**新跑出的实验不会自动改写旧图表**；如果要用新数据更新图，需按新输出目录另做分析。

## 这些命令从哪里来

- Task 1 启动入口：原 `TODO01_GUIDE.md` 和原项目 `README.md`；通信命令也见本人当时截图。
- 正常基线、Task 2、Task 3：本人 2026-10-16 的终端截图和贴出的命令；对应 `TODO02_GUIDE.md`、`TODO03_GUIDE.md`、`TODO04_GUIDE.md`。
- Task 4：原 `TASK4_GUIDE.md` 的 B 启动及 A/C 参数切换；三行 `py` 来自本人 A/C/B 补测截图。
- Task 5：本人 2026-10-17 两次 B 补测截图及原 `TASK5_GUIDE.md`。
