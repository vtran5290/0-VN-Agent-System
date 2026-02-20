# Ops playbook for Claude Code

Goal: produce weekly packet with minimal edits.

Steps:
1) Copy last week manual_inputs.json → manual_inputs_prev.json
2) Update manual_inputs.json with 8 core numbers + overrides
3) Update weekly_notes.json with facts-only policy/earnings items
4) Run: `python -m src.report.weekly`
5) Verify outputs exist and end sections present

Key: Claude Code chỉ cần đọc file này + chạy commands.
