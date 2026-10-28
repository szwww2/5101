# Task 4：异常期间合法流改道与恢复

[返回完整指南](REPRODUCE.md) · [上一任务](TASK3_LINK_COST.md) · [下一任务](TASK5_EVALUATION.md)

## 1. 老师要求什么

先建立合法 h1→h6 流，记录原路径、链路代价、丢包和吞吐。再依次测试下面三种异常。每种都要观察负载/成本，验证源被检测并封锁，判断合法流是否转到成本更低的路径，记录异常前/中性能，验证合法连接保持，并在异常停止后核对代价和路由恢复（10 分）。路由参考 resilient_controller.py。

| 场景 | 异常源→目的 | 指定受影响链路 | 原合法路径是否经过该边 |
|---|---|---|---|
| A | h2→h3 | s2→s3 | 否 |
| B | h2→h6 | s2→s6 | 是 |
| C | h5→h6 | s5→s6 | 否 |

分成三种场景是为了分别观察不同异常位置。**并非老师要求每一种都必须改道**；要根据各候选路径的当前成本判断。A/C 原合法路径未经过异常边，保持原路可以是正确结果。

## 2. 我们做了什么，为什么

rerouting_controller.py 把 Task 2 的检测/封锁、Task 3 的动态代价与真实路由更新集成：

1. 每轮用当前有向代价重算主机对的最短路。
2. 候选新路至少便宜 1，且距上次切换至少 3 秒才切换，减少微小负载波动导致的反复选路。
3. 为新路线分配内部 VLAN 版本，先装好下游规则，等待 OpenFlow Barrier 确认，再改变入口规则；目的交换机去掉 VLAN。
4. 保留旧版本 5 秒后按专属 cookie 清理，减少在途包混用新旧路径的问题。
5. 源 IP drop 使用独立 cookie 和更高优先级，不随路径更新被删除。

VLAN 在这里是区分转发版本的内部标签，不需要给 h1/h6 配 VLAN。Barrier 表示交换机处理完此前消息，不等于承诺任意流量下零丢包。3 秒、5 秒和成本改善阈值都是实现参数。

以 B 为例：空闲原路成本 19，小于备选 22；s2→s6 加 60 后，原路变贵，备选 s1→s2→s3→s6 更便宜。异常活动停止、惩罚撤销后，原路又更便宜，恢复原路。实际选择还会计入各边的负载项。

### C 场景必须披露的条件

原权重下 h5→h6 的自然最短路是 s5→s3→s6，成本 9+7=16；直接 s5→s6 成本 20。为了让该测试流确实经过老师指定的 s5–s6，C 模式**只固定 h5→h6 IPv4 测试对到直接链路**，其他流继续动态选路，基础代价不修改。

这是我们的实验安排，仍需向教师/TA 确认是否接受。不能把它说成无约束 Dijkstra 自然得到的路径，也不能隐去该条件。程序启动 C 时会再次打印说明。

## 3. 全流程：每种场景独立一轮

推荐按老师顺序 A→B→C；如果只是排查环境，可先看最明显的 B。每轮都完整结束旧网络和控制器再重启，不共用封锁状态。

每轮测量自动完成以下步骤：

| 时间/阶段 | 做什么 | 保存/观察什么 |
|---|---|---|
| 启动、预热 | 六交换机、22 个方向就绪；源基线预热 | READY、初始路径、无封锁 |
| 测量前 | pingall、实际路径快照 | evidence/initial.json |
| 0–12 秒 | h1→h6 连续 10Mbps UDP，并持续 ping | 正常接收吞吐、成本和路径 |
| 约 12–26 秒 | 指定异常源 ICMP flood 14 秒 | BLOCK、惩罚、实际路径、drop 保留、接收性能 |
| 26–60 秒 | 异常已停止，合法流继续 | 惩罚撤销、代价及合法路径恢复 |
| 60 秒后 | 合法源 ping 3 次、被封锁源 ping 2 次 | 合法仍通、异常源仍封锁 |

正式图表分析 0–60 秒。末尾被封锁源的探测会再次产生 drop 活动，有时短暂重激活惩罚和 B 的改道；这不是正式异常没有恢复，必须按时间区分。

## 4. 场景 A：完整启动和运行

先完成环境安装，并结束 Task 3；不要遗留 h6 的 5001 接收端。

**终端 C：**

~~~bash
cd "$HOME/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
mkdir -p local-validation
CEG_CONSOLE="$(mktemp "$PWD/local-validation/task4-A-controller-XXXXXX.log")"
bash run_rerouting.sh A 2>&1 | tee "$CEG_CONSOLE"
~~~

记下打印的 **todo05/run-A-日期时间-随机后缀**。终端 O 可以同时记 Git 版本：

~~~bash
cd "$HOME/5101"
git rev-parse HEAD
~~~

**终端 M：**

~~~bash
cd "$HOME/5101"
sudo service openvswitch-switch start
sudo bash run_miniedit.sh
~~~

MiniEdit File → Open → 本仓库 todo01/ca2-mesh-my.mn → Run。等待终端 C 出现 REROUTING READY: scenario=A，初始路线 [1,2,6]，再等至少 8 秒。

**截图 1：**拓扑、READY 和初始成本。等待期间不要自行发 flood 或额外 UDP。

在 **mininet>** 输入：

~~~text
py __import__('os').getcwd()
py __import__('sys').path.insert(0, __import__('os').getcwd())
py __import__('student_task4_experiment').run(net)
~~~

第一条必须显示本次克隆的 5101 仓库目录。如果不是，停止并从正确目录重开 MiniEdit；不要把别的项目目录加进模块搜索路径。

第二条把仓库目录放到 Python 模块搜索列表前面。第三条导入 student_task4_experiment.py 并调用 **run(net)**；net 就是当前 MiniEdit 创建的网络，不会再建第二张可见网络。文件由 Python 搜索路径找到，因此写模块名时不加 .py。

默认选择本仓库最新的 todo05/run-* 目录，所以只保留一个当前控制器。开始后它会打印 Output，**必须和本轮控制器输出一致**。如果你保留多个输出需要明确指定，用下面一条替代第三条，填本轮实际绝对路径：

~~~text
py __import__('student_task4_experiment').run(net, output="/home/你的Linux用户名/5101/todo05/本轮run目录名")
~~~

这个函数自动启动 h6 接收端、h1 合法业务、异常源进程、每秒取证，最后停止它启动的流量进程。不需要自己抢时间输入 hping3，也不要再手动启动第二个 iperf。已有 results.json 的目录会拒绝重跑以防覆盖。

**截图 2：**终端 C 的 BLOCK、penalty=60、恢复 penalty=0。**截图 3：**终端 M 的最终 PASS、Actual paths 和三个窗口的接收指标。

要分析自己的新测量，**此时先在终端 O 执行 Task 5 第 5 节的冻结与绘图命令，再结束网络**；B/C 也一样。这样不会把手动 Stop 引发的拓扑退出错误混入待复核的事件文件。只阅读旧报告时可以跳过新数据分析。

A 预期：

- h2 被封锁；s2→s3 基础 10，惩罚期约 70 加负载项，随后恢复。
- h1→h6 全程 [1,2,6]，因为 s2→s3 不在原合法路线上。
- 各一秒窗口仍有合法接收；如有丢包保留真实数值。

## 5. 场景 B、C：重新启动后执行相同测量

A 完成后：mininet> 输入 exit → MiniEdit Stop 并关闭 → 终端 C Ctrl+C。

**B 的终端 C 完整命令：**

~~~bash
cd "$HOME/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
mkdir -p local-validation
CEG_CONSOLE="$(mktemp "$PWD/local-validation/task4-B-controller-XXXXXX.log")"
bash run_rerouting.sh B 2>&1 | tee "$CEG_CONSOLE"
~~~

终端 M 重新执行第 4 节的 MiniEdit 启动命令，Open/Run，等 B READY 和至少 8 秒预热，再执行相同三条 py 命令。

B 预期 h2 被封锁；s2→s6 成本从约 14–15.3 升为约 74 加负载项；合法流实际路径 **[1,2,6] → [1,2,3,6] → [1,2,6]**。保存 BLOCK、两次 ROUTE 和最终汇总。

B 完成后按同样顺序结束。**C 的终端 C 完整命令：**

~~~bash
cd "$HOME/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
mkdir -p local-validation
CEG_CONSOLE="$(mktemp "$PWD/local-validation/task4-C-controller-XXXXXX.log")"
bash run_rerouting.sh C 2>&1 | tee "$CEG_CONSOLE"
~~~

终端 M 再次从第 4 节启动 MiniEdit 并执行 py 测量。检查启动时的固定测试对说明。

C 预期 h5 被封锁；s5→s6 的成本从约 20 升到约 80 加负载项再恢复；合法 h1→h6 保持 [1,2,6]。记下本轮 run-C-* 目录，保留截图。

## 6. 自动入口究竟运行了什么命令

verify_rerouting.py 通过每台主机的 popen 启动以下程序，参数已经固定在代码里。此表供理解，**使用自动入口时不要再额外执行一次**。

| 作用 | 主机及内部命令 |
|---|---|
| 接收合法 UDP | h6：iperf -s -u -p 5001 -i 1 -f m |
| 发送合法 UDP | h1：iperf -c 10.0.0.6 -u -b 10000000 -t 60 -i 1 -p 5001 -f m |
| 连续可达性 | h1：ping -D -i 0.5 -W 1 10.0.0.6 |
| A 异常 | h2：timeout 14s hping3 -1 --flood 10.0.0.3 |
| B 异常 | h2：timeout 14s hping3 -1 --flood 10.0.0.6 |
| C 异常 | h5：timeout 14s hping3 -1 --flood 10.0.0.6 |

自动时序使每轮可比较。终端最终 before/during/after 使用稳定窗口 **4–10 / 15–24 / 40–55 秒**，没有包含所有切换瞬间；Task 5 必须再看完整一秒曲线和整轮结果，不能只报这三个窗口零丢包。

## 7. 如何证明“实际改道”，而非只看控制器日志

inspect_rerouting.py 会读取真实 OVS 入口规则的 VLAN 标签、沿途版本规则、output 端口、Linux veth 对端和包计数。dataplane-samples.jsonl 每秒保存一次，所以有数据平面证据支持路径结论。

需要另存一个现场快照时，在 **终端 O** 执行，路径替换为本轮真实目录：

~~~bash
cd "$HOME/5101"
export CEG_RUN="$PWD/todo05/这里替换为本轮run目录名"
sudo /usr/bin/python3 inspect_rerouting.py manual-check --output "$CEG_RUN"
~~~

它只读流表/状态并把快照写入 evidence/manual-check.json。若想采多个快照，换 label，避免覆盖自己之前的 manual-check。正式测量已每秒自动取证，无须为了取证打断或重开网络。

## 8. 输出、验收和下一步

| 文件 | 用来回答什么 |
|---|---|
| results.json | 本轮检查结果、整轮/分窗口性能、时序、路径 |
| sender.log / receiver.log | UDP 发送和接收端实际报告 |
| continuous-ping.log | 合法流持续可达性、时间戳和最终 ICMP 统计 |
| flood.log | 限时异常进程输出 |
| dataplane-samples.jsonl | 每秒真实路径、VLAN、流表和计数 |
| link-costs.jsonl / cost-state.json | 完整代价时间序列与当前状态 |
| events.jsonl | BLOCK、惩罚、路径切换、恢复与错误事件 |
| evidence/initial.json、recovered.json | 初始及恢复状态的完整证据 |
| post-pings.txt | 末尾合法可通、异常源仍封锁 |

脚本 PASS 表示通过本项目检查，不是教师给分或零丢包保证。当前检查包含整轮接收 >8Mbps、UDP 丢包 <5%、每秒接收非零、足够连续 ping 回复、实际路径/惩罚恢复及源封锁保留等；这些阈值是本项目验收选择。

如果 FAIL，保留 results.json 的 error/traceback、控制器日志和本轮目录；不要手改 PASS 或在同一封锁状态反复重跑。查明原因后正常结束，再启动一个新 run-*。

A/B/C 各轮完成并冻结所需的新数据后，关闭网络和控制器，按 [Task 5](TASK5_EVALUATION.md) 整理比较。这些数据已经包含所需时间序列；不需要为了画图再无目的地重复所有实验。B 的三次重复是本项目做的额外重复性检查，不是老师明确规定的次数。
