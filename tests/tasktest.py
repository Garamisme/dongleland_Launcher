"""tasktest.py — Fabric 업데이트·Java 설치의 취소 (네트워크·실제 다운로드 없이).

  1. 받다 만 Java 런타임(java.exe 는 있는데 .version 이 없음)은 '설치 안 됨'
  2. Java 설치는 시작할 때 묵은 취소 신호를 지우고, 취소되면 '실패'가 아니라 '취소'
  3. Fabric 업데이트 취소는 상태 전환 전에 멈춰 옛 로더를 그대로 둔다
  4. 브릿지는 취소를 프론트에 Fabric = -2, Java = "cancelled" 로 알린다
"""

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tasktest-")

import api  # noqa: E402
import game_installer as gi  # noqa: E402

fails = []


def check(name, cond):
    print(("✅ " if cond else "❌ [FAIL] ") + name)
    if not cond:
        fails.append(name)


# ── 1. 받다 만 런타임 ───────────────────────────────────────────────────────
mc = tempfile.mkdtemp(prefix="mc-")
plat = os.path.join(mc, "runtime", "java-x", "windows-x64")
java = os.path.join(plat, "java-x", "bin", "java.exe")
os.makedirs(os.path.dirname(java))
open(java, "w").close()
gi.instance.installed_version_id = lambda *a, **k: "fabric-loader-x"
gi.instance.instance_dir = lambda *a, **k: mc
gi._runtime.get_version_runtime_information = lambda vid, d: {"name": "java-x", "javaMajorVersion": 25}
gi._runtime.get_executable_path = lambda name, d: java
check("java.exe 만 있고 .version 없음 → 미설치", gi.runtime_info()["installed"] is False)
open(os.path.join(plat, ".version"), "w").close()
check(".version 까지 있음 → 설치됨", gi.runtime_info()["installed"] is True)
os.remove(os.path.join(plat, ".version"))

# ── 2. Java 설치 취소 ───────────────────────────────────────────────────────
calls = []


def install_ok(name, d, callback):
    callback["setStatus"]("Download a")      # 묵은 취소 신호가 남아 있으면 여기서 터진다
    calls.append("ok")


gi.request_cancel()                          # 이전 작업이 남긴 취소 신호
gi._runtime.install_jvm_runtime = install_ok
try:
    gi.ensure_runtime()
    check("묵은 취소 신호를 지우고 설치 진행", calls == ["ok"])
except Exception as e:
    check("묵은 취소 신호를 지우고 설치 진행 (" + type(e).__name__ + ")", False)


def install_cancelled(name, d, callback):
    gi.request_cancel()
    callback["setStatus"]("Download b")


gi._runtime.install_jvm_runtime = install_cancelled
try:
    gi.ensure_runtime()
    check("Java 취소 → InstallCancelled", False)
except gi.InstallCancelled:
    check("Java 취소 → InstallCancelled (실패로 둔갑하지 않음)", True)
except Exception as e:
    check("Java 취소 → InstallCancelled (" + type(e).__name__ + ")", False)

# ── 3. Fabric 업데이트 취소 → 옛 로더 유지 ───────────────────────────────────
switched = []
gi._assert_installable = lambda: None
gi.instance.load_state = lambda *a, **k: {"fabric_loader_version": "0.1", "installed_version_id": "old"}
gi.instance.is_version_ready = lambda *a, **k: True
gi.instance.ensure_dirs = lambda *a, **k: mc
gi.instance.set_installed_version_id = lambda *a, **k: switched.append(a)
gi._pick_stable_loader = lambda: "0.2"
gi._resolve_installer_java = lambda *a: None


def fabric_cancelled(mcv, d, loader_version, callback, java):
    gi.request_cancel()
    callback["setStatus"]("Download Libraries")


gi._fabric.install_fabric = fabric_cancelled
try:
    gi.update_loader()
    check("Fabric 취소 → InstallCancelled", False)
except gi.InstallCancelled:
    check("Fabric 취소 → InstallCancelled", True)
check("Fabric 취소 → 상태 전환 안 함(옛 로더 유지)", switched == [])

# ── 4. 브릿지가 프론트에 알리는 값 ───────────────────────────────────────────
pushed = []


class Win:
    def evaluate_js(self, js):
        pushed.append(js)


def run_bridge(start, flag):
    a = api.Api.__new__(api.Api)
    a._window = Win()
    a._client_installing = False
    start(a)
    for _ in range(100):
        if not getattr(a, flag, False):
            break
        time.sleep(0.02)


def raise_cancel(*a, **k):
    raise gi.InstallCancelled()


gi.update_loader = raise_cancel
run_bridge(lambda a: a.update_fabric_async(), "_fabric_updating")
check("Fabric 취소 → onFabricUpdate(-2, …)", any("onFabricUpdate(-2" in j for j in pushed))

pushed.clear()
gi.runtime_info = lambda *a, **k: {"ok": True}
gi.ensure_runtime = raise_cancel
run_bridge(lambda a: a.install_java_async(), "_java_installing")
check('Java 취소 → onJavaInstall("cancelled", …)', any('onJavaInstall("cancelled"' in j for j in pushed))

a = api.Api.__new__(api.Api)
a._java_installing = True
check("Java 설치 중에도 취소 요청이 받아들여짐", a.cancel_install().get("ok") is True)

print(f"\n{len(fails)} 실패" if fails else "\n전부 통과")
sys.exit(1 if fails else 0)
