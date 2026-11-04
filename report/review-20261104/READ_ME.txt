CEG5101 CA2 中英文报告：2026-11-04 说明补充版

两版各18页，12幅原有截图/图表。测量仍来自2026-10-11、16、17；本次未运行新实验。
第4页说明Task2轮询流表统计，Task3再加入端口统计。
新增第5页：原hping3命令逐项解释；traffic_stats.py与anomaly_controller.py函数入口；
TCP 127.0.0.1:6653控制连接、OpenFlow 1.3 FlowMod下发、s2优先级5000与110匹配比较；
h2请求在s2丢弃，h1源IP不同仍通。封源IP而非断开链路或关闭h6。
原17页版仍保留在相邻review-20261017目录。

页码：1摘要；2-3拓扑/基线；4-5检测/封锁；6动态代价；7-10改道/A/B/C；
11-16性能评价；17结论/限制/AI声明/参考；18复现和证据。

PDF为已检查版。HTML与assets一起保存，可阅读和编辑；report-content.json为中英文结构化内容。
figure-provenance.json记录12幅图来源哈希；source-provenance.json和REPORT_VALIDATION.json记录核验。
本人原命令操作文档见MY_EXPERIMENT_REPLAY.md（Git仓库位于docs/）。
成员与分工按用户要求暂不加入；C固定测试对安排仍需教师/TA确认。

English: 18 pages per language. Page 5 explains the original flood command and the path from
EMA decisions to OpenFlow source blocking. No new measurements were generated.
Keep HTML files with assets. The original 17-page report remains in review-20261017.
