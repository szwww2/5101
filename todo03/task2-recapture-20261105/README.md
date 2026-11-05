# Task 2 连续补测 / Continuous Task 2 repeat

2026-11-05，用户要求修复原图封锁附近的数据断口并授权重新实验。本轮由助手运行，不计入十月学生亲自操作的实验或 B 的三次重复。

使用原保存拓扑、原 anomaly_controller.py、原 EMA 参数（0.3、三倍旧 EMA、最低 2000 pps、五个预热样本）。为隔离已有实验，节点加 q2 前缀，控制器端口改为 16661；DPID、IP、链路参数及路由保持。运行前后桥列表一致，未使用全局清理。

## 实验流程

1. 启动隔离控制器和由保存文件构建的 MiniEdit 网络，等待 READY。
2. 开始采集六台交换机完整流表，同时 h1、h2 每 0.5 秒 ping h6。
3. 约第 12 秒，h2 运行 `timeout 8s hping3 -1 --flood 10.0.0.6`。
4. 持续采集到第 32 秒，记录正常流在攻击及封锁后的转发与回复。
5. 最后分别让 h1/h2 ping 三次，再停止本轮进程和隔离网络。

## 为什么这次没有旧图断口

原控制器按每条规则做差分。新 drop 规则第一次出现时没有前值，因此该轮源速率不写入日志。这不是断网，也不能把缺口直接画成零。

本轮保持该控制器不变，另以 `ovs-ofctl -O OpenFlow13 --no-names dump-flows` 每约半秒保存完整表。按源 IP 汇总 priority 100/110 的转发计数、priority 5000 的丢弃计数；排除 priority 109 的 echo reply。完整快照确认 drop 规则尚不存在时，该类累计数为零。下一份快照出现规则后，可用当前总数减上次总数，再除以两次采集实际时间差。

这得到包括规则创建区间在内的平均速率，**不是插值，也不是瞬时速率**。每台交换机使用自己的读取时间中点；一次表读取的起止时间和完整文本均保存。计数器有重置或间隔超过一秒时，绘图校验会失败；本轮均没有发生。

## 实测结果

- 66 份全网快照；最大单交换机间隔 0.514 秒；780 行逐源差分。
- 正常 h2 约 2 pps，EMA 到达 1.96 pps；检测样本 5,863.1 pps > 2,000 pps。
- 六台交换机均有 h2 源 drop；h1 没有被封锁。h2 在 s2/s6 的后续转发停止。
- h1 连续 ping 为 64/64；之后 h1 为 3/3，h2 为 0/3。
- flood 结束后普通 h2 ping 仍被丢弃；源封锁没有自动解除。

## 重做命令

这是本次新增的自动采集入口，不冒充用户十月手动输入的命令。从项目目录、已有 Mininet/Ryu 环境运行，`--output` 必须是尚不存在的新目录：

```bash
sudo /usr/bin/python3 capture_task2.py --output todo03/task2-repeat-new
```

脚本默认使用本机 `/home/robot/miniforge3/envs/ceg5101-ryu38/bin/ryu-manager`；其他机器可通过 `CEG_RYU_MANAGER` 指定实际路径。需要现有 OVS 服务和可用图形环境，MiniEdit 窗口在脚本内隐藏。没有重新安装环境。

当前报告的离线重画入口仍为 `python analyze_policy_evidence.py`，读取本目录已保存的这轮数据。若重做生成其他目录，应明确修改绘图脚本的 RUN 选择并保留该次结果，不能覆盖本次原始数据。

Raw OVS tables, controller samples/events, host ping logs, topology and process timings are retained. `capture-results.json` records the original controller hashes and cleanup checks. This repeat is separate from the October data; no old/new observations are spliced.
