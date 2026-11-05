# Task 2 全链路端口补测 / Port-capture repeat

这是学生要求“缺数据就重新实验”后，由助手于 2026-11-05 独立完成的一轮测量。原 Task 2 和前一次仅 ping 补测没有保存端口字节统计；它们不能用来还原各链路 Mbps。本轮沿用原 `anomaly_controller.py`、EMA、源 IP 封锁规则和保存的 MiniEdit 拓扑，新增独立观测程序 `capture_task2_links.py`，没有修改控制器。

## 做了什么，为什么这样做

- 持续 32 秒：h1→h6 发送 10 Mbps UDP，并每 0.5 秒 ping；h2→h6 普通 ping 建立正常基线。
- 第 12 秒附近，h2 运行 8 秒 `hping3 -1 --flood 10.0.0.6`。保持正常业务运行，观察封锁之前、期间和攻击停止之后。
- 每约 0.5 秒保存六台交换机的完整流表及 `ovs-ofctl -O OpenFlow13 dump-ports` 输出，共 66 份端口快照，最大间隔 0.617 秒。
- 11 条交换机链路均取下游接收端 RX，覆盖 22 个方向；六条主机接入链路使用交换机入口 RX 和出口 TX，覆盖另 12 个方向。原始计数除以实际相邻采样间隔计算速率，不填补或拼接别轮数据。
- 流表计数用于判断哪个源被丢弃；端口统计用于显示流量停在何处。端口汇总本身不能逐包识别源地址，出口 TX 也不等于主机全部收到。

## 实际结果

| 项目 | 测量 |
|---|---:|
| 检测时 h2 源速率 | 12,831.7 pps |
| 检测阈值 | 2,000 pps |
| BLOCK 相对采集开始 | 12.775 秒 |
| h1 UDP 接收报告 | 10.0 Mbps |
| UDP 丢失 | 35/27,214（0.1286%） |
| h1 连续 ping | 64/65 |
| 后测 h1 / h2 ping | 3/3 / 0/3 |

六台交换机均保留 h2 源 IP drop；h1 未被封锁。封锁并排空后，h2 在 s2/s6 的转发计数停止增加；h2→s2 的入口流量仍持续到 flood 结束，而 s2→s6 回到正常业务负载。h1 的原路径 s1→s2→s6 仍承载流量。全部实际损失保留，不将本轮描述成零丢包。

此轮与 `../task2-recapture-20261105/` 的仅 ping 补测（64/64）分开；十月原测量也保留。它不是“仅封锁”与“封锁加改道”的受控性能对照。

## 这轮实际使用的完整启动命令

以下为新增自动补测的命令，不是用户十月手动实验命令。它会自己创建隔离的 Mininet 网络，无需另外点击 MiniEdit Run。

```powershell
wsl -d Ubuntu-22.04 -u root -- /usr/bin/python3 -B "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/capture_task2_links.py" --output "/mnt/d/desktop/nus/CEG5101 Modern Computer Networking/sdn_assignment/todo03/task2-link-capture-20261105"
```

此结果目录已存在，脚本拒绝覆盖。若需要再次运行，将 `--output` 改成一个新的目录名。脚本使用本机既有 Ryu 环境、`l2h*`/`l2s*` 节点及控制器端口 16662；只清理自身网络和进程。本轮前后 OVS 桥列表相同。搭档的环境路径需按自己的安装配置，不应直接照抄本机绝对路径。

## 原始证据与图

`capture-results.json` 保存条件、事件时间、源码哈希、流表检查和清理检查；`port-snapshots.jsonl` 保存逐交换机原始端口输出、解析计数和采样时间；`flow-snapshots.jsonl` 保存转发/drop 计数。`source-rates.jsonl`、`events.jsonl`、ping、UDP 和 flood 日志均保留。

图、CSV 和重画入口见 [全部链路补图](../../todo06/all-link-evidence-20261105/README.md)。双语报告第 7–8 页使用本轮，第 6 页仍使用前一轮仅 ping 数据。

## English summary

This separately labeled, assistant-run 32-second repeat was requested by the student. The original Task 2 controller is unchanged. A 10 Mbps h1 UDP stream and continuous ping remain active while h2 generates an 8-second ICMP flood around second 12. Sixty-six complete port snapshots cover all 11 switch links in both directions and all six host attachments. Source-flow counters confirm selective h2 filtering; the port data locate its effect. Receiver results are 10.0 Mbps with 35/27,214 UDP datagrams lost, 64/65 continuous h1 ping replies, and post-tests of h1 3/3 and h2 0/3. No old/new samples are spliced, and the earlier ping-only repeat remains separate.
