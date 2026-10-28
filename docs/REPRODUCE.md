# 搭档复现指南

目标是先确认环境可用，再复现正常通信、异常源封锁、合法流改道和恢复，最后讨论改进。已有实验数据保留在仓库，新的输出使用新目录，不覆盖旧结果。

## 1 安装 Linux 依赖

原测试环境为 WSL2 Ubuntu 22.04、系统 Python 3.10.12、Mininet 2.3.0、Open vSwitch 2.17.12。推荐从 Ubuntu 22.04 环境复现；其他版本尚未验证。Windows 本身不能直接运行 Mininet 网络命名空间实验。

在 Ubuntu 终端：

```bash
sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch python3-tk python3-pip \
  python3-dev build-essential iproute2 iputils-ping net-tools iperf hping3 \
  git curl xbitmaps xvfb xauth
git clone https://github.com/szwww2/5101.git
cd 5101
```

需要 iperf 2，不使用 iperf3 替换，否则现有日志解析和命令不兼容。MiniEdit 需要显示环境：WSLg、Linux 桌面或 X11 均可；无显示时只能先使用下文虚拟显示的自动验证。

## 2 安装独立 Ryu 环境

使用已有 Conda/Miniforge 安装，不要将旧版 Ryu 装入 Ubuntu 系统 Python。若没有 Conda，先按 Miniforge 官方安装说明安装并重开终端。

```bash
conda create -n ceg5101-ryu38 python=3.8.20 pip=24.0 -y
conda activate ceg5101-ryu38
python -m pip install setuptools==57.5.0 wheel==0.37.1
python -m pip install --no-build-isolation -r requirements-ryu38-lock.txt
ryu-manager --version
```

锁定文件来自原已验证环境；关键组合为 Ryu 4.34、eventlet 0.30.2、dnspython 1.16.0、NetworkX 2.6.3。若新安装失败，保留完整错误，先记录而不是直接升级全部依赖。

启动脚本优先使用 `CEG_RYU_MANAGER`，再找 PATH 中的 `ryu-manager`，最后尝试当前用户常见 Conda 安装目录。通常激活环境即可。如果用了其他位置：

```bash
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
```

## 3 先做无网络流量检查

仍在激活的 Ryu 环境、仓库根目录：

```bash
python -B -m unittest test_traffic_stats test_link_costs test_task4_evidence test_task5_analysis
/usr/bin/python3 check_environment.py
```

第一条检查计数器差分、EMA、惩罚恢复和已有数据解析，不生成攻击流量。第二条检查系统命令、Mininet、Tk、MiniEdit 位图及 Ryu 依赖，不启动服务。两条通过后再继续。

## 4 自动验证 B 场景

```bash
sudo service openvswitch-switch start
CEG_USE_XVFB=1 bash run_headless.sh B
```

脚本自动以 sudo 运行自己的网络，使用 `t4s1` 等独立节点、控制器端口 16659。MiniEdit 在虚拟显示中建网；已有桥必须在结束时保持不变。发现同名前缀占用时会拒绝运行，不应通过全局清理命令处理。

实验约需一分钟，另有启动和检查时间。预期：B PASS；路径 `[1,2,6]` → `[1,2,3,6]` → `[1,2,6]`；合法接收不断流；异常源仍被封锁。输出在新的 `todo05/verification-B-日期时间/`，不会覆盖五轮历史数据。重复运行时间至少错开一秒，以免验证目录时间戳重名。

有正常图形显示也可 `bash run_headless.sh B`。该自动验证显示的是独立验证结果，不是新增学生操作测量，不能混入旧报告的学生重复统计。

## 5 使用可见 MiniEdit 做现场演示

准备两个 Ubuntu 终端，都进入本次克隆的仓库。先确保上一轮正常退出，不能同时启动两个占用 6653 的控制器。

终端 B（控制器）：

```bash
conda activate ceg5101-ryu38
bash run_rerouting.sh B
```

终端 A（MiniEdit，用系统 Python）：

```bash
sudo bash run_miniedit.sh
```

在 MiniEdit 选择 File → Open，打开本仓库 `todo01/ca2-mesh-my.mn`，然后 Run。回到终端 B 等待 `REROUTING READY` 和至少 8 秒预热。终端 A 会出现 `mininet>` 提示符。

在 `mininet>` 输入下列两条命令，第一条引号内改为**搭档本机仓库的 Linux 绝对路径**，不要照抄原作者路径：

```text
py __import__('sys').path.insert(0, "/home/yourname/5101")
py __import__('student_task4_experiment').run(net)
```

第二条导入本仓库 `student_task4_experiment.py` 并调用 `run(net)`，复用当前 MiniEdit 网络。它会找到最新控制器目录，检查状态，启动定时测量；已经存在最终结果的目录会被拒绝，防止覆盖。不要同时运行多个控制器实验；需要明确选择时可调用 `run(net, output="本轮控制器输出目录")`。

### 这一分钟在做什么

- 0–12 秒：h6 作为 UDP 接收端，h1 以 10 Mbps 持续发送，建立正常基线。
- 约 12–26 秒：h2 向 h6 发送 ICMP flood；观察 `BLOCK`、目标边惩罚和 `ROUTE`。
- 26–60 秒：异常停止，等待安静期后恢复代价和合法路线。
- 60 秒以后：合法 ping 和已封锁源 ping 分别验证连通与封锁；后者可能再次短暂激活惩罚，不计入正式性能窗口。

预期原路线为 h1–s1–s2–s6–h6，异常时避开 s2–s6，经过 s3。吞吐应仍有接收，但不要要求另一台机器复制相同丢包数；原三轮 B 本来就有波动。

**截图检查点**：运行前保存拓扑和 READY；实验时保存 BLOCK/改道及恢复日志；结束保存 PASS 汇总。不要等日志滚走后才找截图。

### 切换到 A 或 C

每次先在 A 输入 `exit` → MiniEdit 点击 Stop → 在 B 按 Ctrl+C。然后 B 运行 `bash run_rerouting.sh A` 或 `C`，MiniEdit 重新 Run 并等待预热，再运行同一 Python 实验入口。

每轮必须重启状态，因为封锁不会自动解除。A 的异常源同样是 h2，不能沿用已经封锁 h2 的 B 状态。C 仅测试对 h5→h6 固定到直接 s5→s6；该条件已披露，需教学确认。

## 6 重新生成已有结果图

这一步只读取旧数据，不需要 sudo、OVS 或运行控制器。激活 Ryu 环境后：

```bash
python -B analyze_task5.py --output todo06/reproduced-three-cases
python -B compare_task5_b.py \
  --run run-B-20261016-144402-YuFNPf \
  --run run-B-20261017-105957-DfB6RZ \
  --run run-B-20261017-111734-b9lfbt \
  --output todo06/reproduced-B-comparison
```

输出目录必须不存在；再次生成时换新名字。历史事件采用冻结快照，旧记录中的绝对路径无需修改。Task3 大型快照压缩为 `.gz`，若要查看，可使用 `gzip -dc 文件.jsonl.gz`；Task5 绘图输入保持原始文件名，可直接解析。

## 7 常见问题

| 现象 | 处理与原因 |
|---|---|
| 找不到 ryu-manager | 激活环境；或设置 CEG_RYU_MANAGER，再运行环境检查 |
| No module named mininet | MiniEdit/验证入口必须用 `/usr/bin/python3`，不要用 Conda Python |
| couldn't connect to display | 检查 WSLg/X11；自动验证可用 xvfb，但可见演示仍需要图形环境 |
| OVS database connection failed | 先 `sudo service openvswitch-switch start` |
| h2 从实验开始就不通 | 上轮封锁仍在；按 exit → Stop → Ctrl+C 正常重启 |
| Switch/link disappeared | 就绪后网络被 Stop/重建；本实现面向固定拓扑，需要重开本轮 |
| HTB quantum 警告 | 保留日志，检查网络是否正常运行；不能把这条警告单独当作实验失败 |
| Python 模块改了却没更新 | 重启 MiniEdit，或对明确修改的模块使用 importlib.reload |

请按 `docs/PARTNER_REVIEW.md` 记录遇到的问题和建议。不要使用 `killall`、全局 `mn -c` 或删除全部 OVS 桥来解决占用，以免影响同机其他实验。
