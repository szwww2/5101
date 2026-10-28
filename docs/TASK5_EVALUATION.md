# Task 5：性能评价、已有结果复现与新实验绘图

[返回完整指南](REPRODUCE.md) · [上一任务](TASK4_REROUTING.md)

## 1. 老师要求什么

报告放入拓扑截图；评价集成控制器在异常前、异常中、异常后的表现；绘制：

1. Dynamic Link Cost（normalized cost）vs. Time。
2. Packet Loss（%）vs. Time。
3. Throughput（Mbps）vs. Time。

解释路由代价、路径选择、丢包和吞吐的变化。教师原文没有规定必须三次重复、固定 60 秒或做参数扫描；这些应按想证明的结论选择。

## 2. 我们做了什么，为什么

我们用 Task 4 的原始接收报告、端口代价和路径证据绘制 A/B/C 时间曲线；另将 B 做了三轮，展示同样条件下的波动。拓扑截图来自实际 MiniEdit，不是示意替代品。

| 指标 | 计算/来源 | 不能混淆的量 |
|---|---|---|
| 归一化成本 | C(t)/C0；A 除以 10，B 除以 14，C 除以 20 | 不是利用率，也不是除以本次最大成本 |
| 一秒 UDP 丢包率 | 100×接收端该窗口 lost/total | 不能用发送目标速率推算，也不把 ICMP 混进 UDP |
| 接收吞吐 | receiver.log 每秒的 Mbps | -b 10000000 只是提供负载 |
| 实际路径 | dataplane-samples.jsonl | 控制器希望走哪条路不等于包实际走哪条路 |
| 整轮丢包 | 整轮 lost/total | 不对各秒百分比直接做未加权平均 |

保持原始一秒窗口，避免平滑掩盖短暂丢包。图上标出计划异常窗口、检测、惩罚恢复和路径提交事件。控制器和接收端时钟约按秒对齐，不声称毫秒级因果先后。

为什么要同时看整轮与瞬时值：B1 整轮 43/51024，仅约 0.0843%，但 12–13 秒有 43/848≈5.07% 丢包，接收吞吐降到 9.47Mbps。最终三个稳定窗口均 0% 不能代表切换瞬间也 0%。

## 3. 已有数据在哪里

| 轮次 | todo05 下的目录 | 原整轮 UDP 丢包 |
|---|---|---:|
| A | run-A-20261016-145805-CPT5A8 | 0/51024 |
| B1 | run-B-20261016-144402-YuFNPf | 43/51024 |
| B2 | run-B-20261017-105957-DfB6RZ | 78/51024 |
| B3 | run-B-20261017-111734-b9lfbt | 22/51024 |
| C | run-C-20261016-153103-Ho9Y7P | 0/51024 |

[原图表和分析](../todo06/task5-final-20261017/) 包含三场景三类曲线、B 路径/代价图、B 三轮比较、CSV 和文字。中英文报告在 [报告目录](../report/review-20261017/)。

B1 原始 results.json 的 FAIL 来自当时检查器错误地要求外部控制器有 ryu.log；另存的完整证据复核为 PASS，原文件未篡改。旧分析使用冻结事件和复核结果。

## 4. 复现“已有结果”：无需重跑网络

以下在 **Ubuntu shell**，不在 mininet>，不需要 sudo，也不用启动 OVS：

~~~bash
cd "$HOME/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
CEG_FIGURES="todo06/reproduced-three-cases-$(date +%Y%m%d-%H%M%S)"
python -B analyze_task5.py --output "$CEG_FIGURES"
~~~

它固定读取上表 A、B1、C，输出三场景总图、各场景图、B 路径/成本图、CSV 和 analysis-summary.json。输出目录必须不存在；重新运行请换新名字。

重画已有 B 三轮比较：

~~~bash
CEG_REPEAT_FIGURES="todo06/reproduced-B-comparison-$(date +%Y%m%d-%H%M%S)"
python -B compare_task5_b.py \
  --run run-B-20261016-144402-YuFNPf \
  --run run-B-20261017-105957-DfB6RZ \
  --run run-B-20261017-111734-b9lfbt \
  --output "$CEG_REPEAT_FIGURES"
~~~

比较脚本同时冻结输入并记录 SHA256。预期仍是 43、78、22 个丢包；三轮平均整轮丢包率约 0.0934%，样本标准差约 0.0554 个百分点。机器不同可能使图像字节或字体不同，但原始输入数值不应改变。

**这两条是重画旧数据，不是分析“最新的一轮”。** 原 analyze_task5.py 的 TRIALS 固定了旧目录，B 图还保留 B1 的特定标注；compare_task5_b.py 依赖特定的复核/冻结文件。不要仅替换目录名就假装它们自动支持任意新结果。

## 5. 分析搭档自己新跑的 A/B/C

### 5.1 在什么时候做

每完成 Task 4 一种场景，看到最终 PASS 后，在**结束网络和控制器之前**用终端 O 执行本节。这样可以冻结完整的测量证据，而不会混入人为 Stop 造成的拓扑退出错误；这一步不发流量、不修改流表。

三种场景分别执行一次，每次只改 CEG_RUN 为本轮目录。图与原始数据副本保存在新的 todo06/reproduced-new-*，不会覆盖历史结果。冻存后再按共同顺序结束该场景。

### 5.2 指定本轮输入

终端 O：

~~~bash
cd "$HOME/5101"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate ceg5101-ryu38
export CEG_RUN="$PWD/todo05/这里替换为本轮真实run目录名"
test -f "$CEG_RUN/results.json"
python -m json.tool "$CEG_RUN/results.json"
~~~

检查 scenario、status、路径与控制台一致。这里故意让你明确选择输入，不自动挑最新目录。若 FAIL，先保留失败证据并诊断，不进行下方 PASS 分析或人工改状态。

### 5.3 一次性冻结、复核、导出 CSV 并画三条新曲线

整个命令块复制到 **Ubuntu Bash shell**。这是调用现有离线核验函数并生成本轮图表的分析命令，不修改控制器，也不会向新图写入 B1 的固定丢包标注。

~~~bash
python -B - <<'PY'
import csv
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from task4_evidence import review_saved

root = Path.cwd()
run = Path(os.environ["CEG_RUN"]).resolve()
assert (root / "task4_evidence.py").is_file(), "Run from repository root"
assert run.is_dir(), "Select an existing experiment directory"
original = json.loads((run / "results.json").read_text())
assert original["status"] == "PASS", "Preserve and diagnose this failed run first"
(root / "todo06").mkdir(exist_ok=True)
out = Path(tempfile.mkdtemp(prefix="reproduced-new-", dir=root / "todo06"))
frozen = out / "inputs"
names = ["results.json", "sender.log", "receiver.log", "continuous-ping.log",
         "post-pings.txt", "dataplane-samples.jsonl", "link-costs.jsonl",
         "events.jsonl", "evidence/initial.json", "evidence/recovered.json"]
if (run / "ryu.log").is_file():
    names.append("ryu.log")
hashes = {}
for name in names:
    dest = frozen / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(run / name, dest)
    hashes[name] = hashlib.sha256(dest.read_bytes()).hexdigest()

review = review_saved(frozen)
case = review["scenario"]
edge, base = {"A": ("2>3", 10), "B": ("2>6", 14), "C": ("5>6", 20)}[case]
origin = original["legitimate_started"]
attack_on = original["attack_started"] - origin
attack_off = attack_on + 14
def lines(name):
    return [json.loads(s) for s in (frozen / name).read_text().splitlines()]
costs = []
for item in lines("link-costs.jsonl"):
    seconds = item["time"] - origin
    if 0 <= seconds <= 60 and item["ready"] and edge in item["links"]:
        link = item["links"][edge]
        assert link["base"] == base
        costs.append(dict(seconds=seconds, normalized=link["cost"] / base,
                          cost=link["cost"], mbps=link["received_bps"] / 1e6,
                          penalty=link["penalty"]))
assert costs, "Missing measured costs"
receiver = [dict(r, loss_percent=100 * r["lost"] / r["total"])
            for r in review["receiver_intervals"]]
assert len(receiver) == 60, "Inspect receiver intervals before plotting"
assert sum(r["lost"] for r in receiver) == review["lost"]
paths = [dict(seconds=s["elapsed"], path=s["actual_path"], vlan=s["active_vlan"])
         for s in lines("dataplane-samples.jsonl")]
events = []
for event in lines("events.jsonl"):
    seconds = event["time"] - origin
    relevant = event["event"] in ("block", "penalty_added", "penalty_restored")
    relevant |= event["event"] == "route_committed" and event.get("flow") == "10.0.0.1>10.0.0.6"
    if relevant and 0 <= seconds <= 60:
        events.append(dict(seconds=seconds, **event))
def write_csv(name, rows):
    with (out / name).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
write_csv("link-cost.csv", costs)
write_csv("receiver.csv", receiver)
write_csv("paths.csv", paths)
(out / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")

fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
axes[0].step([r["seconds"] for r in costs], [r["normalized"] for r in costs], where="post")
axes[0].set_ylabel("Link cost / base")
bins = [receiver[0]["start"]] + [r["end"] for r in receiver]
axes[1].stairs([r["loss_percent"] for r in receiver], bins, baseline=None, color="firebrick")
axes[1].set_ylabel("UDP loss (%)")
axes[2].stairs([r["mbps"] for r in receiver], bins, baseline=None, color="seagreen")
axes[2].axhline(10, color="gray", linestyle="--", label="Offered load 10 Mbps")
axes[2].set_ylabel("Receiver Mbps")
axes[2].set_xlabel("Seconds; receiver bins approximately aligned to sender start")
axes[2].legend()
for ax in axes:
    ax.axvspan(attack_on, attack_off, color="orange", alpha=0.15)
    ax.set_xlim(0, 60)
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.2)
    for event in events:
        if event["event"] in ("block", "penalty_restored"):
            ax.axvline(event["seconds"], color="red" if event["event"] == "block" else "green", linestyle=":")
        elif event["event"] == "route_committed":
            ax.axvline(event["seconds"], color="purple", linestyle="-.")
fig.suptitle("New case " + case + " | link " + edge + " | " + run.name, fontsize=10)
fig.tight_layout()
fig.savefig(out / "timeseries.png", dpi=180)
fig.savefig(out / "timeseries.svg")
plt.close(fig)
summary = dict(scope="New reproduction; separate from historical student measurements",
               source_run=str(run), frozen_sha256=hashes, review=review,
               normalization="C/base; base=" + str(base),
               whole_udp_loss_percent=100 * review["lost"] / review["total"],
               peak_one_second_loss_percent=max(r["loss_percent"] for r in receiver),
               min_one_second_receiver_mbps=min(r["mbps"] for r in receiver),
               timing="Sender start; receiver bins aligned only approximately; flood stop is planned timeout",
               case_c_test_pair_pinned=case == "C")
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print("Offline evidence review:", review["status"])
print("Paths:", review["initial_path"], review["during_path"], review["recovered_path"])
print("UDP lost/total:", review["lost"], review["total"])
print("Output:", out)
PY
~~~

预期打印 Offline evidence review: PASS，并给出本轮路径和真实丢包数。PNG/SVG 的阴影表示计划异常期，红线是 BLOCK，绿线是惩罚恢复，紫线是合法流路径提交；使用本轮事件，不固定事件秒数。纵轴从零开始，便于阅读；查看 receiver.csv 可读出小幅波动的准确数值。

若检查失败，输出目录里的 inputs 已保留诊断输入；不要删除断言来凑图。先查缺失接收日志、没有完整 60 秒、源未封锁、未恢复或拓扑退出错误等原因。该命令要求新版本 run 的 legitimate_started/attack_started 字段；历史 B1 请用第 4 节的专门处理。

### 5.4 保存和比较新结果

每个场景保存 timeseries.png/svg、四类数据/事件文件、summary.json 和 inputs。截图另外保留拓扑、BLOCK/ROUTE、最终汇总，并记录 Git commit。

如要重复 B，先完成整个“结束→新控制器→新网络→预热→60 秒→冻结分析”流程。比较每轮整轮 lost/total、最高一秒丢包、最低一秒接收吞吐和实际路径；不要只挑最好一轮。现成 compare_task5_b.py 面向旧复核文件格式，本节的新结果可从各自 summary.json/receiver.csv 汇总，不能把旧比较图当成新测量。

## 6. 图该怎么解释

- A/C：异常边加惩罚，异常源被封锁；原合法路径未经过该边，因此保持原路。合法流不必为了“展示改道”故意换到更贵路径。
- B：原路线受惩罚，备选更便宜；实际流表与计数证明换路；惩罚撤销后恢复原路。
- 封锁后目标边速率下降但成本仍高：入口 drop 活动仍表示异常源在发，惩罚未达到安静期恢复条件。
- 短暂丢包不等于持续断连；但每秒仍有接收也不能证明每个包无损。把稳定窗口、切换窗口和整轮统计分开。
- 10Mbps 成功不证明 40Mbps 饱和吞吐；没有“同样封锁但禁用改道”的对照，不能量化改道的独立性能收益。
- 原连续 ping 为 121 发 120 收，尾包原因未抓包确认；保留 ICMP 统计，不用 UDP 的零丢包替代。
- C 的固定测试对条件必须保留；成本/路径恢复与源仍被封锁并不矛盾。

## 7. 完成标准与还需哪些实验

已有数据足够复现旧报告的图表；搭档按 Task 4 新跑三场景后，可用本页流程形成自己的证据，不必复制原机的精确丢包数。要完成老师当前要求，关键是三类时间图、异常前/中/后对照、真实路径与封锁证据以及合理解释。

若进一步想声称“改道更好”“参数最优”“可承受高负载”，才分别补禁用改道对照、参数扫描、提供负载扫描。C 的教学接受度需要向教师/TA 确认，重跑本身不能解决这个问题。

整理报告时加入新拓扑截图、实际实验条件、每轮结果及限制；保留 AI 辅助声明。现场 demo 准备见 [展示建议](DEMO_PLAN.md)，实际时长与地点以课程通知为准。
