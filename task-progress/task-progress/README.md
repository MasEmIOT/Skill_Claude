# task-progress — Persistent task state cho Claude Code

Mỗi task = một thư mục state độc lập, định danh bằng Task ID. Làm TASK-A ở Session A, đóng session,
mở Session B, gõ `/task-progress resume TASK-A` → Claude nạp đúng state của TASK-A, đối chiếu với code/git
thực tế, in tóm tắt và làm tiếp NEXT IMMEDIATE ACTION.

## Cài đặt
```bash
# theo project (khuyến nghị)
mkdir -p .claude/skills && cp -r task-progress .claude/skills/
# hoặc cá nhân, dùng cho mọi project
mkdir -p ~/.claude/skills && cp -r task-progress ~/.claude/skills/
```
Tuỳ chọn (nên làm):
- Dán block trong `references/integration.md` vào `CLAUDE.md` của project → cập nhật state liên tục ổn định hơn.
- Gộp `hooks/settings.example.json` vào `.claude/settings.json` → mỗi session mới Claude thấy danh sách task đang active.
- Quyết định commit hay `.gitignore` thư mục `.claude/task-state/`.

Yêu cầu: Python ≥ 3.8 (chỉ thư viện chuẩn), git (không bắt buộc). Trên Windows có thể cần `python` thay cho `python3`.

## Lệnh
```
/task-progress init "<tên task>"
/task-progress resume "<tên hoặc TASK-ID>"
/task-progress checkpoint "<tên hoặc TASK-ID>"
/task-progress status | update | handoff | compact | close "<tên hoặc TASK-ID>"
```

## Cấu trúc
```
task-progress/
├── SKILL.md                         # protocol cho Claude (modes, rules, continuous updates)
├── scripts/tp.py                    # phần deterministic: ID, resolve, entries, checkpoint, verify, compact, recover
├── templates/                       # 10 state file + checkpoint summary
├── references/
│   ├── state-format.md              # schema từng file
│   ├── reconciliation-and-recovery.md
│   └── integration.md               # CLAUDE.md block, hooks, concurrency, limitations
├── hooks/settings.example.json
├── tests/selftest.py                # 11 kịch bản
└── examples/                        # state thật sinh từ một lần chạy Session A → B + WALKTHROUGH.md
```

## Self-test
```bash
python3 tests/selftest.py          # --keep để giữ lại sandbox
```
