# Task 3：动态链路代价与恢复

[返回完整指南](REPRODUCE.md) · [上一任务](TASK2_DETECTION.md) · [下一任务](TASK4_REROUTING.md)

## 1. 老师要求什么

对每条交换机间链路，根据当前流量负载和异常状态计算动态路由代价；拥塞/受异常影响的链路代价提高，使后续选路更倾向其他链路。可从教师 Reference C 的公式出发，也允许提出考虑负载和异常的替代形式（10 分）。

## 2. 我们做了什么，为什么

dynamic_cost_controller.py 继承检测和封锁功能；link_costs.py 计算 **22 条有向边** 的速率、代价和惩罚恢复。终端常打印 s2→s6 只是为了观察本次测试，不是只计算这一条链路。完整值在 cost-state.json 的 links 中。

$$R_{ij}(t)=\frac{8\Delta B^{rx}_{j\leftarrow i}}{\Delta t},\quad
U_{ij}(t)=\mathrm{clip}\left(\frac{R_{ij}(t)}{40\times10^6},0,1\right),\quad
C_{ij}(t)=C^0_{ij}+5U_{ij}(t)+60A_{ij}(t).$$

| 量 | 含义与实现理由 |
|---|---|
| R | 以对端入口 rx_bytes 差分计算到达 bit/s；源端 tx 也记录供核对，避免把进入出口队列都当成到达 |
| U | 到达速率 / 40Mbps，在代价计算中限制到 0–1；保留原始速率 |
| C0 | 原拓扑对应边的延迟数值，保持不变 |
| 5U | 正常负载越大，链路略贵 |
| 60A | 已检测异常路径上的方向受惩罚时加 60；不会让所有边一起加 60 |

这是选路评分，**加 60 不代表把 tc 延迟调高 60ms**。负载系数 5、惩罚 60 是项目参数，不是老师指定的最优值。

封锁后，攻击包不再到达后面的链路，R 很快下降，但源仍可能在拼命发包。因此继续读取入口 drop 计数判断活动：惩罚至少保持 8 秒，并且入口连续 5 秒没有丢弃活动才恢复；源统计过期不能当作静默。**恢复代价不解除源 IP 封锁。**

本页使用 h2→h6，其路径为 s2→s6，因此这次只给该有向边加异常惩罚。s6→s2 是另一个方向；其他正常链路也在计算自己的负载项。本阶段保留静态转发规则，Task 4 才会把代价应用到实际改道。

## 3. 完整启动

结束旧网络及控制器后，**终端 C：**

~~~bash
cd "$HOME/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
mkdir -p local-validation
CEG_CONSOLE="$(mktemp "$PWD/local-validation/task3-controller-XXXXXX.log")"
bash run_costs.sh 2>&1 | tee "$CEG_CONSOLE"
~~~

**终端 M：**

~~~bash
cd "$HOME/5101"
sudo service openvswitch-switch start
mkdir -p local-validation
export CEG_EVIDENCE="$(mktemp -d "$PWD/local-validation/task3-manual-XXXXXX")"
printf '%s\n' "$CEG_EVIDENCE"
sudo --preserve-env=CEG_EVIDENCE bash run_miniedit.sh
~~~

MiniEdit Open todo01/ca2-mesh-my.mn → Run。等 COST MONITOR READY，再等至少 8 秒完成预热。控制器新目录为 todo04/run-*。

## 4. 实验一：空闲与正常负载

先看终端 C：s2→s6 的 base=14、penalty=0、cost≈14。少量 LLDP 等控制流量可能使速率不严格等于零。

**截图 1：**就绪和空闲 LINK 行。

在 **mininet>** 启动一个 h6 接收端，然后发 15 秒正常 UDP：

~~~text
h6 iperf -s -u -p 5001 -i 1 -f m > "$CEG_EVIDENCE/receiver.log" 2>&1 & echo $! > "$CEG_EVIDENCE/receiver.pid"
h1 iperf -c 10.0.0.6 -u -b 10000000 -t 15 -i 1 -p 5001 -f m > "$CEG_EVIDENCE/normal-sender.log" 2>&1
h1 tail -n 10 "$CEG_EVIDENCE/normal-sender.log"
~~~

发送时看 LINK：R 约 10Mbps，U 约 0.25，负载项约 1.25，cost 约 15.25，penalty 仍为 0。端口字节计数含协议头，数值可以略高于应用层的 10Mbps。发送停止后，cost 逐步回到约 14。

**截图 2：**正常发送期间 LINK 行和接收汇总。此时先不要停止 h6 接收端，下一实验复用它。

## 5. 实验二：正常流持续时加入异常，再观察恢复

以下命令在 **mininet>** 连续执行。先读完，避免在正常流结束后才开始异常：

~~~text
h1 iperf -c 10.0.0.6 -u -b 10000000 -t 60 -i 1 -p 5001 -f m > "$CEG_EVIDENCE/continuous-sender.log" 2>&1 &
sh sleep 10
h2 timeout 8s hping3 -1 --flood 10.0.0.6 > "$CEG_EVIDENCE/flood.log" 2>&1
sh ovs-ofctl -O OpenFlow13 dump-flows s2 "ip,nw_src=10.0.0.2" > "$CEG_EVIDENCE/s2-block.txt"
sh sleep 15
sh ovs-ofctl -O OpenFlow13 dump-flows s2 "ip,nw_src=10.0.0.1,nw_dst=10.0.0.6"
h1 wait
h1 tail -n 10 "$CEG_EVIDENCE/continuous-sender.log"
~~~

这里为便于人工观察，先给正常流约 10 秒，再引入 8 秒异常。它是 Task 3 分阶段演示，不与 Task 4 的“12 秒开始、14 秒异常”测量混为同一试验。

你应看到以下过程：

| 阶段 | s2→s6 预期现象 | 解释 |
|---|---|---|
| 正常 UDP | cost 约 15.3，penalty=0 | 基础代价 14 + 实测负载项 |
| 检测并封锁 h2 | BLOCK；penalty=60；cost 约 75–79 | 受异常影响的边变贵 |
| 封锁后仍在 flood | 接收负载下降，drop_pps 仍可很大；惩罚保持 | 入口阻断不等于源停止 |
| h2 停止且满足恢复条件 | penalty=0；若 h1 仍发，cost 约 15.3 | 只去掉异常惩罚，正常负载项还在 |
| h1 也结束 | cost 约 14 | 回到空闲基础代价附近 |

**截图 3、4：**分别保存 penalty=60 的 LINK 和恢复 penalty=0 的 LINK；保存 Server Report 与 drop 规则。等待恢复时让 h2 保持静默，不要 ping h2 的目标，因为被封锁源的新包也会增加 drop 计数并重激活惩罚。

原 Task 3 60 秒实验收到约 9.99Mbps、44/51024 丢包；这是整轮统计，不能当成仅 8 秒异常窗口的吞吐/丢包。本次新机器测量请保留自己的结果。

## 6. 核对所有方向及结束

在终端 O 的 Ubuntu shell 中，把下面路径替换为终端 C 打印的本轮目录：

~~~bash
cd "$HOME/5101"
export CEG_RUN="$PWD/todo04/run-这里替换为本轮目录名"
/usr/bin/python3 -m json.tool "$CEG_RUN/cost-state.json"
~~~

应该有 22 个方向；base、received_bps、utilization、load_term、penalty、cost 能解释每条边的成本。link-costs.jsonl 保留完整时间序列，events.jsonl 记录 penalty_added / penalty_restored / penalty_reactivated，source-rates.jsonl 记录源与 drop 速率。观察 s2→s6 的日志不意味着其他边没有计算。

在 **mininet>** 停止本轮接收端：

~~~text
h6 kill -INT "$(cat "$CEG_EVIDENCE/receiver.pid")"
h6 tail -n 15 "$CEG_EVIDENCE/receiver.log"
exit
~~~

MiniEdit Stop 并关闭 → 终端 C Ctrl+C，开始 [Task 4](TASK4_REROUTING.md)。

本任务完成的证据是**实测负载变化、异常惩罚、恢复条件和完整代价记录**。只看 cost 增加不能证明路径改变；Task 3 的静态路径仍为 1→2→6 正是此阶段的预期。
