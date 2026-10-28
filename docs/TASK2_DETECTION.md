# Task 2：流量监测、EMA 异常检测与源 IP 封锁

[返回完整指南](REPRODUCE.md) · [上一任务](TASK1_TOPOLOGY.md) · [下一任务](TASK3_LINK_COST.md)

## 1. 老师要求什么

监测活跃流量速率，维护 EMA 正常基线；源流量超过阈值时判异常并安装源 IP 防火墙规则，验证异常流量不再转发。用正常 ping 建立基线，用 hping3 ICMP flood 产生异常；参考 anomaly_detection.py（5 分）。

## 2. 我们做了什么，为什么

anomaly_controller.py 继承正常转发控制器；traffic_stats.py 处理累计计数、速率和 EMA。本阶段**只增加检测和封锁，路径仍然是静态最短路**。

交换机给的是累计包数 P，不是实时 pps，所以先计算：

$$r_t=\frac{P_t-P_{t-1}}{t_t-t_{t-1}}.$$

本项目先比较 $r_t>\max(2000,3E_{t-1})$，若正常才更新 $E_t=0.3r_t+0.7E_{t-1}$。异常/封锁样本不更新正常基线。

| 处理 | 为什么需要 |
|---|---|
| 只在源接入交换机计数 | 同一包经过多台交换机不能算多次 |
| 用实际采样间隔，不假设恰好 1 秒 | 控制器调度会有抖动 |
| 以完整流表身份做差分 | 同一个源的多个目的流、不同规则不能互相覆盖计数 |
| 先与旧 EMA 比较，再更新 | 大流量不能先把基线抬高而逃过当前判断 |
| 约 1 秒采样，至少 5 个有效预热样本 | 先建立可用计数起点；操作上 READY 后等至少 8 秒 |
| 排除 ICMP echo reply | 避免将 h6 给异常源回包误判为另一个异常源 |
| 最低阈值 2000pps | 10Mbps、1470B 的正常 UDP 约 850pps，初始低 EMA 时不应仅因它启动就封锁 |
| 全部交换机下发 priority=5000 的源 IPv4 drop | 高于 priority=100/109/110 的转发规则，阻止已存在转发规则继续放行 |

EMA 系数 0.3、倍数 3 与教师参考思想一致；最低阈值、预热和统计修正是本项目实现选择。检测的是异常速率，不能声称仅凭这些参数就准确识别所有真实攻击。

## 3. 完整启动

先按 [共同结束顺序](REPRODUCE.md) 关闭 Task 1，特别是旧 iperf 接收端。使用同一份 .mn 拓扑。

**终端 C：**

~~~bash
cd "$HOME/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
export CEG_RYU_MANAGER="$(command -v ryu-manager)"
mkdir -p local-validation
CEG_CONSOLE="$(mktemp "$PWD/local-validation/task2-controller-XXXXXX.log")"
bash run_anomaly.sh 2>&1 | tee "$CEG_CONSOLE"
~~~

**终端 M：**

~~~bash
cd "$HOME/5101"
sudo service openvswitch-switch start
mkdir -p local-validation
export CEG_EVIDENCE="$(mktemp -d "$PWD/local-validation/task2-manual-XXXXXX")"
printf '%s\n' "$CEG_EVIDENCE"
sudo --preserve-env=CEG_EVIDENCE bash run_miniedit.sh
~~~

MiniEdit：Open 本仓库 todo01/ca2-mesh-my.mn → Run。等终端 C 的 BASELINE READY、DETECTION STARTED，再等至少 8 秒；应看到 warmup 完成、blocked=False。控制器数据在本轮 todo03/run-*。

## 4. 先用正常 ping 看基线

**mininet>：**

~~~text
h2 ping -c 20 -i 0.5 -W 1 10.0.0.6
~~~

h2 每 0.5 秒发一个请求，共 20 个，约 2pps。看终端 C 中 source=10.0.0.2 的 STATS：

- pps 约 2，可能因采样边界有少量波动。
- old_ema 是本次判断前的基线，new_ema 逐步接近正常速率。
- threshold 通常仍为 2000，blocked=False。

**截图 1：**正常 STATS 和 ping 20/20 汇总。正常流能通且未被封锁，是后面异常对照的起点。

## 5. 在合法流持续时引入异常

先读完本节，然后在 mininet> 连续操作。h1 的合法 ping 持续约 40 秒，覆盖正常、异常及后续验证。

~~~text
h1 ping -D -c 80 -i 0.5 -W 1 10.0.0.6 > "$CEG_EVIDENCE/h1-continuous-ping.log" 2>&1 &
sh sleep 3
h2 timeout 8s hping3 -1 --flood 10.0.0.6 > "$CEG_EVIDENCE/h2-flood.log" 2>&1
~~~

- -D 给合法 ping 回复加时间戳，后台运行使 CLI 还能控制 h2。
- hping3 的 -1 选择 ICMP；--flood 快速发送；timeout 限为 8 秒。
- 流量源是这个实验里的 h2，目的为实验 h6；不要把该命令放到普通主机 shell 中或更换为外部地址。

观察终端 C：应出现 BLOCK source=10.0.0.2，pps 超过当时 threshold；随后 blocked=True、drop_pps 非零。**截图 2：**保存 BLOCK 行，包含源地址、当前速率、旧 EMA、阈值。

## 6. 证明真正封锁，同时合法主机仍通

异常命令结束后，在 **mininet>**：

~~~text
sh ovs-ofctl -O OpenFlow13 dump-flows s2 "ip,nw_src=10.0.0.2"
h2 ping -c 3 -W 1 10.0.0.6
sh ovs-ofctl -O OpenFlow13 dump-flows s2 "ip,nw_src=10.0.0.2"
h1 ping -c 3 -W 1 10.0.0.6
sh for s in s1 s2 s3 s4 s5 s6; do ovs-ofctl -O OpenFlow13 dump-flows "$s" "ip,nw_src=10.0.0.2" > "$CEG_EVIDENCE/$s-block.txt"; done
h1 wait
h1 tail -n 8 "$CEG_EVIDENCE/h1-continuous-ping.log"
~~~

要读懂三个证据：

1. s2 有 **priority=5000, ip, nw_src=10.0.0.2, actions=drop**，n_packets 已增加；h2 再 ping 后入口 drop 计数继续增加。
2. h2 的新 ping 预期 0/3，h1 的新 ping 预期 3/3。源地址不同，所以 h1 不匹配 h2 的封锁规则。
3. 六台交换机的保存文件都有 h2 drop。**不要求每台的 drop 计数都增加**：入口 s2 已经丢弃了包，下游看不到这些包反而符合封锁效果。

普通转发规则还存在是正常现象：高优先级 drop 会先匹配。hping3 的 flood 模式自身输出不能独立证明封锁；应以实际 drop 规则/计数和后续探测为证据。

h1 wait 等 h1 的后台 ping 自然结束；它不会停止控制器。后台完整 ping 的丢包和后续三次探测要分别报告，不要用后面的 3/3 覆盖完整窗口里可能出现的少量丢包。

**截图 3：**drop 规则及增长计数、h2 0/3、h1 3/3，以及后台 ping 最终统计。

## 7. 保存什么，怎样判断完成

控制器 todo03/run-* 中保留 events.jsonl、source-rates.jsonl、anomaly-state.json 等；手动证据在终端 M 打印的 CEG_EVIDENCE，控制台日志在 local-validation/task2-controller-*。

原实验曾观测入口 drop 478615 包、h2 后续 0/3、h1 后续 3/3。这些是原机测量，不是搭档必须复现的精确数值。需要重现的是“正常不封 → 超阈值检测 → drop 生效 → h1 保持通信”的因果链。

本阶段不改变链路代价，也没有证明动态改道。完成后 mininet> 输入 exit → MiniEdit Stop 并关闭 → 终端 C Ctrl+C，进入 [Task 3](TASK3_LINK_COST.md)。**源封锁不会因 flood 停止自动解除，因此新任务必须新开一轮。**
