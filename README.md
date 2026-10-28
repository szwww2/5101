# CEG5101 SDN 实验与现场演示

这个仓库供搭档复现 CA2 实验、检查实现并准备现场 demo。代码将流量监测、EMA 异常检测、源地址封锁、动态链路代价和合法流量改道集成在一个 Ryu 控制器中。

## 从哪里开始

1. **先理解并复现**：[完整安装与 Task 1–5 指南](docs/REPRODUCE.md)。逐项说明老师要求、我们的实现、原因、完整命令、预期现象与证据；首次学习按 Task 1→5，快速检查环境可先做独立 B 验证。
2. **先理解再改**：[实现与数据说明](docs/DESIGN_AND_RESULTS.md)。这里解释算法参数、原始结果与已知限制。
3. **准备现场展示**：[25 分钟 demo 建议](docs/DEMO_PLAN.md)。时间分配是建议，以课程公布的时段为准。
4. **请搭档反馈**：[复现与改进问题清单](docs/PARTNER_REVIEW.md)。记录失败步骤、建议改动及展示方式。

### 按老师任务阅读

| 任务 | 逐步指南 |
|---|---|
| Task 1 | [MiniEdit 参数、17 条链路、连通性、端口/流表与正常吞吐](docs/TASK1_TOPOLOGY.md) |
| Task 2 | [正常 ping 基线、EMA、限时异常、drop 规则与合法通信](docs/TASK2_DETECTION.md) |
| Task 3 | [全部有向链路代价、正常负载、异常惩罚与恢复](docs/TASK3_LINK_COST.md) |
| Task 4 | [A/B/C 完整启动、定时测量、真实改道与恢复证据](docs/TASK4_REROUTING.md) |
| Task 5 | [重画已有结果、冻结和绘制自己的新测量、解释图表](docs/TASK5_EVALUATION.md) |

注意：原 analyze_task5.py 默认读取历史 A/B1/C，不会自动分析最新实验；新数据的完整命令在 Task 5 第 5 节。

## 已有报告与实验结果

- [完整英文报告 PDF](report/review-20261017/CEG5101_CA2_Report_English.pdf)
- [完整中文报告 PDF](report/review-20261017/CEG5101_CA2_Report_Chinese.pdf)
- 同目录 HTML 可编辑；移动时一起保留 `assets/`。报告是 2026-10-17 的原始快照，未补成员和分工。
- [三场景与三轮 B 的图表、CSV 和分析](todo06/task5-final-20261017/)
- `todo01/evidence/` 至 `todo04/evidence/` 保存前期截图与证据。
- `todo05/` 保存五轮学生实验。保留 B1 最初的检查器 FAIL 以及另存的核验 PASS，没有用后来的较好结果替换它。

| 场景 | 异常流与目标链路 | 合法 h1→h6 路线 |
|---|---|---|
| A | h2→h3，s2→s3 | s1→s2→s6，保持原路 |
| B | h2→h6，s2→s6 | s1→s2→s6 → s1→s2→s3→s6 → s1→s2→s6 |
| C | h5→h6，s5→s6 | s1→s2→s6，保持原路 |

**C 的条件**：仅 h5→h6 IPv4 测试对被固定到直接 s5→s6，原始链路代价不变。无约束最短路是 s5→s3→s6（16），不是直接 s5→s6（20）。这一实验安排需要向教师/TA 确认；报告和代码均明确披露。

## 最短启动示例

在 Linux/WSL Ubuntu 22.04 内，按安装指南安装依赖后：

```bash
git clone https://github.com/szwww2/5101.git
cd 5101
conda activate ceg5101-ryu38
python -B -m unittest test_traffic_stats test_link_costs test_task4_evidence test_task5_analysis
/usr/bin/python3 check_environment.py
sudo service openvswitch-switch start
bash run_headless.sh B
```

最后一条会运行约一分钟的隔离验证，使用自己的 `t4` 节点和端口 16659；生成 `todo05/verification-B-.../`。它仍通过 MiniEdit 建网，并依赖可用的图形显示；无显示环境可在安装 `xvfb xauth` 后运行 `CEG_USE_XVFB=1 bash run_headless.sh B`。正式现场演示按指南使用可见 MiniEdit 和端口 6653。

## 发布范围与来源

这是从原实验工作区整理的协作副本。核心检测、代价与路由算法保持原样；仅适配 Ryu 路径和验证入口，新增安装/复现/演示说明。启动脚本自动寻找激活环境中的 `ryu-manager`，也支持 `CEG_RYU_MANAGER` 指定绝对路径，不依赖原作者用户名。

历史 JSON、日志和截图中保留的 Windows/WSL 路径是原实验记录，不是搭档需要使用的路径。`SOURCE_MANIFEST.json` 记录原始文件及发布文件 SHA256、适配文件与省略范围。Task3 大型 JSONL 快照以无损 `.gz` 保存，解压后的 SHA256 与原始文件一致。

原课程材料不在此复制，拓扑保存文件可直接运行。MiniEdit 源自 Mininet，保留原作者署名，许可说明见 [third_party](third_party/MININET_COPYRIGHT.txt)。AI 辅助范围见报告声明。

## English overview

This repository contains the controller, saved MiniEdit topology, measured student evidence, bilingual reports and partner reproduction instructions. Start with `docs/REPRODUCE.md`. Use Ubuntu 22.04, system Python for Mininet/MiniEdit, and the separate Python 3.8 Ryu environment. Case B demonstrates the route change and recovery. Case C uses an explicitly disclosed test-pair path constraint. Observed measurements are evidence, not guaranteed identical outcomes on another machine.
