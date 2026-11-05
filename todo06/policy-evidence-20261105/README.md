# 多链路流量与策略证据 / Multi-link policy evidence

这些图仅由 2026 年 10 月已有实验日志重建。没有执行新网络实验、修改原始计数或改变控制器。完整中英文报告在 `report/review-20261105`，各 24 页；六张新图已嵌入相应任务正文。

## 六张图分别回答什么

| 图文件 | 报告页 | 要回答的问题 |
|---|---:|---|
| `task2-selective-blocking.png` | 6 | h2 是否从转发变为入口丢弃？h1 是否仍正常转发并收到回复？ |
| `task3-cost-without-rerouting.png` | 8 | 独立代价阶段为何代价提高、原路径流量却没有迁走？ |
| `B1-branch-transfer-and-cost.png` | 13 | 代价比较如何对应原分支降载、备用两跳增载、共用路段持续承载？ |
| `B1-all-links-heatmap.png` | 16 | 全部 22 个方向是否显示同一转移现象，其他方向又是什么状态？ |
| `AC-unaffected-legitimate-path.png` | 17 | A/C 封锁异常源时，未受影响的合法路径是否继续承载？ |
| `B-all-repeats-branch-transfer.png` | 19 | 三轮 B 是否都发生实际流量转移与恢复，过渡过程有何差别？ |

每图另有 SVG；CSV 导出五轮实验（A、B1、B2、B3、C）的全部 22 个有向链路，以及每条链路的实测速率、利用率、负载项、惩罚项、总成本和归一化成本。`all-trials-phase-means.csv` 使用原比较窗口 [4,10)、[15,24)、[40,55) 秒，按记录样本算术平均，不冒充精确按时间加权平均。

## 策略与结果怎么对应

- **Task 2：EMA 检测加源 IP 封锁。** 当源速率超过 `max(2000 pps, 3×旧 EMA)`，通过 OpenFlow 在交换机安装 priority 5000、匹配该 IPv4 源地址的 drop 规则。后续 h2 转发计数不再增加，drop 计数增加；h1 不匹配该源地址，继续通信。新 drop 计数最初没有前值，图中保留采样缺口。全部后台 ping 为 292/293，不能声称全程零丢包。
- **Task 3：负载加异常风险的成本策略。** `C=C0+5U+60A`；`U` 为有向链路实测速率除以 40 Mbps 后限制到 0–1，`A` 表示该方向仍在异常惩罚期。入口仍丢弃攻击包时延长惩罚；最少 8 秒且连续 5 秒无入口 drop 活动后才清除。独立 Task 3 控制器只计算成本，保留静态路由。
- **Task 4：执行选路。** 对未封锁源，比较候选路径的链路代价之和，并满足改善/保持条件后更新交换机规则。B 中 s2→s6 的负载迁到 s2→s3→s6；A/C 原合法路径不受影响，保持原路。
- **Task 5：分析证据。** 同时检查源转发/drop、原/备用链路、路径规则和接收数据。单独看到 flood 链路速率下降，不能区分“源被封锁”与“正常流已改道”。

## 测量口径和不能推断的内容

端口 RX 是链路汇总字节速率，包含报头、标签、控制报文和其他流；接收端 iperf 的约 10 Mbps 是正常 h1 UDP 的有效载荷吞吐。因此端口约 10.3 Mbps 不表示超过了设定的有效发送速率。备用两跳承载同一数据，不能把 10.3+10.3 当作 20.6 Mbps 业务吞吐。反方向的短暂尖峰保留在全网图中，端口计数本身不能逐包识别源地址。

Task 2 没有保存端口统计：只能根据源转发/drop 及 ping 解释该阶段，不能还原当时每条链路的字节吞吐。Task 3 和集成 Task 4 则已保存全部方向。

B1 使用原分析的估计零点，其他集成轮次使用发送启动时间。接收端、端口统计和规则检查约按一秒对齐，事件标记不证明亚秒级因果顺序。独立 Task 2/3 图以各自记录的 block 事件为零点，没有臆造手工发包的精确启动时间。

B2 在 15.60 秒仍有原链路 4.726 Mbps 的样本，因此其 [15,24) 秒平均是 0.525 Mbps，保留在 CSV 和图中。18–24 秒内三轮 B 原分支均低于 0.01 Mbps，备用两跳都约 10.3 Mbps。不能因为稳定阶段转移完成而删除过渡样本。

恢复成本不解除源封锁。C 仅将 h5→h6 测试对固定到 s5→s6，教学确认仍待完成。没有进行“仅封锁”与“封锁加改道”的受控对照，不能凭这些图量化改道独立提升了多少性能，也没有证明 5/60 是最优参数。

## 重画与可追溯性

离线脚本为项目根目录 `analyze_policy_evidence.py`，依赖 matplotlib、numpy，并复用 `analyze_task5.py` 的接收数据解析和时间基准。它兼容发布仓库的 Task 3 gzip 历史文件。以下是新增的离线重画入口，不是本人当时发包的历史命令：

```bash
python analyze_policy_evidence.py --output todo06/policy-evidence-redraw
```

在已能运行原 Task 5 分析的 Python 环境执行即可，不需要启动 MiniEdit。`POLICY_EVIDENCE.json` 记录 50 个来源文件的压缩文件/解压内容 SHA256、时间基准、事件、限制和检查结果。原始文件保留在对应 todo03、todo04、todo05 中。

## English reading notes

The six figures reconstruct existing student measurements only. Task 2 implements selective source filtering; Task 3 scores directed links; Task 4 computes and installs routes; Task 5 interprets the integrated measurements. Task 4 is therefore an implementation task as well as an experiment.

The B curves show an approximately 10.3 Mbps port load moving from s2→s6 to both consecutive hops s2→s3 and s3→s6, while s1→s2 remains active and h6 receives approximately 10 Mbps of legitimate UDP payload. A/C retain the unaffected legitimate route. The standalone Task 3 curves demonstrate that cost computation alone does not modify forwarding.

All three B trials and their transients are retained. B2's original-link mean in [15,24) s is 0.525 Mbps because a 4.726 Mbps sample remains at 15.60 s. Port polling, interval averaging and independent receiver timing limit precise causal timing claims. Task 2 lacks port statistics, so only source counters and received ping replies are plotted for that stage. No controlled comparison isolates the independent benefit of rerouting.
