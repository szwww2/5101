# Task 2、3 与 Task 4 A/B/C 全链路图

本次增加六幅完整链路图，并嵌入中英文报告对应任务。每版报告现为 30 页、24 幅截图或图表。Task 4 的 A、B、C 各有自己的全链路图，位于各场景原有代价、丢包、吞吐结果之后；Task 5 继续以 B 为主要改道分析对象。

| 图 | 报告页 | 数据与要说明的现象 |
|---|---:|---|
| `task2-all-links.png` | 7 | 新 Task 2 端口补测：11 条交换机链路双向，h2 封锁后下游突发消失，h1 原路仍有负载 |
| `task2-host-attachments.png` | 8 | 同一轮六条主机接入链路：h2 仍向 s2 发送，但包在 s2 被过滤 |
| `task3-all-links.png` | 11 | 原 Task 3 全部 22 方向：代价提高但正常流仍走原路；此阶段尚未执行改道 |
| `task4-A-all-links.png` | 14 | 原 A：s2→s3 突发被封锁，s1→s2→s6 保持正常负载 |
| `task4-B-all-links.png` | 16 | 原 B1：s2→s6 负载转到 s2→s3→s6，再恢复 |
| `task4-C-all-links.png` | 18 | 原 C：s5→s6 突发被封锁，合法原路不变；保留 s6→s3→s5 的短暂返回流量 |

每图另有 SVG。全部 11 条交换机链路均展示两个方向，包括接近空闲的链路；每幅图的交换机子图使用统一线性 Mbps 纵轴。蓝线从较小编号到较大编号，橙线为反方向。红线为源封锁；绿色线为惩罚解除；Task 3/4 末子图展示目标方向代价（另有单位）。Task 2 的主机图使用交换机端口 RX/TX，不把 TX 当成主机端的接收保证。

## 数据来源

- **Task 2：需要补数据，因此实际新跑了一轮。** `todo03/task2-link-capture-20261105`：32 秒，h1 10 Mbps UDP + ping，h2 正常 ping + 8 秒 flood。66 个端口快照，最大间隔 0.617 秒，22 个交换机方向、12 个主机接入方向。控制器不变。UDP 接收 10.0 Mbps，35/27,214 丢失（0.1286%），h1 ping 64/65；后测 h1 3/3、h2 0/3。详细方法和实际启动命令见 [补测记录](../../todo03/task2-link-capture-20261105/README.md)。
- **Task 3：直接使用原完整日志。** 45 个全网快照，990 行方向数据；以 h2 BLOCK 为时间零点。没有为补图重复发包。
- **Task 4 A/B1/C：直接使用各自原日志。** 每轮 59 个完整快照、1,298 行方向数据；流量图与前一页结果来自同一轮。A/C 无需重做，B2/B3 的原比较仍保留在 Task 5。
- C 的初始规则验证 h5→h6 为 `[5,6]`，h6→h5 返回路为 `[6,3,5]`。反向短暂流量与此规则一致，但端口汇总不具备逐包源识别能力。h5→h6 固定测试对的教学确认仍待完成。

## CSV 与测量口径

- `task2-all-directed-links.csv`：1,430 行，65 个区间 × 22 方向；使用目标交换机接收端字节差分和实际采样间隔。
- `task2-host-attachments.csv`：780 行，65 个区间 × 12 方向；六条接入链路的两个方向。
- `all-tasks-phase-means.csv`：330 行，Task 2/Task 3/A/B/C × 三阶段 × 22 方向。
- Task 3、A/B1/C 的逐方向原 CSV 位于 `../policy-evidence-20261105/`，没有重新改写。

阶段窗口：Task 2 为 [4,10)、[14,19)、[24,30) 秒；Task 3 相对 BLOCK 为 [-10,-2)、[3,8)、[20,30) 秒；Task 4 为 [4,10)、[15,24)、[40,55) 秒。阶段表为窗口内样本算术平均，不是精确时间加权平均。完整时间曲线保留启动、封锁和恢复的过渡样本。

端口约 10.3 Mbps 包含报头等开销，不等于接收端约 10 Mbps 的 UDP 有效吞吐；不能把同一流连续两跳的速率相加。近零线可能包含少量控制流量，不代表计数为零。Task 2 本轮与仅 ping 的上一补测分开，没有拼接、插值或掩去丢包。现有实验不构成用于量化改道独立收益的受控对照。

## 离线重画

在项目根目录、具有 matplotlib/numpy 的 Python 环境运行；不需要启动 Mininet：

```bash
python plot_all_link_evidence.py --output todo06/all-link-redraw
```

本机已实际验证的原目录命令：

```powershell
wsl -d Ubuntu-22.04 -- /home/robot/miniforge3/bin/python -B "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/plot_all_link_evidence.py"
```

`ALL_LINK_EVIDENCE.json` 保存 83 个输入文件的文件及解压内容 SHA256、脚本哈希、补测结果、各场景时间和路径。发布副本重画也需通过这些来源检查。SVG 可能带有生成时间；PNG 和 CSV 可逐字节复核。

## English reading notes

The six new figures are placed directly in Tasks 2, 3 and each Task 4 case. All 11 switch links are shown bidirectionally, including idle and reverse directions. Only Task 2 needed a new experiment because previous captures lacked port byte statistics; its unchanged controller was observed during a separate 32-second UDP-plus-ping run. Task 3 and A/B/C use complete original October measurements. Task 2 filters h2 while preserving the legitimate route; standalone Task 3 updates costs without changing routes; Task 4 B moves traffic to the alternative branch and back, while A/C keep the unaffected route. Port throughput, source-flow counters, installed routes and receiver measurements must be interpreted together.
