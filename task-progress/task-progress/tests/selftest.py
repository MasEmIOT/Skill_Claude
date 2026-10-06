#!/usr/bin/env python3
"""Self-test for task-progress/scripts/tp.py — runs in a throwaway git repo.
Usage: python3 tests/selftest.py [--keep]   (--keep leaves the sandbox for inspection)"""
import os, re, shutil, subprocess, sys, tempfile

TP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "tp.py")
SANDBOX = tempfile.mkdtemp(prefix="tp-selftest-")
ENV = dict(os.environ, TASK_STATE_PROJECT_ROOT=SANDBOX)
STATE = os.path.join(SANDBOX, ".claude", "task-state")
results = []

def tp(*args, ok=True):
    r = subprocess.run([sys.executable, TP, *args], cwd=SANDBOX, env=ENV, capture_output=True, text=True)
    if ok and r.returncode != 0:
        raise AssertionError(f"tp {' '.join(args)} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r

def git(*a):
    subprocess.run(["git", *a], cwd=SANDBOX, capture_output=True, check=True)

def rd(*p):
    return open(os.path.join(*p), encoding="utf-8").read()

def test(name):
    def deco(fn):
        try:
            fn(); results.append((name, "PASS", ""))
        except AssertionError as e:
            results.append((name, "FAIL", str(e)))
        except Exception as e:
            results.append((name, "ERROR", repr(e)))
        return fn
    return deco

def tdir(tid):
    return os.path.join(STATE, [d for d in os.listdir(STATE) if d.startswith(tid)][0])

git("init", "-q"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
open(os.path.join(SANDBOX, "README.md"), "w").write("# Sandbox project\n")
git("add", "."); git("commit", "-qm", "initial")
ctx = {}

@test("1 init creates identity, directory, all state files, index, checkpoint-001")
def _():
    r = tp("init", "Build IoT Light System", "--project", "Smart Home IoT",
           "--objective", "Remote-controlled light via ESP32 + Firebase",
           "--requirement", "Toggle relay from app", "--acceptance", "Relay toggles remotely",
           "--next", "Create PlatformIO project for ESP32")
    m = re.search(r"TASK-\d{8}-\d{3}", r.stdout); assert m, r.stdout
    ctx["A"] = m.group(0); d = tdir(ctx["A"])
    assert os.path.basename(d).endswith("_build-iot-light-system"), d
    for f in ["TASK.md", "CURRENT_STATE.md", "PROGRESS.md", "DECISIONS.md", "FAILED_ATTEMPTS.md", "BLOCKERS.md",
              "FILES.md", "TESTS.md", "NEXT_STEPS.md", "SESSION_HANDOFF.md", "checkpoints/checkpoint-001.md"]:
        assert os.path.exists(os.path.join(d, f)), f
    t = rd(d, "TASK.md")
    assert f"Task ID: {ctx['A']}" in t and "Status: IN_PROGRESS" in t and "Project: Smart Home IoT" in t
    assert ctx["A"] in rd(STATE, "task-index.md") and ctx["A"] in rd(STATE, "active-tasks.md")

@test("2 simulated work updates state (file, test, progress, next action)")
def _():
    os.makedirs(os.path.join(SANDBOX, "src"), exist_ok=True)
    open(os.path.join(SANDBOX, "src", "main.cpp"), "w").write("void setup(){}\nvoid loop(){}\n")
    tp("add", ctx["A"], "file", "kind=created", "path=src/main.cpp", "note=firmware entry")
    tp("add", ctx["A"], "file", "kind=important", "path=src/main.cpp")
    r = tp("add", ctx["A"], "test", "case=firmware compiles", "command=pio run", "expected=build ok",
           "actual=SUCCESS 3.1s", "result=PASS")
    assert "T-001" in r.stdout
    bad = tp("add", ctx["A"], "test", "case=relay", "command=n/a", "expected=on", "actual=", "result=PASS", ok=False)
    assert bad.returncode != 0, "PASS without real evidence must be rejected"
    tp("set-next", ctx["A"], "Implement WiFi connection in src/main.cpp")
    d = tdir(ctx["A"])
    assert "`src/main.cpp`" in rd(d, "FILES.md")
    assert "Implement WiFi" in rd(d, "CURRENT_STATE.md") and "Implement WiFi" in rd(d, "NEXT_STEPS.md")
    assert "T-002" not in rd(d, "TESTS.md")

@test("3 failed attempt recorded with all fields")
def _():
    tp("add", ctx["A"], "failed", "title=Upload via COM3", "problem=ESP32 upload failed", "approach=Used COM3 directly",
       "result=Port busy", "why=Serial monitor held the port", "lesson=Check port ownership first",
       "next=Close monitor, retry")
    s = rd(tdir(ctx["A"]), "FAILED_ATTEMPTS.md")
    for k in ["F-001", "Problem:", "Approach attempted:", "Why it failed:", "What was learned:", "Recommended next approach:"]:
        assert k in s, k

@test("4 decision recorded; supersede updates status in place")
def _():
    tp("add", ctx["A"], "decision", "title=Use Firebase RTDB", "decision=Firebase Realtime Database",
       "reason=Free tier, realtime push", "alternatives=MQTT, HTTP REST", "consequence=Needs auth handling")
    tp("set-entry", ctx["A"], "D-001", "Status", "ACTIVE (reconfirmed)")
    s = rd(tdir(ctx["A"]), "DECISIONS.md")
    assert "## D-001: Use Firebase RTDB" in s and "Alternatives considered: MQTT, HTTP REST" in s
    assert "- Status: ACTIVE (reconfirmed)" in s

@test("5 checkpoint: numbered, immutable, has events + git + next action")
def _():
    summ = os.path.join(SANDBOX, "summary.md")
    open(summ, "w").write("## Completed since previous checkpoint\n\n- [VERIFIED] firmware compiles — evidence: T-001\n")
    r = tp("checkpoint", ctx["A"], "--summary-file", summ, "--session", "session-A")
    assert "checkpoint-002" in r.stdout
    p = os.path.join(tdir(ctx["A"]), "checkpoints", "checkpoint-002.md"); s = rd(p)
    for k in ["Task ID: " + ctx["A"], "session-A", "D-001", "F-001", "T-001", "Branch:", "Implement WiFi"]:
        assert k in s, k
    assert not os.access(p, os.W_OK) or os.geteuid() == 0, "checkpoint should be read-only"
    assert "checkpoint-002" in rd(tdir(ctx["A"]), "SESSION_HANDOFF.md")

@test("6 Session B: resume by ID and by name resolves same task, pack restores context")
def _():
    by_id = tp("resume-pack", ctx["A"]).stdout
    by_name = tp("resume-pack", "Build IoT Light System").stdout
    by_slug = tp("resume-pack", "build-iot-light-system").stdout
    assert by_id.splitlines()[0] == by_name.splitlines()[0] == by_slug.splitlines()[0]
    for k in ["Use Firebase RTDB", "Upload via COM3", "firmware compiles", "Implement WiFi", "checkpoint-002", "VERIFY"]:
        assert k in by_id, k

@test("7 multi-task isolation: resume B never contains A's state; identical names need ID")
def _():
    r = tp("init", "Flutter Monitoring App", "--next", "Scaffold flutter project")
    ctx["B"] = re.search(r"TASK-\d{8}-\d{3}", r.stdout).group(0)
    assert ctx["B"] != ctx["A"]
    tp("add", ctx["B"], "decision", "title=Use Riverpod", "decision=Riverpod", "reason=testable",
       "alternatives=Bloc", "consequence=-")
    pb = tp("resume-pack", ctx["B"]).stdout
    for leak in [ctx["A"], "Firebase RTDB", "COM3", "Implement WiFi"]:
        assert leak not in pb, f"leak from A into B: {leak}"
    assert "Use Riverpod" not in tp("resume-pack", ctx["A"]).stdout
    tp("init", "Build App"); tp("init", "Build App")
    amb = tp("resume-pack", "Build App", ok=False)
    assert amb.returncode == 2 and "AMBIGUOUS" in amb.stderr, amb.stderr

@test("8 mismatch: state says file exists but it was deleted -> detected")
def _():
    os.remove(os.path.join(SANDBOX, "src", "main.cpp"))
    r = tp("verify", ctx["A"], ok=False)
    assert r.returncode == 5 and "src/main.cpp" in r.stdout and "MISMATCH" in r.stdout, r.stdout
    open(os.path.join(SANDBOX, "src", "main.cpp"), "w").write("restored\n")
    assert tp("verify", ctx["A"]).returncode == 0
    p = os.path.join(tdir(ctx["A"]), "checkpoints", "checkpoint-002.md")
    os.chmod(p, 0o644); open(p, "a").write("\n(tampered)\n")
    r = tp("verify", ctx["A"], ok=False)
    assert "content changed after creation" in r.stdout, r.stdout
    os.chmod(p, 0o644); s = rd(p).replace("\n(tampered)\n", ""); open(p, "w").write(s); os.chmod(p, 0o444)
    assert tp("verify", ctx["A"]).returncode == 0

@test("9 compact: old checkpoints archived (not deleted), hashes still verify, synthesis scaffold")
def _():
    for i in range(4):
        tp("checkpoint", ctx["A"], "--session", f"s{i}")
    d = tdir(ctx["A"])
    before = sorted(os.listdir(os.path.join(d, "checkpoints")))
    tp("compact", ctx["A"], "--keep", "2")
    live = [f for f in os.listdir(os.path.join(d, "checkpoints")) if f.startswith("checkpoint-")]
    arch = [f for f in os.listdir(os.path.join(d, "history", "archive")) if f.startswith("checkpoint-")]
    assert len(live) == 2 and len(arch) == 4, (live, arch)
    assert "Synthesis" in rd(d, "history", "COMPACTED_HISTORY.md")
    assert tp("verify", ctx["A"]).returncode == 0
    assert "checkpoint-007" in tp("checkpoint", ctx["A"]).stdout, "numbering must continue after compaction"
    assert "COMPACTED_HISTORY" in tp("resume-pack", ctx["A"]).stdout

@test("10 recovery: lost CURRENT_STATE + corrupt TASK.md + lost index are rebuilt and marked RECONSTRUCTED")
def _():
    d = tdir(ctx["A"])
    os.remove(os.path.join(d, "CURRENT_STATE.md"))
    open(os.path.join(d, "TASK.md"), "w").write("garbage")
    os.remove(os.path.join(STATE, "task-index.md"))
    r = tp("recover", ctx["A"])
    assert "CURRENT_STATE.md" in r.stdout and "TASK.md" in r.stdout
    assert "RECONSTRUCTED" in rd(d, "CURRENT_STATE.md") and "RECONSTRUCTED" in rd(d, "TASK.md")
    assert "Task Name: Build IoT Light System" in rd(d, "TASK.md"), "name must be recovered from checkpoint"
    assert f"Task ID: {ctx['A']}" in rd(d, "TASK.md") and "Status: PAUSED" in rd(d, "TASK.md")
    assert any(f.startswith("TASK.md.corrupt-") for f in os.listdir(d)), "corrupt original must be kept"
    assert os.path.exists(os.path.join(STATE, "task-index.md")) and os.path.exists(os.path.join(d, "RECOVERY_REPORT.md"))
    # next action survived via latest checkpoint
    assert "Implement WiFi" in rd(d, "CURRENT_STATE.md")
    # lost directory entirely -> recreate by ID + name
    shutil.rmtree(tdir(ctx["B"]))
    tp("recover", ctx["B"], "--name", "Flutter Monitoring App")
    assert "RECONSTRUCTED" in rd(tdir(ctx["B"]), "TASK.md")

@test("11 close gating: cannot mark COMPLETED without evidence; can after")
def _():
    r = tp("init", "Tiny Close Test", "--acceptance", "Script prints hello")
    tid = re.search(r"TASK-\d{8}-\d{3}", r.stdout).group(0)
    assert tp("set-status", tid, "COMPLETED", ok=False).returncode == 4
    tp("add", tid, "test", "case=prints hello", "command=python3 hello.py", "expected=hello", "actual=hello", "result=PASS")
    d = tdir(tid); p = os.path.join(d, "TASK.md")
    txt = rd(p).replace("- [ ] Script prints hello", "- [x] Script prints hello — evidence: T-001"); open(p, "w").write(txt)
    tp("set-status", tid, "COMPLETED")
    assert tid not in rd(STATE, "active-tasks.md") and tid in rd(STATE, "task-index.md")

w = max(len(n) for n, _, _ in results)
print("\ntask-progress self-test\n" + "=" * 60)
for n, s, msg in results:
    print(f"{s:5}  {n}")
    if msg:
        print("       " + msg.replace("\n", "\n       "))
fails = sum(1 for _, s, _ in results if s != "PASS")
print("=" * 60 + f"\n{len(results) - fails}/{len(results)} passed.  sandbox: {SANDBOX}")
if "--keep" not in sys.argv:
    shutil.rmtree(SANDBOX, ignore_errors=True)
sys.exit(1 if fails else 0)
