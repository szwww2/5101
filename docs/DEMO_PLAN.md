# 现场 demo 准备建议

通知要求提前至少 10 分钟到场，并带报告副本辅助演示。若排期确认为每组 25 分钟，可采用下面的安排；这不是教师指定的讲解时长。现场应留出运行和提问时间。

| 时间 | 展示内容 | 需要让老师看到什么 |
|---|---|---|
| 0–2 分钟 | MiniEdit 拓扑与任务目标 | 6 主机、6 交换机、17 数据链路，合法流与异常流分别是谁 |
| 2–6 分钟 | 监测、EMA、源封锁、动态代价 | 指出关键代码和公式，解释为什么只封锁异常源 |
| 6–12 分钟 | 现场 B 实验 | 原路 → BLOCK → 代价提高 → 替代路 → 恢复；合法接收保持 |
| 12–16 分钟 | A/C 结果或短时展示 | 为什么不一定改道；明确说明 C 的固定测试对条件 |
| 16–20 分钟 | 报告曲线与性能 | B 启动附近丢包、三轮波动、稳定阶段与整轮指标区别 |
| 20–25 分钟 | 提问与补充检查 | 路径证据、drop 计数、恢复条件、已知限制 |

## 原作者本机：可直接复制的演示命令

本节用于已经配置好的原作者 WSL Ubuntu-22.04。完整项目已在 D 盘，**不用重新 clone，也不用重装 Mininet/Ryu**。下列命令已经写好本机路径；搭档在其他电脑演示时使用自己的克隆目录。目录对照见 [复现指南第 0 节](REPRODUCE.md)。

开始前先结束上一轮实验：Mininet CLI 输入 exit → MiniEdit Stop 并关闭 → 旧控制器 Ctrl+C。下面以最容易展示真实改道的 B 场景为例。

### 终端 C：控制器

~~~bash
cd "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/publish/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
mkdir -p local-validation
CEG_CONSOLE="$(mktemp "$PWD/local-validation/demo-B-controller-XXXXXX.log")"
bash run_rerouting.sh B 2>&1 | tee "$CEG_CONSOLE"
~~~

记下启动时打印的 todo05/run-B-* 输出目录。此时控制器等待交换机连接，继续打开第二个 Ubuntu 终端。

### 终端 M：MiniEdit

~~~bash
cd "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/publish/5101"
sudo service openvswitch-switch start
sudo bash run_miniedit.sh
~~~

File → Open 选择这个文件，然后点 Run：

~~~text
/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/publish/5101/todo01/ca2-mesh-my.mn
~~~

每个终端都要单独 cd。此次使用 publish/5101 里的代码和拓扑；/home/robot/CEG5101/todo01 是早期操作文件存放处。打开拓扑文件不会自动切换 Python 的当前工作目录，所以启动 MiniEdit 前的 cd 仍然必需。

### mininet>：开始 B 的一分钟测量

等终端 C 出现 REROUTING READY: scenario=B 和初始 [1,2,6]，再等至少 8 秒预热。先保存拓扑和 READY 截图，然后在终端 M 的 mininet> 逐条输入：

~~~text
py __import__('os').getcwd()
py __import__('sys').path.insert(0, __import__('os').getcwd())
py __import__('student_task4_experiment').run(net)
~~~

第一条应显示上述 publish/5101 目录；第三条开始时的 Output 应与终端 C 本轮目录一致。实验自动完成 0–12 秒正常、约 12–26 秒异常、后续恢复，预期路径 [1,2,6] → [1,2,3,6] → [1,2,6]。

截图保存 BLOCK、两次 ROUTE 和最终汇总。如果要为这一轮生成新图，结束网络前在终端 O 按 [Task 5 第 5 节](TASK5_EVALUATION.md) 冻结分析；该页的 cd 同样替换成本机完整路径。测量和取证细节见 [Task 4](TASK4_REROUTING.md)。

### 若单独展示其他任务

终端 C 选择对应入口；终端 M 的目录与拓扑不变，每轮仍需结束旧网络/控制器再重开：

| 展示内容 | 控制器入口 | 后续操作 |
|---|---|---|
| Task 1 正常基线 | bash run_baseline.sh | 按 Task 1 执行 net、pingall、流表与 UDP 测量 |
| Task 2 检测封锁 | bash run_anomaly.sh | 按 Task 2 做正常 ping、限时异常和封锁检查 |
| Task 3 动态代价 | bash run_costs.sh | 按 Task 3 观察空闲、正常、惩罚及恢复 |
| Task 4 A | bash run_rerouting.sh A | 预热后使用同一 run(net) 入口 |
| Task 4 C | bash run_rerouting.sh C | 预热后使用同一入口，说明固定测试对条件 |
| Task 5 图表解释 | 不需要新控制器 | 打开现有图表，或按 Task 5 离线重画 |

## 上场前

1. 在演示设备上完整跑通至少一轮 B；提前确认电源、终端、显示缩放和 Linux 图形显示。
2. 准备 MiniEdit、控制器终端、Mininet CLI、报告 PDF 和图表。报告与原图离线可打开。
3. 开始新轮时确认旧 CLI 已 exit、MiniEdit 已 Stop、旧 Ryu 已停止；本轮 READY、代价无惩罚且源未被封锁。
4. 将报告中的 B 图、B3 汇总截图放在容易切换的位置，作为现场环境问题时解释已有证据的材料。回放旧结果要明确说是已有实验。
5. 不要在演示前临时整体升级 Python/Ryu 或更改已测量参数。

## 演示时怎么解释

“h1→h6 是持续合法流量。最初 s1→s2→s6 便宜。h2→h6 flood 超过包速率阈值后，入口封锁 h2，受影响 s2→s6 获得惩罚。控制器选择总代价更低的 s1→s2→s3→s6。异常停止并满足安静期后代价恢复，合法流返回原路；h2 仍然封锁。”

不要只说 PASS。用控制器事件、实际输出端口/VLAN 规则及计数、接收端吞吐互相印证。对于 A/C，要解释受影响边不在合法原路上，因此保持原路合理。

## 可能的问题

- 为什么采用旧 EMA 判断，而不是先把当前 flood 更新进基线？
- 为什么源速率只在入口统计，为什么排除 ICMP 回复？
- 为什么链路收到的流量很低，惩罚仍保留？
- 为什么恢复代价后不解除源封锁？
- VLAN 和 Barrier 分别解决什么问题，为什么要保留旧规则？
- 如何知道实际走过 s3，而不是控制器只打印了改道？
- 三轮丢包为何不同？现有证据能确定到什么程度？
- C 的自然最短路是什么，如何确保指定链路被施压？
- 如果真的拔掉一条链路会怎样？说明本次验证边界，不能宣称已测试。
