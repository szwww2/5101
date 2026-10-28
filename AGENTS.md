# Collaboration instructions

- Work within this standalone SDN repository. Keep original measured evidence unchanged.
- Read README.md and docs/REPRODUCE.md before changing startup or experiment scripts.
- Use system Python for Mininet/MiniEdit and a separate Python 3.8 Ryu environment.
- Resolve Ryu with runtime_paths.py or CEG_RYU_MANAGER; never hard-code a username.
- Do not run global mn -c, killall, or delete unrelated OVS bridges. Isolated validation uses t4 nodes and checks that pre-existing bridges are preserved.
- Keep historical student measurements separate from new independent validation runs.
- Case C pins only the h5→h6 IPv4 test pair to s5→s6. Disclose this condition and obtain instructional clarification; do not claim it is the unconstrained shortest route.
- Re-run relevant offline tests for code changes. Run a fresh network experiment when the change affects routing or measurement behaviour.
- Preserve MiniEdit attribution and the third-party copyright notice.
