# Task 1：MiniEdit 拓扑与正常通信基线

[返回完整指南](REPRODUCE.md) · [下一步：Task 2](TASK2_DETECTION.md)

## 1. 老师要求什么

使用提供的 ceg_mesh_topo.py，在 MiniEdit 中创建并运行拓扑（5 分）。这里先复现已经按教师拓扑保存的文件，再核对参数与真实端口。正常路径和吞吐基线是后面 Task 4 比较的准备，不额外虚构一个评分任务。

## 2. 我们做了什么，为什么

保存了 [ca2-mesh-my.mn](../todo01/ca2-mesh-my.mn)：6 台主机、6 台交换机、1 个远程控制器。**17 条数据链路 = 6 条主机接入链路 + 11 条交换机间链路**。图上的红色控制器连接表示控制关系，不计入数据链路数。

| 对象 | 设置 | 用途 |
|---|---|---|
| h1–h6 | IP 10.0.0.1/24 到 10.0.0.6/24；MAC 最后一字节 01–06 | 固定主机身份，与控制器主机表一致 |
| s1–s6 | DPID 0000000000000001 到 0000000000000006 | Ryu 用 DPID 识别是哪台交换机 |
| c0 | Remote，127.0.0.1:6653 | OVS 连接本机 Ryu |
| OVS | OpenFlow 1.3 | 与控制器使用的协议版本一致 |
| 全部数据链路 | Bandwidth=40 Mbps | 用 Linux tc 限定容量，也是利用率的参考容量 |
| 每条 hi–si | Delay=15ms | 模拟主机接入延迟 |

11 条交换机链路的延迟与基础选路代价如下。基础代价采用相同数值；后续代价增加是改变选路评分，不是修改真实延迟。

| 链路 | 延迟 / 基础代价 | 链路 | 延迟 / 基础代价 |
|---|---:|---|---:|
| s1–s2 | 5ms / 5 | s2–s3 | 10ms / 10 |
| s4–s5 | 15ms / 15 | s5–s6 | 20ms / 20 |
| s1–s4 | 8ms / 8 | s2–s5 | 12ms / 12 |
| s3–s6 | 7ms / 7 | s1–s5 | 18ms / 18 |
| s2–s4 | 6ms / 6 | s2–s6 | 14ms / 14 |
| s3–s5 | 9ms / 9 | | |

baseline_controller.py 使用 LLDP 发现交换机链路，结合固定主机接入表、代理 ARP 和 Dijkstra 下发正常转发规则。采用代理 ARP 是为了避免有环 mesh 中无约束广播；本版不实现任意新主机发现。

原 h1→h6 路线是 **h1–s1–s2–s6–h6**，交换机路径成本为 5+14=19。备选 s1–s2–s3–s6 为 5+10+7=22。这里的路径成本没有把两条主机链路计入，但 ping RTT 包含实际经过的主机链路、往返和系统开销，所以不会等于 19ms。

## 3. 如何在 MiniEdit 里设置这些内容

复现直接 File → Open 本仓库的 todo01/ca2-mesh-my.mn，参数已经保存。可以右键查看属性，理解它们如何生效：

1. 主机 Properties 的 IP Address；Start Command 中的 ip link set dev h1-eth0 address 00:00:00:00:00:01 固定 MAC，其他主机对应改数字。
2. 交换机 Properties 的 DPID；交换机类型使用 OpenFlow/OVS，不能换成不受控制器管理的普通转发设备。
3. c0 属性：Controller Type=Remote，地址和端口如上。
4. Edit → Preferences：勾选 OpenFlow 1.3 和 Start CLI。
5. 数据链路 Properties：Bandwidth 填 40，Delay 填带单位的 5ms、15ms 等。
6. Save As 另存自己的 .mn；不要覆盖仓库历史文件。重新打开后核对，再 Run。

如果从空白画布自己重画，按上表连接 17 条线。**端口编号可能随连线顺序改变**；本项目主机表和路径取证使用已保存文件的端口布局。仅画出相同形状不保证现成控制器/取证脚本可直接运行。首次复现请使用仓库 .mn；重画后必须核对并相应维护端口映射。

## 4. 完整启动命令

先完成 [环境安装](REPRODUCE.md)，并按该页的结束顺序关闭上一轮网络。

**终端 C：启动基线控制器并保存控制台日志。**

~~~bash
cd "$HOME/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
mkdir -p local-validation
CEG_CONSOLE="$(mktemp "$PWD/local-validation/task1-controller-XXXXXX.log")"
bash run_baseline.sh 2>&1 | tee "$CEG_CONSOLE"
~~~

它会打印本轮 todo02/run-* 目录。此时等待交换机连接是正常的。

**终端 M：启动有图形界面的 MiniEdit。**

~~~bash
cd "$HOME/5101"
sudo service openvswitch-switch start
mkdir -p local-validation
export CEG_EVIDENCE="$(mktemp -d "$PWD/local-validation/task1-manual-XXXXXX")"
printf '%s\n' "$CEG_EVIDENCE"
sudo --preserve-env=CEG_EVIDENCE bash run_miniedit.sh
~~~

MiniEdit 中 File → Open → 选择本仓库 todo01/ca2-mesh-my.mn → Run。终端 M 出现 mininet>；终端 C 应出现：

~~~text
BASELINE READY: 6 switches, 22 directed links, 30 routes; h1->h6 [1, 2, 6] cost=19.0
~~~

22 是 11 条交换机链路的两个方向；30 是 6×5 个不同源、目的主机组合。

## 5. 实验操作及每一步的含义

### 5.1 拓扑、IP、协议和链路参数

在 **mininet>** 逐条运行：

~~~text
net
h1 ip -br addr show h1-eth0
h6 ip -br addr show h6-eth0
sh ovs-vsctl get bridge s1 datapath_id
sh ovs-vsctl get bridge s1 protocols
sh ovs-ofctl -O OpenFlow13 show s2
sh tc -s qdisc show dev s2-eth6
sh tc class show dev s2-eth6
~~~

net 给出真实接口两端的对应关系；DPID 和 protocols 检查 OVS 当前配置；tc 的 class/qdisc 显示带宽整形与延迟。s2-eth6 是本拓扑中 s2 连向 s6 的接口，预期显示 40Mbit 限速和 14ms 的 netem 延迟（输出单位/排版可能不同）。

**eth2 只表示某设备自己的接口编号，不等于 s2。** 例如 s1-eth2 恰好连接 s2，是因为 net 显示 s1-eth2:s2-eth2；换一种连线顺序就不一定如此。

本文件的端口核对表：

| 交换机 | 端口 1 | 其他端口连接 |
|---|---|---|
| s1 | h1 | 2→s2，3→s4，4→s5 |
| s2 | h2 | 2→s1，3→s3，4→s5，5→s4，6→s6 |
| s3 | h3 | 2→s2，3→s6，4→s5 |
| s4 | h4 | 2→s5，3→s1，4→s2 |
| s5 | h5 | 2→s4，3→s6，4→s2，5→s1，6→s3 |
| s6 | h6 | 2→s5，3→s3，4→s2 |

### 5.2 正常连通性与真实路径

~~~text
pingall
h1 ping -c 5 -W 1 10.0.0.6
sh ovs-ofctl -O OpenFlow13 dump-flows s1 "ip,nw_src=10.0.0.1,nw_dst=10.0.0.6"
sh ovs-ofctl -O OpenFlow13 dump-flows s2 "ip,nw_src=10.0.0.1,nw_dst=10.0.0.6"
sh ovs-ofctl -O OpenFlow13 dump-flows s6 "ip,nw_src=10.0.0.1,nw_dst=10.0.0.6"
~~~

预期 pingall 为 30/30；三个交换机的 output 对应 s1-eth2、s2-eth6、s6-eth1，也就是 s1→s2→s6→h6。再发一次 ping 并重查，相关 n_packets 应增加。**有流表且计数在增长，才比单独一行控制器“路径”打印更有说服力。**

保存流表和配置证据：

~~~text
sh ovs-ofctl -O OpenFlow13 dump-flows s1 > "$CEG_EVIDENCE/s1-flows.txt"
sh ovs-ofctl -O OpenFlow13 dump-flows s2 > "$CEG_EVIDENCE/s2-flows.txt"
sh ovs-ofctl -O OpenFlow13 dump-flows s6 > "$CEG_EVIDENCE/s6-flows.txt"
sh ovs-vsctl show > "$CEG_EVIDENCE/ovs.txt"
h1 ping -c 5 -W 1 10.0.0.6 > "$CEG_EVIDENCE/h1-ping.log" 2>&1
~~~

### 5.3 正常 UDP 吞吐与丢包

先开 h6 接收端，再让 h1 发 15 秒。以下仍在 **mininet>**：

~~~text
h6 iperf -s -u -p 5001 -i 1 -f m > "$CEG_EVIDENCE/receiver.log" 2>&1 & echo $! > "$CEG_EVIDENCE/receiver.pid"
h1 iperf -c 10.0.0.6 -u -b 10000000 -t 15 -i 1 -p 5001 -f m > "$CEG_EVIDENCE/sender.log" 2>&1
h1 cat "$CEG_EVIDENCE/sender.log"
h6 kill -INT "$(cat "$CEG_EVIDENCE/receiver.pid")"
h6 tail -n 20 "$CEG_EVIDENCE/receiver.log"
~~~

服务端 -s 接收；客户端 -c 指定 h6；-u 使用 UDP；-b 10000000 指定每秒一千万 bit；-t 15 持续 15 秒；-i 1 每秒报告；-f m 固定 Mbps 格式；& 使接收端在后台运行。最后按本轮记录的 PID 只停止这个接收端。

客户端普通 Bandwidth 行主要反映发送；请看最后的 **Server Report** 和 receiver.log 判断实际接收与丢包。10 Mbps 是提供负载，不是在测 40 Mbps 最大容量。原两轮正常实验均约 10 Mbps、0/12759 UDP 丢包；另一台机器不必复制完全相同 RTT 或包数。

## 6. 完成标准、截图和下一步

保存到本轮 CEG_EVIDENCE 目录：完整拓扑截图、net/端口检查、30/30 pingall、h1→h6 ping、三台交换机流表/递增计数、UDP Server Report。控制器自动输出的 state.json、events.jsonl 位于启动时打印的 todo02/run-*。

完成后应能解释：17 条数据线怎样组成、IP/DPID/端口各代表什么、40Mbps/延迟如何实现、为什么原路是 1→2→6。

在 mininet> 输入 exit → MiniEdit Stop 并关闭窗口 → 终端 C Ctrl+C。随后按 [Task 2](TASK2_DETECTION.md) 从新控制器启动，不能在当前基线控制器上期待自动封锁。
