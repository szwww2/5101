# 完整复现指南：按老师 Task 1–5 操作

这份指南的目标是让搭档既能运行实验，也能解释每一步在验证什么。每个任务分别说明：**老师要求 → 我们做了什么 → 为什么这样做 → 完整启动与实验命令 → 预期现象 → 保存证据 → 结束和重做**。

任务要求按课程四页 Lab Assignment 的 Task 1–5 及 Reference A–C 核对后概述；教师原文件不在仓库转载，请用课程平台上的原件核对。文中给出的参数、实验时长、验收阈值和操作顺序是本项目的选择，不全部是老师规定。

## 1. 先看全流程和编号

| 老师任务 | 要回答的问题 | 主要实现/入口 | 原工作区编号 |
|---|---|---|---|
| [Task 1：拓扑与正常基线](TASK1_TOPOLOGY.md) | 网络是否按要求建好？正常情况下走哪条路？ | todo01/ca2-mesh-my.mn、run_baseline.sh | TODO1；附带 TODO2 基线 |
| [Task 2：监测、检测、封锁](TASK2_DETECTION.md) | 谁发得异常快？是否真的被交换机丢弃？ | run_anomaly.sh | TODO3 |
| [Task 3：动态链路代价](TASK3_LINK_COST.md) | 负载和异常如何使链路变贵？何时恢复？ | run_costs.sh | TODO4 |
| [Task 4：合法流改道](TASK4_REROUTING.md) | 异常发生后，h1→h6 是否选择更低成本路线并持续通信？ | run_rerouting.sh A/B/C | TODO5 |
| [Task 5：性能评价](TASK5_EVALUATION.md) | 把前、中、后的代价、丢包和吞吐画出来，能得出什么结论？ | analyze_task5.py、compare_task5_b.py、指南内新数据分析命令 | TODO6 |

老师 Task 1–4 分别标为 5、5、10、10 分；Task 5 是性能评价要求，没有另标分数。TODO0 是前期学习练习，不是老师的第六个评分任务。

第一次理解项目，按 Task 1→2→3→4→5 走一遍。只检查安装是否可用，可先做本页第 5 节的独立 B 验证，但它不能替代逐任务理解和可见 MiniEdit 展示。

最终控制链是：

**建立拓扑和正常路径 → 读取计数并计算速率 → EMA 判断异常源 → 安装源 IP drop → 提高异常边代价 → Dijkstra 重算 → 更新实际流表 → 接收端测量 → 停止异常后的恢复。**

## 2. 环境安装：只做一次

已验证环境：WSL2 Ubuntu 22.04、系统 Python 3.10.12、Mininet 2.3.0、Open vSwitch 2.17.12；Ryu 在独立 Python 3.8.20 环境。新机器完整安装尚需搭档验证，其他系统版本不能视为已通过。

以下命令全部在 **Ubuntu 的 Bash 终端**执行，不在 Windows PowerShell 中执行。若使用 Windows，先进入已安装的 Ubuntu 22.04。可见 MiniEdit 需要 WSLg、Linux 桌面或配置好的 X11。

### 2.1 系统依赖与仓库

~~~bash
sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch python3-tk python3-pip \
  python3-dev build-essential iproute2 iputils-ping net-tools iperf hping3 \
  git curl xbitmaps xvfb xauth
git clone https://github.com/szwww2/5101.git "$HOME/5101"
cd "$HOME/5101"
mkdir -p local-validation
~~~

已经克隆过：进入现有仓库，先看 git status；没有待处理本地改动时用 git pull --ff-only 更新，不重复 clone 到同名目录。

必须使用 **iperf 2**；iperf3 的参数和日志格式不同，不能直接替换。本指南统一把克隆位置写成 "$HOME/5101"，若你选了别的位置，请在所有终端一致替换。

### 2.2 没有 Conda 时安装 Miniforge

已有 Linux 内的 Conda/Miniforge 可以跳过本节；Windows 中安装的 Conda 不代替 WSL 内的环境。以下命令按 [Miniforge 官方说明](https://github.com/conda-forge/miniforge#install) 选择本机 Linux 架构，安装到用户目录，不覆盖已有安装目录：

~~~bash
cd "$HOME"
curl -fL -o Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname -s)-$(uname -m).sh"
bash Miniforge3.sh -b -p "$HOME/miniforge3"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
cd "$HOME/5101"
~~~

本项目实际验证的是 x86_64 Ubuntu 环境；其他架构依赖能否安装和运行需要另测。安装包的 base Python 与下面单独创建的 Python 3.8 环境不是一回事。

### 2.3 创建 Ryu 环境

~~~bash
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda create -n ceg5101-ryu38 python=3.8.20 pip=24.0 -y
conda activate ceg5101-ryu38
cd "$HOME/5101"
python -m pip install setuptools==57.5.0 wheel==0.37.1
python -m pip install --no-build-isolation -r requirements-ryu38-lock.txt
ryu-manager --version
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
~~~

如果 Conda 在 miniconda3 或其他位置，修改 source 的路径即可。环境已创建则只需 source 和 activate，不反复 create。保留锁文件；安装失败时保存错误，不直接升级所有依赖。

Ryu 使用隔离环境，是因为该版本依赖较旧；Mininet/MiniEdit 使用 Ubuntu 的 **/usr/bin/python3**，才能找到系统安装的 Mininet、Tk 和网络工具。run_miniedit.sh 已固定使用系统 Python。

### 2.4 启动网络前检查

~~~bash
cd "$HOME/5101"
python -B -m unittest -v test_traffic_stats test_link_costs test_task4_evidence test_task5_analysis
/usr/bin/python3 check_environment.py
sudo service openvswitch-switch start
sudo ovs-vsctl list-br
~~~

前两条分别运行 19 项离线检查和环境检查，不产生异常流量。最后一条列出已有 OVS 桥，便于分清本实验与其他网络；不要删除不属于本实验的桥。

## 3. 终端分工、命令含义和日志位置

本指南固定使用同一种命名：

| 窗口 | 用途 | 看到的提示符 |
|---|---|---|
| 终端 C | 启动控制器，观察 STATS/BLOCK/LINK/ROUTE | Ubuntu shell；启动后持续打印日志 |
| 终端 M | 启动 MiniEdit；点 Run 后输入实验命令 | 从 Ubuntu shell 变成 mininet> |
| 终端 O（可选） | 同时查看文件、流表或运行离线分析 | Ubuntu shell |

**不要复制提示符 mininet>。** 本指南标为 text 的命令块在 Mininet CLI 输入；bash 块在 Ubuntu shell 输入。

| 命令开头 | 实际在哪里执行 |
|---|---|
| h1 / h2 / h6 | 对应虚拟主机的 Linux 命名空间，例如 h1 ping ... |
| sh | Mininet 所在机器的 shell，适合 ovs-ofctl / tc |
| py | Mininet 进程里的 Python 表达式，可访问当前 net 对象 |
| sudo | 给建网进程管理 Linux namespace、veth、OVS、tc 的权限 |

任务 1–3 的页面会在终端 M 创建唯一的 CEG_EVIDENCE 目录，并通过 sudo 传给 Mininet。主机共享文件系统，因而 h1 和 h6 可以向同一目录写不同日志；它们的网络命名空间仍然不同。不要去掉 --preserve-env=CEG_EVIDENCE。

控制器启动器另外创建 todo02/03/04/05 下的新 run-* 目录，保存 state、事件和统计。终端 C 的输出也通过 tee 留存。任务 4 的自动入口会把流量与状态证据集中在本轮 todo05/run-* 中。

新数据默认被 .gitignore 忽略，避免把每轮机器结果都误提交；它们仍存在磁盘。要分享新实验，先检查再显式选择需要的目录。

## 4. 每次切换任务/场景必须重新开始

每个任务页面的启动步骤都从“上一轮已结束”开始。依次操作：

1. 等本轮测试完成，停止本轮手动启动的接收端，保存日志和截图。
2. 在终端 M 的 mininet> 输入 exit。
3. 回 MiniEdit 点击 Stop；若已经自动停网，确认已停止即可。需要换证据目录时关闭此 MiniEdit 窗口，回到 Ubuntu shell。
4. 在终端 C 按 Ctrl+C 停止旧控制器。
5. 按下一任务页面启动新控制器、新 MiniEdit，然后 Open 和 Run。

原因：异常源封锁保留到这一轮结束。沿用已经封锁 h2 的状态再次测试 h2，会使异常一开始就被挡住，失去“正常→检测→封锁”的过程。

控制器就绪后不要为了继续实验再点 Stop/Run。本实现对固定拓扑工作；中途整网重建会触发 Switch/link disappeared，需结束后重新开一轮。不要使用全局 mn -c、killall 或删除所有 OVS 桥。

## 5. 可选：自动做一次独立集成验证

它自动创建并清理自己的 t4 网络，端口 16659，不占用可见实验的 s1–s6 / 6653。单次约 60 秒测量，另有启动、预热和检查时间。

~~~bash
cd "$HOME/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
sudo service openvswitch-switch start
bash run_headless.sh B
~~~

无显示或想使用虚拟显示，最后一条改为：

~~~bash
CEG_USE_XVFB=1 bash run_headless.sh B
~~~

依次验证全部三场景：

~~~bash
CEG_USE_XVFB=1 bash run_headless.sh all
~~~

预期 B PASS，路径 [1,2,6] → [1,2,3,6] → [1,2,6]；A/C 保持 [1,2,6]。输出为新的 todo05/verification-*。每轮保留全部结果，不能只挑最好的一次。xvfb 分支尚未在原作者机器执行验证；原发布验证使用已有 WSLg 显示。

## 6. 常见问题

| 现象 | 检查和处理 |
|---|---|
| No module named mininet | MiniEdit 必须用 run_miniedit.sh 中的 /usr/bin/python3 |
| 找不到 ryu-manager | 在终端 C 激活环境并 export CEG_RYU_MANAGER；这个变量不会自动传播到其他终端 |
| couldn't connect to display | 检查 WSLg/X11；自动验证可用 xvfb，可见 MiniEdit 仍需真实显示 |
| OVS database connection failed | sudo service openvswitch-switch start |
| 6653 already in use | 用 sudo ss -ltnp 'sport = :6653' 找原进程，在所属终端正常停止 |
| h2 从第一步就不通 | 检查是否沿用了上轮封锁；完整结束后重启 |
| Address already in use（5001） | 本轮已有 h6 iperf 接收端；不要重复启动，按任务中的 PID 清理 |
| HTB quantum 警告 | 保留日志并继续检查实际连通性/参数；单凭这行不能判定实验失败 |
| 新代码未生效 | 重启 MiniEdit；仅重启 Ryu 不会清除 Mininet Python 的导入缓存 |
| Task 3 cost 变了却未改道 | 这是该阶段刻意保留的静态转发；Task 4 才启用实际改道 |
| Task 4 最后又改道一次 | 60 秒后的封锁探测可能重激活惩罚，查看时间，不混入正式 0–60 秒图 |
| Task 5 重画结果和新实验不同 | 原绘图入口固定读取旧试验；新数据请用 Task 5 页面专门的流程 |

## 7. 交给搭档的复现记录

按 [反馈清单](PARTNER_REVIEW.md) 记录机器/系统版本、Git commit、每个任务的输出目录、通过/失败证据及建议。优先完整复现现有版本，再改检测阈值、恢复策略或实验条件。

本轮指南补充范围是操作说明与离线分析命令，没有改变原控制器算法。历史测量和报告仍是原版本的证据；新的测量单独保存。C 场景的测试对固定路径条件详见 Task 4，仍待教师/TA 确认。
