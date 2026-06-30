# -*- coding: utf-8 -*-
"""
동글랜드 모드 설치 도우미 v2  —  메인 앱
작성자: Garamisme
"""

import os
import sys
import json
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont

import preflight
import modrinth_api
from mod_catalog import (
    MODS, VISIBLE_MODS, MOD_BY_ID, CATEGORIES, CATEGORY_COLOR
)
from modrinth_api import ModRegistry

# ── 상수 ────────────────────────────────────────────────────────────────────

APP_VERSION  = "2.0.4"
APP_AUTHOR   = "Garamisme"
GAME_VERSION = "26.1.2"
LOADER       = "fabric"
ACCENT       = "#10897F"   # 차분한 틸 — 강조는 이 색 하나로 통일
ACCENT_DARK  = "#0C6B63"
SELECT_HL    = "#10897F"   # 사이드바/카테고리 선택 강조 (틸 — ACCENT와 통일)

THEMES = {
    "light": {
        "bg":         "#FAFAFA",   # 거의 흰색에 가까운 미니멀 배경
        "surface":    "#FFFFFF",
        "surface2":   "#F4F4F5",
        "sidebar":    "#FFFFFF",   # 사이드바도 밝게 — 여백으로 구분
        "sidebar_fg": "#52525B",
        "sidebar_hl": "#F4F4F5",
        "text":       "#27272A",
        "text2":      "#71717A",
        "border":     "#ECECEE",   # 선은 거의 안 보이게
        "border2":    "#E4E4E7",
        "tag_bg":     "#FFFFFF",
        "tag_fg":     "#A1A1AA",   # 태그는 옅은 회색 텍스트만
        "row_hover":  "#F7F7F8",
        "header_bg":  "#FFFFFF",
        "header_fg":  "#A1A1AA",
        "entry_bg":   "#F4F4F5",
        "scroll_trough": "#FAFAFA",
        "scroll_thumb":  "#E0E0E3",
        "scroll_hover":  "#CACAD0",
    },
    "dark": {
        "bg":         "#18181B",   # 부드러운 차콜 (순흑 아님)
        "surface":    "#1F1F23",
        "surface2":   "#27272A",
        "sidebar":    "#18181B",   # 사이드바도 배경과 동일 톤
        "sidebar_fg": "#A1A1AA",
        "sidebar_hl": "#27272A",
        "text":       "#E4E4E7",
        "text2":      "#8B8B92",
        "border":     "#2A2A2E",   # 선 거의 안 보이게
        "border2":    "#323237",
        "tag_bg":     "#1F1F23",
        "tag_fg":     "#71717A",
        "row_hover":  "#222226",
        "header_bg":  "#18181B",
        "header_fg":  "#71717A",
        "entry_bg":   "#27272A",
        "scroll_trough": "#18181B",
        "scroll_thumb":  "#3A3A40",
        "scroll_hover":  "#4A4A52",
    },
}

# 버튼 색: 강조(설치)만 ACCENT, 나머지는 무채색으로 차분하게
BTN_COLORS = {
    "install":   ("#10897F", "#FFFFFF"),   # 강조색
    "installed": ("#E4E4E7", "#71717A"),   # 옅은 회색 (완료 = 비활성 느낌)
    "update":    ("#71717A", "#FFFFFF"),   # 중간 회색
    "conflict":  ("#D4D4D8", "#A1A1AA"),   # 옅은 회색 (불가)
    "checking":  ("#E4E4E7", "#A1A1AA"),
}

FONT_NORMAL = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_SMALL  = ("Segoe UI", 9)
FONT_TITLE  = ("Segoe UI", 14, "bold")


# ── 유틸 ────────────────────────────────────────────────────────────────────

def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _system_is_dark() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return val == 0
    except Exception:
        return False


# ── 툴팁 ────────────────────────────────────────────────────────────────────

class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text   = text
        self._tip    = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._tip, text=self._text,
            background="#FFFBCC", relief="solid", borderwidth=1,
            font=FONT_SMALL, padx=6, pady=3,
        ).pack()

    def _hide(self, _event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


# ── 커스텀 스크롤바 (테마 색상 적용 가능) ──────────────────────────────────────

class ThemedScrollbar(tk.Canvas):
    """tk.Canvas 로 직접 그린 세로 스크롤바.
    ttk.Scrollbar 와 달리 트랙/썸 색을 테마에 맞출 수 있다.

    yscrollcommand=self.set / command 연결은 ttk.Scrollbar 와 동일한 인터페이스.
    """

    def __init__(self, master, command, trough, thumb, thumb_hover, width=10):
        super().__init__(master, width=width, highlightthickness=0,
                         bg=trough, bd=0)
        self._command   = command          # 보통 canvas.yview
        self._trough    = trough
        self._thumb     = thumb
        self._thumb_hl  = thumb_hover
        self._width     = width
        self._lo, self._hi = 0.0, 1.0
        self._thumb_id  = None
        self._dragging  = False
        self._drag_offset = 0

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_dragging", False))
        self.bind("<Enter>", lambda e: self._set_thumb_color(self._thumb_hl))
        self.bind("<Leave>", lambda e: self._set_thumb_color(self._thumb)
                  if not self._dragging else None)

    # scrollbar.set(lo, hi) — canvas 가 호출
    def set(self, lo, hi):
        self._lo, self._hi = float(lo), float(hi)
        self._redraw()

    def _redraw(self):
        self.delete("all")
        h = self.winfo_height()
        w = self.winfo_width()
        if h <= 1:
            return
        # 콘텐츠가 전부 보이면 (lo=0, hi=1) 썸 숨김
        if self._lo <= 0.0 and self._hi >= 1.0:
            self._thumb_id = None
            return
        pad = 2
        y0 = self._lo * h + pad
        y1 = self._hi * h - pad
        if y1 - y0 < 18:           # 최소 썸 길이 보장
            mid = (y0 + y1) / 2
            y0, y1 = mid - 9, mid + 9
        r = (w - 4) / 2            # 둥근 모서리 반경
        self._thumb_id = self._round_rect(2, y0, w - 2, y1, r, self._thumb)

    def _round_rect(self, x0, y0, x1, y1, r, color):
        # 둥근 사각형을 polygon 으로 근사
        pts = [
            x0+r, y0,  x1-r, y0,  x1, y0,  x1, y0+r,
            x1, y1-r,  x1, y1,  x1-r, y1,  x0+r, y1,
            x0, y1,  x0, y1-r,  x0, y0+r,  x0, y0,
        ]
        return self.create_polygon(pts, smooth=True, fill=color, outline="")

    def _set_thumb_color(self, color):
        if self._thumb_id is not None:
            self.itemconfigure(self._thumb_id, fill=color)

    def _on_click(self, event):
        if self._thumb_id is None:
            return
        coords = self.coords(self._thumb_id)
        if not coords:
            return
        ys = coords[1::2]
        top, bottom = min(ys), max(ys)
        if top <= event.y <= bottom:
            # 썸 위 클릭 → 드래그 시작
            self._dragging = True
            self._drag_offset = event.y - top
            self._set_thumb_color(self._thumb_hl)
        else:
            # 트랙 클릭 → 해당 위치로 점프
            frac = event.y / max(1, self.winfo_height())
            self._command("moveto", frac)

    def _on_drag(self, event):
        if not self._dragging:
            return
        h = max(1, self.winfo_height())
        thumb_h = (self._hi - self._lo) * h
        new_top = event.y - self._drag_offset
        frac = new_top / max(1, (h - thumb_h)) if (h - thumb_h) > 0 else 0
        frac = max(0.0, min(1.0, frac)) * (1.0 - (self._hi - self._lo))
        self._command("moveto", frac)


# ── 메인 앱 ──────────────────────────────────────────────────────────────────

class ModInstallerApp(tk.Tk):

    def __init__(self):
        # Windows 작업표시줄에서 독립 아이콘을 표시하려면 AppUserModelID 필요
        # (없으면 pythonw.exe 와 그룹화되어 파이썬 아이콘으로 표시됨)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "dongleland.modinstaller.2"
            )
        except Exception:
            pass

        super().__init__()
        self.title(f"동글랜드 모드 설치 도우미 v{APP_VERSION}")
        self.resizable(False, False)
        self._set_app_icon()
        # 모니터 중앙에 배치
        _w, _h = 860, 660
        self.update_idletasks()
        _sw = self.winfo_screenwidth()
        _sh = self.winfo_screenheight()
        _x  = (_sw - _w) // 2
        _y  = (_sh - _h) // 2
        self.geometry(f"{_w}x{_h}+{_x}+{_y}")

        self._config       = preflight.load_config()
        self._C            = {}          # 현재 테마 색상
        self._preflight_result = None
        self._registry: ModRegistry | None = None
        self._mod_statuses: dict[str, str] = {}   # mod_id → 상태 문자열
        self._mod_rows:     dict[str, tk.Frame]   = {}
        self._current_page  = "mods"
        self._current_cat   = "전체"

        self._apply_theme()
        self._build_preflight_view()
        self.after(200, self._show_startup_warning)

    def _set_app_icon(self):
        """창/작업표시줄 아이콘 설정. ico 우선, 실패 시 png 폴백."""
        try:
            ico = resource_path(os.path.join("assets", "app_icon.ico"))
            if os.path.isfile(ico):
                # default=True 로 모든 하위 Toplevel 에도 적용
                self.iconbitmap(default=ico)
        except Exception:
            pass
        # iconphoto 는 ico 가 안 먹는 환경 대비 폴백
        try:
            png = resource_path(os.path.join("assets", "app_icon_64.png"))
            if os.path.isfile(png):
                self._icon_img = tk.PhotoImage(file=png)
                self.iconphoto(True, self._icon_img)
        except Exception:
            pass

    # ── 테마 ──────────────────────────────────────────────────────────────

    def _resolve_theme(self) -> str:
        t = self._config.get("theme", "system")
        if t == "system":
            return "dark" if _system_is_dark() else "light"
        return t if t in THEMES else "light"

    def _apply_theme(self):
        self._C = THEMES[self._resolve_theme()]
        self.configure(bg=self._C["bg"])

    # ── Preflight 화면 ────────────────────────────────────────────────────

    def _build_preflight_view(self):
        self._pf_frame = tk.Frame(self, bg=self._C["bg"])
        self._pf_frame.place(relwidth=1, relheight=1)

        center = tk.Frame(self._pf_frame, bg=self._C["bg"])
        center.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(
            center, text="🎮 동글랜드", font=("Segoe UI", 20, "bold"),
            bg=self._C["bg"], fg=ACCENT,
        ).pack(pady=(0, 4))
        tk.Label(
            center, text="모드 설치 도우미",
            font=("Segoe UI", 13), bg=self._C["bg"], fg=self._C["text"],
        ).pack(pady=(0, 24))

        self._pf_status = tk.Label(
            center, text="시작 중...", font=FONT_NORMAL,
            bg=self._C["bg"], fg=self._C["text2"], wraplength=420, justify="center",
        )
        self._pf_status.pack()

        self._pf_progress = ttk.Progressbar(center, mode="indeterminate", length=320)
        self._pf_progress.pack(pady=(16, 0))
        self._pf_progress.start(12)

        tk.Label(
            self._pf_frame,
            text=f"v{APP_VERSION}  ·  made by {APP_AUTHOR}",
            font=FONT_SMALL, bg=self._C["bg"], fg=self._C["text2"],
        ).place(relx=1.0, rely=1.0, anchor="se", x=-12, y=-8)

    def _show_startup_warning(self):
        messagebox.showwarning("실행 전 확인", preflight.STARTUP_WARNING)
        threading.Thread(target=self._run_preflight, daemon=True).start()

    def _run_preflight(self):
        result = preflight.run_preflight(
            on_status=lambda step, msg: self.after(0, self._on_pf_status, step, msg),
            config=self._config,
        )
        self.after(0, self._on_pf_done, result)

    def _on_pf_status(self, step: str, message: str):
        self._pf_status.configure(text=message)

        if step == "mc_not_found":
            self._pf_progress.stop()
            messagebox.showerror("마인크래프트 없음", message)
            self.destroy()

        elif step == "error":
            self._pf_progress.stop()
            messagebox.showerror("오류", message)
            self.destroy()

    def _on_pf_done(self, result):
        if not result:
            return
        self._preflight_result = result
        self._registry = ModRegistry(result["mods_dir"])
        self._config["minecraft_dir"] = result["minecraft_dir"]
        preflight.save_config(self._config)

        self._pf_frame.destroy()
        self._build_main_ui()
        threading.Thread(target=self._scan_and_check, daemon=True).start()
        self.after(3000, self._watch_mods_folder)

    def _watch_mods_folder(self):
        """3초마다 mods 폴더를 확인 — 외부 삭제를 즉시 반영"""
        if not self._registry or not self._preflight_result:
            self.after(3000, self._watch_mods_folder)
            return
        mods_dir = self._preflight_result["mods_dir"]
        for mod in VISIBLE_MODS:
            mid = mod["id"]
            if self._mod_statuses.get(mid) not in ("installed", "update"):
                continue
            filename = self._registry.get_installed_filename(mid)
            if filename and not os.path.isfile(os.path.join(mods_dir, filename)):
                self._registry.record_remove(mid)
                self._mod_statuses[mid] = "not_installed"
                self._refresh_row(mid)
        self.after(3000, self._watch_mods_folder)

    def _scan_and_check(self):
        """mods 폴더 스캔 → 설치 감지 → 업데이트 확인 (v1.0.9 방식 기반).

        핵심 원리 (v1.0.9에서 작동했던 방식 그대로):
          1) 번들 모드 즉시 처리
          2) slug 목록을 Modrinth batch API 로 단 1회 호출 → slug→project_id 맵
          3) mods 폴더 jar 파일별 sha1 → get_version_from_hash → project_id
             project_id → slug 역맵으로 어떤 카탈로그 모드인지 확정
          4) 설치된 파일의 sha1 vs Modrinth 최신 파일 sha1 비교 (문자열 비교 X)
        """
        mods_dir = self._preflight_result["mods_dir"]
        os.makedirs(mods_dir, exist_ok=True)

        # ── Step 1: 번들 모드(slug 없음) 즉시 처리 ──────────────────────────
        for mod in MODS:
            if mod.get("slug"):
                continue
            mid = mod["id"]
            ba  = mod.get("bundled_asset")
            if ba and os.path.isfile(os.path.join(mods_dir, ba)):
                if not self._registry.is_installed(mid):
                    self._registry.record_install(mid, ba, "1.2.0", None)
            self._mod_statuses[mid] = (
                "installed" if self._registry.is_installed(mid) else "not_installed"
            )
            self.after(0, self._refresh_row, mid)

        # ── Step 2: slug → project_id 맵 구축 (batch API, 단 1회 호출) ──────
        all_slugs = [m["slug"] for m in MODS if m.get("slug")]
        pid_cache: dict = self._config.get("_pid_cache", {})
        missing = [s for s in all_slugs if s not in pid_cache]
        if missing:
            fresh = modrinth_api.get_projects_batch(missing)
            if fresh:
                pid_cache.update(fresh)
                self._config["_pid_cache"] = pid_cache
                preflight.save_config(self._config)

        # project_id → slug 역맵
        pid_to_slug: dict = {v: k for k, v in pid_cache.items()}

        # ── Step 3: mods 폴더 jar 스캔 → sha1 → project_id 특정 ─────────────
        # {project_id: (jar_filename, local_sha1, installed_version)}
        installed_by_pid: dict = {}
        if os.path.isdir(mods_dir):
            for jar in os.listdir(mods_dir):
                if not jar.lower().endswith(".jar") or jar.startswith("."):
                    continue
                path = os.path.join(mods_dir, jar)
                try:
                    local_sha1 = modrinth_api.sha1_of_file(path)
                    info = modrinth_api.get_version_from_hash(local_sha1)
                except Exception:
                    continue
                if info and info.get("project_id"):
                    pid = info["project_id"]
                    ver = info.get("version_number", "?")
                    installed_by_pid[pid] = (jar, local_sha1, ver)

        # ── Step 4: 카탈로그 모드별 설치 여부 + 업데이트 비교 ────────────────
        for mod in VISIBLE_MODS:
            mid  = mod["id"]
            slug = mod.get("slug")
            if not slug:
                continue  # Step 1 에서 이미 처리

            pid = pid_cache.get(slug)
            if pid and pid in installed_by_pid:
                jar_file, local_sha1, ver = installed_by_pid[pid]

                # 레지스트리에 기록/갱신
                self._registry.record_install(mid, jar_file, ver, pid)

                # 최신 버전 sha1 과 비교 (v1.0.9 방식)
                try:
                    latest  = modrinth_api.get_latest_compatible_version(slug, GAME_VERSION, LOADER)
                    primary = modrinth_api.pick_primary_file(latest) if latest else None
                    latest_sha1 = primary.get("hashes", {}).get("sha1") if primary else None
                    if latest_sha1 and local_sha1 != latest_sha1:
                        self._mod_statuses[mid] = "update"
                    else:
                        self._mod_statuses[mid] = "installed"
                except Exception:
                    self._mod_statuses[mid] = "installed"
            else:
                # mods 폴더에 없음 → 레지스트리 정리
                if self._registry.is_installed(mid):
                    self._registry.record_remove(mid)
                self._mod_statuses[mid] = "not_installed"

            self.after(0, self._refresh_row, mid)

    # ── 메인 UI ───────────────────────────────────────────────────────────

    def _build_main_ui(self):
        self._sidebar  = tk.Frame(self, bg=self._C["sidebar"], width=150)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._content = tk.Frame(self, bg=self._C["bg"])
        self._content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._show_mods_view()

    def _build_sidebar(self):
        # 로고 영역 (진한 박스 제거 — 텍스트만)
        logo_frame = tk.Frame(self._sidebar, bg=self._C["sidebar"], height=64)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)
        tk.Label(
            logo_frame, text="동글랜드",
            font=("Segoe UI", 14, "bold"),
            bg=self._C["sidebar"], fg=ACCENT,
        ).pack(expand=True, pady=(18, 0))

        # 부제
        tk.Label(
            self._sidebar, text="모드 설치 도우미",
            font=("Segoe UI", 8), bg=self._C["sidebar"],
            fg=self._C["sidebar_fg"],
        ).pack(pady=(2, 18))

        self._nav_btns = {}
        nav_items = [
            ("launch",   "🎮", "런처 실행"),
            ("mods",     "📦", "모드"),
            ("shaders",  "✨", "셰이더팩"),
            ("settings", "⚙️", "시스템"),
        ]
        for key, icon, label in nav_items:
            frame = tk.Frame(self._sidebar, bg=self._C["sidebar"])
            frame.pack(fill="x", padx=8, pady=1)

            btn = tk.Label(
                frame, text=f" {icon}  {label}", anchor="w",
                font=FONT_NORMAL,
                bg=self._C["sidebar"], fg=self._C["sidebar_fg"],
                padx=12, pady=9, cursor="hand2",
            )
            btn.pack(fill="x")

            def _enter(e, b=btn, k=key):
                if self._current_page != k:
                    b.configure(bg=self._C["sidebar_hl"], fg=self._C["text"])
            def _leave(e, b=btn, k=key):
                if self._current_page != k:
                    b.configure(bg=self._C["sidebar"], fg=self._C["sidebar_fg"])

            btn.bind("<Button-1>", lambda e, k=key: self._nav_click(k))
            btn.bind("<Enter>",    _enter)
            btn.bind("<Leave>",    _leave)
            self._nav_btns[key] = btn

        # 하단 버전 정보
        tk.Label(
            self._sidebar,
            text=f"v{APP_VERSION}  ·  {APP_AUTHOR}",
            font=("Segoe UI", 8), bg=self._C["sidebar"],
            fg=self._C["sidebar_fg"], justify="center",
        ).pack(side="bottom", pady=12)

        self._update_nav_highlight()

    def _update_nav_highlight(self):
        for key, btn in self._nav_btns.items():
            if key == self._current_page:
                btn.configure(bg=self._C["sidebar_hl"], fg=SELECT_HL)
            else:
                btn.configure(bg=self._C["sidebar"], fg=self._C["sidebar_fg"])

    def _on_mousewheel(self, event):
        """콘텐츠가 화면보다 짧으면 스크롤하지 않음 (모드가 적을 때 상단 고정)"""
        if not (hasattr(self, "_canvas") and self._canvas.winfo_exists()):
            return
        if event.delta == 0:
            return
        # 스크롤 영역이 보이는 영역보다 작으면 무시
        bbox = self._canvas.bbox("all")
        if bbox:
            content_h = bbox[3] - bbox[1]
            visible_h = self._canvas.winfo_height()
            if content_h <= visible_h:
                self._canvas.yview_moveto(0.0)
                return
        direction = -1 if event.delta > 0 else 1
        self._canvas.yview_scroll(direction, "units")

    def _nav_click(self, key: str):
        if key == "launch":
            ok = preflight.launch_minecraft()
            if not ok:
                messagebox.showwarning("런처 실행 실패",
                    "마인크래프트 런처를 찾을 수 없습니다.\n"
                    "마인크래프트가 설치되어 있는지 확인해주세요.")
            return
        # 페이지 전환 시 전역 스크롤 바인딩 해제
        self.unbind_all("<MouseWheel>")
        self._current_page = key
        self._update_nav_highlight()
        for w in self._content.winfo_children():
            w.destroy()
        if key == "mods":
            self._show_mods_view()
        elif key == "shaders":
            self._show_shaders_view()
        elif key == "settings":
            self._show_settings_view()

    # ── 모드 목록 화면 ────────────────────────────────────────────────────

    def _show_mods_view(self):
        self._current_page = "mods"

        # 헤더 탭바
        tab_bar = tk.Frame(self._content, bg=self._C["header_bg"], height=44)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)
        self._cat_btns = {}
        for cat in CATEGORIES:
            b = tk.Label(
                tab_bar, text=cat, font=FONT_SMALL,
                bg=self._C["header_bg"], fg=self._C["header_fg"],
                padx=12, pady=12, cursor="hand2",
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, c=cat: self._set_category(c))
            b.bind("<Enter>", lambda e, lb=b: lb.configure(fg=self._C["text"]) if lb.cget("fg") != SELECT_HL else None)
            b.bind("<Leave>", lambda e, lb=b, c=cat: lb.configure(
                fg=SELECT_HL if c == self._current_cat else self._C["header_fg"]))
            self._cat_btns[cat] = b

        # 헤더 구분선 제거 — 여백으로만 구분

        # 액션 바 (전체 업데이트 / 전체 삭제) — 네모 버튼 없이 텍스트 링크
        action_bar = tk.Frame(self._content, bg=self._C["bg"])
        action_bar.pack(fill="x", padx=18, pady=(10, 2))

        def _text_action(parent, text, command):
            lbl = tk.Label(
                parent, text=text, font=FONT_SMALL,
                bg=self._C["bg"], fg=self._C["text2"],
                cursor="hand2",
            )
            lbl.bind("<Button-1>", lambda e: command())
            lbl.bind("<Enter>", lambda e: lbl.configure(fg=ACCENT))
            lbl.bind("<Leave>", lambda e: lbl.configure(fg=self._C["text2"]))
            return lbl

        _text_action(action_bar, "전체 업데이트", self._do_update_all).pack(side="left", padx=(0, 16))
        _text_action(action_bar, "전체 삭제", self._do_delete_all).pack(side="left")

        # 스크롤 영역
        outer = tk.Frame(self._content, bg=self._C["bg"])
        outer.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(outer, bg=self._C["bg"], highlightthickness=0, bd=0)
        scrollbar = ThemedScrollbar(
            outer, command=self._canvas.yview,
            trough=self._C["scroll_trough"],
            thumb=self._C["scroll_thumb"],
            thumb_hover=self._C["scroll_hover"],
        )
        self._list_frame = tk.Frame(self._canvas, bg=self._C["bg"])
        self._list_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        )
        self._list_win = self._canvas.create_window((0, 0), window=self._list_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=scrollbar.set)
        # bind_all 로 자식 위젯 위에서도 스크롤 동작
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        # 캔버스 너비에 맞춰 내부 프레임 너비 동기화
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._list_win, width=e.width))

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._set_category(self._current_cat)

    def _set_category(self, cat: str):
        self._current_cat = cat
        for c, b in self._cat_btns.items():
            if c == cat:
                b.configure(fg=SELECT_HL, font=("Segoe UI", 9, "bold"))
            else:
                b.configure(fg=self._C["header_fg"], font=FONT_SMALL)

        for w in self._list_frame.winfo_children():
            w.destroy()
        self._mod_rows.clear()
        # 카테고리 전환 시 항상 스크롤 상단으로
        if hasattr(self, "_canvas") and self._canvas.winfo_exists():
            self._canvas.yview_moveto(0.0)

        mods = [m for m in VISIBLE_MODS if cat == "전체" or m["category"] == cat]
        for mod in mods:
            self._build_mod_row(mod)

    def _build_mod_row(self, mod: dict):
        mod_id = mod["id"]
        cat    = mod["category"]
        color  = CATEGORY_COLOR.get(cat, "#7F8C8D")

        # 카드 외부 패딩 프레임
        outer = tk.Frame(self._list_frame, bg=self._C["bg"])
        outer.pack(fill="x", padx=10, pady=2)

        # 카드 본체 (테두리선 없음 — 여백과 hover 배경으로만 구분)
        row = tk.Frame(outer, bg=self._C["surface"], cursor="hand2",
                       highlightthickness=0)
        row.pack(fill="x")

        # 스트라이프 제거 — 더미 프레임 (skip 참조 호환용, 폭 0)
        stripe = tk.Frame(row, bg=self._C["surface"], width=0)
        stripe.pack(side="left", fill="y")

        # stripe 제외 전체 배경 변경 함수
        def _set_bg(widget, color_, skip=None):
            if widget is skip:
                return
            try:
                if not isinstance(widget, (tk.Button,)):
                    widget.configure(bg=color_)
            except Exception:
                pass
            for child in widget.winfo_children():
                _set_bg(child, color_, skip)

        def _is_inside_row(event_widget):
            """마우스 포인터가 아직 row 카드 안에 있는지 확인"""
            try:
                px, py = event_widget.winfo_pointerxy()
                under  = event_widget.winfo_containing(px, py)
                if under is None:
                    return False
                w = under
                while w is not None:
                    if w is row:
                        return True
                    try:
                        w = w.master
                    except Exception:
                        break
            except Exception:
                pass
            return False

        def _hover_on(e=None):
            _set_bg(row, self._C["row_hover"], skip=stripe)

        def _hover_off(e=None):
            if e and _is_inside_row(e.widget):
                return   # 아직 카드 안 → leave 무시
            _set_bg(row, self._C["surface"], skip=stripe)

        def _force_hover_off():
            """클릭으로 상세창 열 때 hover 상태를 강제로 해제 (grab_set 으로
            Leave 이벤트가 안 오는 문제 방지)"""
            _set_bg(row, self._C["surface"], skip=stripe)

        def _on_card_click():
            _force_hover_off()
            self._open_detail(mod_id)

        def _bind_hover_all(widget):
            """stripe 제외 모든 자식 위젯에 hover 이벤트 바인딩"""
            if widget is stripe:
                return
            widget.bind("<Enter>", lambda e: _hover_on())
            widget.bind("<Leave>", _hover_off)
            if not isinstance(widget, tk.Button):
                widget.bind("<Button-1>", lambda e: _on_card_click())
            for child in widget.winfo_children():
                _bind_hover_all(child)

        row.bind("<Enter>", lambda e: _hover_on())
        row.bind("<Leave>", _hover_off)
        row.bind("<Button-1>", lambda e: _on_card_click())

        # ── 우측 고정 요소 먼저 배치 (버튼 → 태그) ────────────────────────
        # 상태 버튼
        status = self._get_status(mod_id)
        btn_text, bg, fg = self._status_btn_props(mod_id, status)
        actionable = status in ("not_installed", "update")
        btn = tk.Button(
            row, text=btn_text, font=("Segoe UI", 9, "bold"),
            bg=bg, fg=fg, relief="flat",
            padx=14, pady=6,
            cursor="hand2" if actionable else "arrow",
            activebackground=bg, activeforeground=fg,
            command=(lambda m=mod_id: self._handle_btn(m)) if actionable else (lambda: None),
        )
        btn.pack(side="right", padx=14, pady=10)

        if status == "conflict":
            Tooltip(btn, "한글 모드는 1개만 설치할 수 있습니다.")

        # 태그 (박스 제거 — 텍스트만, fg 강조색)
        tag_frame = tk.Frame(row, bg=self._C["surface"])
        tag_frame.pack(side="right", padx=(0, 6))
        for tag in mod["tags"][:2]:
            tk.Label(
                tag_frame, text=tag, font=("Segoe UI", 8),
                bg=self._C["surface"], fg=self._C["tag_fg"],
            ).pack(anchor="e", pady=1)

        # ── 텍스트 영역 (남은 공간만 차지, 고정 폭) ─────────────────────────
        text_frame = tk.Frame(row, bg=self._C["surface"])
        text_frame.pack(side="left", fill="x", expand=True, padx=(14, 8), pady=10)
        text_frame.bind("<Button-1>", lambda e: _on_card_click())

        name_lbl = tk.Label(
            text_frame, text=mod["name"], font=FONT_BOLD,
            bg=self._C["surface"], fg=self._C["text"], anchor="w",
        )
        name_lbl.pack(fill="x")
        name_lbl.bind("<Button-1>", lambda e: _on_card_click())

        # 설명 — 한 줄 고정. 폭에 넘치면 자동으로 끝을 …로 줄임
        desc_full = mod["description"].split("\n")[0]
        desc_lbl = tk.Label(
            text_frame, text=desc_full, font=FONT_SMALL,
            bg=self._C["surface"], fg=self._C["text2"],
            anchor="w", justify="left",
        )
        desc_lbl.pack(fill="x")
        desc_lbl.bind("<Button-1>", lambda e: _on_card_click())

        def _ellipsize(event=None):
            """Label 폭에 맞춰 텍스트가 넘치면 끝을 …로 줄임"""
            avail = desc_lbl.winfo_width()
            if avail <= 1:
                return
            font = tkfont.Font(font=desc_lbl.cget("font"))
            if font.measure(desc_full) <= avail:
                if desc_lbl.cget("text") != desc_full:
                    desc_lbl.configure(text=desc_full)
                return
            # 한 글자씩 줄이며 … 포함 폭이 맞을 때까지
            ell = "…"
            lo, hi = 0, len(desc_full)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if font.measure(desc_full[:mid] + ell) <= avail:
                    lo = mid
                else:
                    hi = mid - 1
            desc_lbl.configure(text=desc_full[:lo].rstrip() + ell)

        desc_lbl.bind("<Configure>", _ellipsize)
        _bind_hover_all(row)
        # stripe 는 hover 대상은 아니지만 클릭은 가능하게
        stripe.bind("<Button-1>", lambda e: _on_card_click())

        self._mod_rows[mod_id] = {"row": row, "btn": btn}

    # ── 모드 상태 ─────────────────────────────────────────────────────────

    def _get_status(self, mod_id: str) -> str:
        mod = MOD_BY_ID.get(mod_id, {})

        # 한글 충돌은 _mod_statuses 보다 우선 판정 (설치 상태와 무관하게 동적)
        if mod.get("exclusive_group") == "korean":
            installed_self = self._is_korean_installed(mod_id)
            if not installed_self:
                # 같은 그룹의 다른 모드가 설치돼 있으면 충돌
                group_ids = [m["id"] for m in MODS if m.get("exclusive_group") == "korean"]
                if any(self._is_korean_installed(g) for g in group_ids if g != mod_id):
                    return "conflict"

        if mod_id in self._mod_statuses:
            return self._mod_statuses[mod_id]
        if self._registry and self._registry.is_installed(mod_id):
            return "checking"
        return "not_installed"

    def _is_korean_installed(self, mod_id: str) -> bool:
        """한글 모드가 실제 설치되어 있는지 (레지스트리 + 현재 상태)"""
        if self._registry and self._registry.is_installed(mod_id):
            return True
        return self._mod_statuses.get(mod_id) in ("installed", "update")

    def _refresh_korean_group(self):
        """한글 그룹 전체 버튼을 다시 그림 (설치/제거 직후 호출)"""
        for m in MODS:
            if m.get("exclusive_group") == "korean":
                self._refresh_row(m["id"])

    def _status_btn_props(self, mod_id: str, status: str):
        labels = {
            "not_installed": "설치",
            "installed":     "설치됨 ✓",
            "update":        "업데이트",
            "conflict":      "설치 불가",
            "checking":      "확인 중...",
        }
        text = labels.get(status, "설치")
        color_key = {
            "not_installed": "install",
            "installed":     "installed",
            "update":        "update",
            "conflict":      "conflict",
            "checking":      "checking",
        }.get(status, "install")
        bg, fg = BTN_COLORS[color_key]
        return text, bg, fg

    def _handle_btn(self, mod_id: str):
        status = self._get_status(mod_id)
        if status in ("installed", "checking", "conflict"):
            return
        if status == "not_installed":
            self._do_install(mod_id)
        elif status == "update":
            self._do_update(mod_id)

    def _refresh_row(self, mod_id: str):
        if mod_id not in self._mod_rows:
            return
        status = self._get_status(mod_id)
        btn_text, bg, fg = self._status_btn_props(mod_id, status)
        btn = self._mod_rows[mod_id]["btn"]
        actionable = status in ("not_installed", "update")
        btn.configure(
            text=btn_text, bg=bg, fg=fg,
            activebackground=bg, activeforeground=fg,
            cursor="hand2" if actionable else "arrow",
            command=(lambda m=mod_id: self._handle_btn(m)) if actionable else (lambda: None),
        )
        # 한글 충돌 툴팁 (상태 갱신 시 재생성)
        if status == "conflict":
            Tooltip(btn, "한글 모드는 1개만 설치할 수 있습니다.")

    # ── 설치 / 제거 / 업데이트 ───────────────────────────────────────────

    def _set_btn_loading(self, mod_id: str, text: str = "처리 중..."):
        if mod_id in self._mod_rows:
            self._mod_rows[mod_id]["btn"].configure(
                text=text, bg="#9CA3AF", state="disabled"
            )

    def _install_single(self, mod_id: str) -> tuple:
        """모드 1개 설치. (성공여부, 실패사유) 튜플 반환.
        성공 시 (True, None), 실패 시 (False, "사유 문자열")."""
        mod = MOD_BY_ID.get(mod_id)
        if not mod or not self._preflight_result:
            return (False, "내부 오류: 모드 정보 또는 사전 점검 결과 없음")
        mods_dir = self._preflight_result["mods_dir"]
        os.makedirs(mods_dir, exist_ok=True)
        name = mod.get("name", mod_id)

        # 번들 모드 (modcheckclient 등)
        if mod.get("bundled_asset"):
            src = resource_path(os.path.join("assets", mod["bundled_asset"]))
            dst = os.path.join(mods_dir, mod["bundled_asset"])
            if not os.path.abspath(dst).startswith(os.path.abspath(mods_dir) + os.sep):
                reason = "비정상적인 대상 경로"
                preflight.write_log(f"[설치실패] {name}: {reason}")
                return (False, reason)
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                reason = f"번들 파일 복사 실패: {e}"
                preflight.write_log(f"[설치실패] {name}: {reason}")
                return (False, reason)
            self._registry.record_install(mod_id, mod["bundled_asset"], "1.2.0", None)
            preflight.write_log(f"[설치성공] {name} (번들)")
            return (True, None)

        slug = mod.get("slug")
        if not slug:
            reason = "slug 정보 없음 (카탈로그 오류)"
            preflight.write_log(f"[설치실패] {name}: {reason}")
            return (False, reason)

        try:
            result = modrinth_api.install_mod_by_slug(slug, mods_dir, GAME_VERSION, LOADER)
        except Exception as e:
            reason = f"예기치 못한 오류: {e}"
            preflight.write_log(f"[설치실패] {name} (slug={slug}): {reason}")
            return (False, reason)

        if result["status"] in ("installed", "up_to_date"):
            self._registry.record_install(
                mod_id,
                result["filename"],
                result["version"],
                result.get("project_id"),
            )
            preflight.write_log(
                f"[설치성공] {name} v{result['version']} ({result['status']})"
            )
            return (True, None)

        # 실패 — install_mod_by_slug 가 담아준 상세 메시지 사용
        reason = result.get("message", f"알 수 없는 오류 (status={result['status']})")
        preflight.write_log(f"[설치실패] {name} (slug={slug}): {reason}")
        return (False, reason)

    def _do_install(self, mod_id: str):
        mod = MOD_BY_ID.get(mod_id, {})

        # 한글 모드 배타 그룹 경고 (레지스트리 + 현재 상태 모두 확인)
        if mod.get("exclusive_group") == "korean":
            group_ids = [m["id"] for m in MODS if m.get("exclusive_group") == "korean"]
            other = next(
                (gid for gid in group_ids
                 if gid != mod_id and (
                     self._registry.is_installed(gid) or
                     self._mod_statuses.get(gid) in ("installed", "update")
                 )),
                None,
            )
            if other:
                other_name = MOD_BY_ID[other]["name"]
                messagebox.showwarning(
                    "한글 모드 충돌",
                    f"한글 모드는 1개만 설치할 수 있습니다.\n\n"
                    f"현재 '{other_name}'이(가) 설치되어 있습니다.\n"
                    f"먼저 제거한 후 설치해주세요.",
                )
                return

        self._set_btn_loading(mod_id)

        def worker():
            # 종속 모드 먼저 설치
            for dep_id in mod.get("dependencies", []):
                if not self._registry.is_installed(dep_id):
                    dep_ok, dep_reason = self._install_single(dep_id)
                    if dep_ok:
                        self._mod_statuses[dep_id] = "installed"
                        self.after(0, self._refresh_row, dep_id)
                    else:
                        # 종속 설치 실패 → 본체도 중단하고 알림
                        dep_name = MOD_BY_ID.get(dep_id, {}).get("name", dep_id)
                        self.after(0, lambda dn=dep_name, dr=dep_reason: messagebox.showerror(
                            "설치 실패",
                            f"{mod['name']}의 필수 종속 모드 '{dn}' 설치에 실패했습니다.\n\n"
                            f"원인: {dr}",
                        ))
                        self.after(0, self._refresh_row, mod_id)
                        return

            ok, reason = self._install_single(mod_id)
            if ok:
                self._mod_statuses[mod_id] = "installed"
            self.after(0, self._refresh_row, mod_id)
            # 한글 모드면 그룹 전체 버튼 갱신
            if mod.get("exclusive_group") == "korean":
                self.after(0, self._refresh_korean_group)
            if not ok:
                self.after(0, lambda r=reason: messagebox.showerror(
                    "설치 실패",
                    f"{mod['name']} 설치에 실패했습니다.\n\n"
                    f"원인: {r}\n\n"
                    f"자세한 기록은 설정(시스템) 화면의 '로그 폴더 열기'에서\n"
                    f"확인할 수 있습니다.",
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _do_update_all(self):
        """업데이트가 필요한 모든 모드를 순차적으로 업데이트"""
        targets = [
            mid for mid, status in self._mod_statuses.items()
            if status == "update"
        ]
        if not targets:
            messagebox.showinfo("알림", "업데이트할 모드가 없습니다.")
            return

        def worker():
            failed = []
            for mid in targets:
                self.after(0, lambda m=mid: self._set_btn_loading(m, "업데이트 중..."))
                old_file = self._registry.get_installed_filename(mid)
                ok, reason = self._install_single(mid)
                if ok:
                    new_file = self._registry.get_installed_filename(mid)
                    mods_dir = self._preflight_result["mods_dir"]
                    if old_file and old_file != new_file:
                        old_path = os.path.join(mods_dir, old_file)
                        if os.path.isfile(old_path):
                            try:
                                os.remove(old_path)
                            except OSError:
                                pass
                    self._mod_statuses[mid] = "installed"
                else:
                    failed.append((MOD_BY_ID.get(mid, {}).get("name", mid), reason))
                self.after(0, self._refresh_row, mid)

            success_n = len(targets) - len(failed)
            if failed:
                detail = "\n".join(f"  • {n}: {r}" for n, r in failed[:5])
                if len(failed) > 5:
                    detail += f"\n  … 외 {len(failed) - 5}개"
                self.after(0, lambda d=detail, s=success_n, f=len(failed): messagebox.showwarning(
                    "업데이트 완료 (일부 실패)",
                    f"성공 {s}개, 실패 {f}개\n\n실패 목록:\n{d}",
                ))
            else:
                self.after(0, lambda s=success_n: messagebox.showinfo(
                    "완료", f"{s}개 모드 업데이트가 완료됐습니다."
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _do_delete_all(self):
        """필수 모드 제외 전체 삭제 (확인 필요)"""
        installed = [
            mid for mid, status in self._mod_statuses.items()
            if status in ("installed", "update")
            and not MOD_BY_ID.get(mid, {}).get("required")
        ]
        if not installed:
            messagebox.showinfo("알림", "삭제할 모드가 없습니다.")
            return
        names = "\n".join(f"  • {MOD_BY_ID[m]['name']}" for m in installed[:10])
        if len(installed) > 10:
            names += f"\n  … 외 {len(installed) - 10}개"
        if not messagebox.askyesno(
            "전체 삭제 확인",
            f"아래 모드를 모두 삭제합니다. 계속하시겠습니까?\n\n{names}",
            icon="warning",
        ):
            return
        for mid in installed:
            self._do_remove(mid)

    def _do_remove(self, mod_id: str, on_done=None):
        mod = MOD_BY_ID.get(mod_id, {})
        if mod.get("required"):
            messagebox.showwarning("제거 불가", f"{mod['name']}은(는) 필수 모드입니다.")
            return
        mods_dir = self._preflight_result["mods_dir"]
        filename = self._registry.get_installed_filename(mod_id)
        if filename:
            path = os.path.join(mods_dir, filename)
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError as e:
                    messagebox.showerror("제거 실패", str(e))
                    return
        self._registry.record_remove(mod_id)
        self._mod_statuses[mod_id] = "not_installed"
        self._refresh_row(mod_id)
        # 한글 모드 제거 시 그룹 전체 갱신 (다른 모드 → 설치 가능 복원)
        if mod.get("exclusive_group") == "korean":
            self._refresh_korean_group()
        if on_done:
            on_done()

    def _do_update(self, mod_id: str):
        mod = MOD_BY_ID.get(mod_id, {})
        self._set_btn_loading(mod_id, "업데이트 중...")

        def worker():
            old_file = self._registry.get_installed_filename(mod_id)
            ok, reason = self._install_single(mod_id)
            if ok:
                new_file = self._registry.get_installed_filename(mod_id)
                mods_dir = self._preflight_result["mods_dir"]
                if old_file and old_file != new_file:
                    old_path = os.path.join(mods_dir, old_file)
                    if os.path.isfile(old_path):
                        try:
                            os.remove(old_path)
                        except OSError:
                            pass
                self._mod_statuses[mod_id] = "installed"
            self.after(0, self._refresh_row, mod_id)
            if not ok:
                self.after(0, lambda r=reason: messagebox.showerror(
                    "업데이트 실패",
                    f"{mod.get('name', mod_id)} 업데이트에 실패했습니다.\n\n원인: {r}",
                ))

        threading.Thread(target=worker, daemon=True).start()

    # ── 모드 상세 창 ──────────────────────────────────────────────────────

    def _open_detail(self, mod_id: str):
        ModDetailWindow(self, mod_id)

    # ── 셰이더팩 화면 ─────────────────────────────────────────────────────

    def _show_shaders_view(self):
        f = tk.Frame(self._content, bg=self._C["bg"])
        f.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(f, text="✨", font=("Segoe UI", 36),
                 bg=self._C["bg"], fg=ACCENT).pack()
        tk.Label(f, text="아직 출시되지 않은 기능입니다.",
                 font=FONT_TITLE, bg=self._C["bg"], fg=self._C["text"]).pack(pady=8)
        tk.Label(f, text="셰이더팩 관리 기능은 추후 업데이트에서 제공될 예정입니다.",
                 font=FONT_NORMAL, bg=self._C["bg"], fg=self._C["text2"]).pack()

    # ── 설정 화면 ─────────────────────────────────────────────────────────

    def _show_settings_view(self):
        """설정 화면 - Canvas 없이 일반 Frame 사용 (렌더링 문제 방지)"""
        C   = self._C

        outer = tk.Frame(self._content, bg=C["bg"])
        outer.pack(fill="both", expand=True)

        # 내부 스크롤 가능한 영역
        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        sb = ThemedScrollbar(
            outer, command=canvas.yview,
            trough=C["scroll_trough"],
            thumb=C["scroll_thumb"],
            thumb_hover=C["scroll_hover"],
        )
        frame = tk.Frame(canvas, bg=C["bg"])

        frame.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        wid = canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.bind("<Configure>", lambda e, w=wid: canvas.itemconfig(w, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # ── 섹션 헬퍼 ─────────────────────────────────────────────────────
        def section(title: str):
            tk.Frame(frame, bg=C["bg"], height=14).pack(fill="x")
            hdr = tk.Frame(frame, bg=C["bg"])
            hdr.pack(fill="x", padx=0)
            tk.Label(hdr, text=title, font=FONT_BOLD,
                     bg=C["bg"], fg=ACCENT,
                     padx=20, pady=4).pack(anchor="w")

        def info_row(label: str, value: str, extra_widget_fn=None):
            r = tk.Frame(frame, bg=C["surface"])
            r.pack(fill="x", padx=20, pady=1)
            tk.Label(r, text=label, font=FONT_SMALL, width=16, anchor="w",
                     bg=C["surface"], fg=C["text2"],
                     padx=12, pady=10).pack(side="left")
            if extra_widget_fn:
                extra_widget_fn(r)
            else:
                tk.Label(r, text=value, font=FONT_NORMAL, anchor="w",
                         bg=C["surface"], fg=C["text"]).pack(side="left")

        # ── 앱 정보 ────────────────────────────────────────────────────────
        section("앱 정보")
        info_row("버전", f"v{APP_VERSION}")
        info_row("업데이트 확인", "추후 지원 예정")

        # ── 마인크래프트 ───────────────────────────────────────────────────
        section("마인크래프트")
        mc_dir  = (self._preflight_result or {}).get("minecraft_dir", "알 수 없음")
        mc_var  = tk.StringVar(value=mc_dir)

        def _mc_widget(p):
            # Fix 3: entry_bg 로 배경색 통일, Fix 5: 변경 버튼 제거
            tk.Entry(p, textvariable=mc_var, font=FONT_SMALL,
                     bg=C.get("entry_bg", C["bg"]),
                     fg=C["text"],
                     insertbackground=C["text"],
                     relief="flat",
                     state="readonly", width=38).pack(side="left", padx=(0, 4))

        info_row("설치 경로", "", _mc_widget)

        # Fabric 버전 + 업데이트 확인 (백그라운드 조회)
        fabric_installed = (self._preflight_result or {}).get("fabric_version", "알 수 없음")

        def _fabric_widget(p):
            self._fabric_ver_lbl = tk.Label(
                p, text=fabric_installed, font=FONT_NORMAL,
                bg=C["surface"], fg=C["text"],
            )
            self._fabric_ver_lbl.pack(side="left")
            # 상태 텍스트 (확인 중 → 결과)
            self._fabric_status_lbl = tk.Label(
                p, text="  업데이트 확인 중…", font=("Segoe UI", 8),
                bg=C["surface"], fg=C["text2"],
            )
            self._fabric_status_lbl.pack(side="left")
            # 업데이트 버튼 (처음엔 숨김)
            self._fabric_update_btn = tk.Button(
                p, text="업데이트", font=("Segoe UI", 8, "bold"),
                bg=ACCENT, fg="white", relief="flat", padx=8, pady=2,
                cursor="hand2", command=self._do_fabric_update,
            )
            # pack 은 결과가 update_available 일 때만

        info_row("Fabric 버전", "", _fabric_widget)
        info_row("Java 버전",
                 (self._preflight_result or {}).get("java_version", "알 수 없음"))

        # 백그라운드로 Fabric 로더 업데이트 확인 시작
        threading.Thread(target=self._check_fabric_update_bg, daemon=True).start()

        # ── 테마 ──────────────────────────────────────────────────────────
        section("테마")
        theme_var = tk.StringVar(value=self._config.get("theme", "system"))

        def _theme_widget(p):
            for val, lbl in [("system", "시스템"), ("light", "라이트"), ("dark", "다크")]:
                tk.Radiobutton(
                    p, text=lbl, variable=theme_var, value=val,
                    font=FONT_NORMAL, bg=C["surface"], fg=C["text"],
                    activebackground=C["surface"], selectcolor=C["surface"],
                    command=lambda: self._change_theme(theme_var.get()),
                ).pack(side="left", padx=10, pady=8)

        info_row("테마 선택", "", _theme_widget)

        # ── 문의 ──────────────────────────────────────────────────────────
        section("문의")
        r = tk.Frame(frame, bg=C["surface"])
        r.pack(fill="x", padx=20, pady=1)
        tk.Label(r, text="디스코드 DM: ", font=FONT_NORMAL,
                 bg=C["surface"], fg=C["text"], padx=12, pady=12).pack(side="left")
        tk.Label(r, text="@garamisme", font=FONT_BOLD,
                 bg=C["surface"], fg=ACCENT).pack(side="left")

        # ── 문제 해결 ──────────────────────────────────────────────────────
        section("문제 해결")
        r2 = tk.Frame(frame, bg=C["surface"])
        r2.pack(fill="x", padx=20, pady=1)
        tk.Label(r2, text="설치 오류 기록", font=FONT_SMALL, width=16, anchor="w",
                 bg=C["surface"], fg=C["text2"], padx=12, pady=10).pack(side="left")

        log_link = tk.Label(
            r2, text="로그 폴더 열기", font=FONT_SMALL,
            bg=C["surface"], fg=ACCENT, cursor="hand2",
        )
        log_link.pack(side="left", padx=(0, 10))
        log_link.bind("<Button-1>", lambda e: self._open_log_folder())
        log_link.bind("<Enter>", lambda e: log_link.configure(fg=ACCENT_DARK))
        log_link.bind("<Leave>", lambda e: log_link.configure(fg=ACCENT))

        tk.Label(
            r2, text="문제 발생 시 이 폴더의 log.txt를 문의처에 보내주세요",
            font=("Segoe UI", 8), bg=C["surface"], fg=C["text2"],
        ).pack(side="left")

        tk.Frame(frame, bg=C["bg"], height=20).pack(fill="x")  # 하단 여백

    def _change_mc_dir(self, var: tk.StringVar):
        new_dir = filedialog.askdirectory(title="마인크래프트 폴더 선택")
        if new_dir:
            var.set(new_dir)
            self._config["minecraft_dir"] = new_dir
            preflight.save_config(self._config)
            messagebox.showinfo("경로 변경", "경로가 저장되었습니다.\n앱을 재시작하면 적용됩니다.")

    def _change_theme(self, theme: str):
        self._config["theme"] = theme
        preflight.save_config(self._config)
        self._apply_theme()
        messagebox.showinfo("테마 변경", "테마가 저장되었습니다.\n앱을 재시작하면 적용됩니다.")

    def _open_log_folder(self):
        """로그 파일이 있는 폴더를 탐색기로 연다."""
        import subprocess
        folder = os.path.dirname(preflight._log_path())
        try:
            os.makedirs(folder, exist_ok=True)
            # 로그 파일이 아직 없으면 빈 파일이라도 만들어 둠
            log_file = preflight._log_path()
            if not os.path.isfile(log_file):
                preflight.write_log("로그 시작")
            os.startfile(folder)
        except Exception as e:
            messagebox.showinfo(
                "로그 위치",
                f"로그 폴더를 자동으로 열 수 없습니다.\n\n경로:\n{folder}",
            )

    def _check_fabric_update_bg(self):
        """백그라운드: Fabric 로더 최신 버전 확인 후 설정 화면 상태 갱신."""
        mc_dir = (self._preflight_result or {}).get("minecraft_dir")
        if not mc_dir:
            self.after(0, self._apply_fabric_status,
                       {"status": "check_failed", "installed": None, "latest": None})
            return
        try:
            result = preflight.check_fabric_loader_update(mc_dir, GAME_VERSION)
        except Exception as e:
            preflight.write_log(f"[Fabric업데이트확인실패] {e}")
            result = {"status": "check_failed", "installed": None, "latest": None}
        self.after(0, self._apply_fabric_status, result)

    def _apply_fabric_status(self, result: dict):
        """Fabric 업데이트 확인 결과를 설정 화면에 반영.
        설정 화면이 닫혔으면(위젯 없음) 조용히 무시."""
        if not hasattr(self, "_fabric_status_lbl"):
            return
        try:
            if not self._fabric_status_lbl.winfo_exists():
                return
        except Exception:
            return

        self._fabric_update_info = result
        status = result.get("status")

        if status == "up_to_date":
            self._fabric_status_lbl.configure(text="  최신 버전", fg=self._C["text2"])
        elif status == "update_available":
            latest = result.get("latest", "?")
            self._fabric_status_lbl.configure(
                text=f"  → 최신 {latest} 있음", fg=ACCENT)
            self._fabric_update_btn.pack(side="left", padx=(8, 0))
        elif status == "not_installed":
            self._fabric_status_lbl.configure(text="  미설치", fg=self._C["text2"])
        else:  # check_failed
            self._fabric_status_lbl.configure(text="  확인 실패", fg=self._C["text2"])

    def _do_fabric_update(self):
        """Fabric 로더를 최신 버전으로 업데이트 (설치 프로그램 실행)."""
        info = getattr(self, "_fabric_update_info", {})
        latest = info.get("latest", "?")
        installed = info.get("installed", "?")

        if not messagebox.askyesno(
            "Fabric 로더 업데이트",
            f"Fabric 로더를 업데이트합니다.\n\n"
            f"현재: {installed}\n최신: {latest}\n\n"
            f"Fabric 설치 프로그램이 실행됩니다. 계속하시겠습니까?",
        ):
            return

        # 버튼 비활성화 + 상태 표시
        try:
            self._fabric_update_btn.configure(state="disabled", text="설치 중…")
        except Exception:
            pass

        def worker():
            try:
                preflight.write_log(f"[Fabric업데이트] {installed} → {latest} 시작")
                installer = preflight.download_fabric_installer()
                preflight.run_fabric_installer(installer)
                preflight.write_log("[Fabric업데이트] 설치 프로그램 실행 완료")
                self.after(0, self._on_fabric_update_done, True, None)
            except Exception as e:
                preflight.write_log(f"[Fabric업데이트실패] {e}")
                self.after(0, self._on_fabric_update_done, False, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fabric_update_done(self, ok: bool, error: str | None):
        if ok:
            # Fabric 버전을 다시 읽어 _preflight_result 갱신
            try:
                mc_dir = (self._preflight_result or {}).get("minecraft_dir")
                if mc_dir:
                    new_ver = preflight.get_fabric_version(mc_dir, GAME_VERSION)
                    if new_ver and self._preflight_result:
                        self._preflight_result["fabric_version"] = new_ver
            except Exception:
                pass

            messagebox.showinfo(
                "Fabric 업데이트",
                "Fabric 로더 업데이트가 완료되었습니다.",
            )
            # 설정 화면을 새로 그려 갱신된 버전 반영
            self._refresh_settings_view()
        else:
            messagebox.showerror(
                "Fabric 업데이트 실패",
                f"업데이트에 실패했습니다.\n\n원인: {error}",
            )
            try:
                self._fabric_update_btn.configure(state="normal", text="업데이트")
            except Exception:
                pass

    def _refresh_settings_view(self):
        """설정 화면을 다시 그린다 (현재 설정 페이지일 때만)."""
        if self._current_page != "settings":
            return
        self.unbind_all("<MouseWheel>")
        for w in self._content.winfo_children():
            w.destroy()
        self._show_settings_view()


# ── 모드 상세 창 ──────────────────────────────────────────────────────────────

class ModDetailWindow(tk.Toplevel):
    def __init__(self, app: ModInstallerApp, mod_id: str):
        super().__init__(app)
        self._app    = app
        self._mod_id = mod_id
        self._mod    = MOD_BY_ID[mod_id]
        self._C      = app._C

        self.title(self._mod["name"])
        self.resizable(False, False)
        self.configure(bg=self._C["bg"])
        # 부모 앱 중앙에 배치
        _w, _h = 500, 500
        self.update_idletasks()
        _px = app.winfo_rootx() + (app.winfo_width()  - _w) // 2
        _py = app.winfo_rooty() + (app.winfo_height() - _h) // 2
        self.geometry(f"{_w}x{_h}+{_px}+{_py}")
        self.grab_set()

        self._build()
        threading.Thread(target=self._load_remote, daemon=True).start()

    def _build(self):
        mod = self._mod
        C   = self._C
        cat   = mod["category"]
        color = CATEGORY_COLOR.get(cat, "#7F8C8D")

        # 헤더 (색 배경 제거 — surface 배경 + 텍스트)
        header = tk.Frame(self, bg=C["surface"], height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=mod["name"], font=("Segoe UI", 16, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(side="left", padx=24, pady=20)
        tk.Label(header, text=cat, font=FONT_SMALL,
                 bg=C["surface"], fg=C["text2"]).pack(side="right", padx=24, pady=28)

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=16)

        def info_row(label, value, value_fg=None):
            f = tk.Frame(body, bg=C["bg"])
            f.pack(fill="x", pady=3)
            tk.Label(f, text=label, font=FONT_SMALL, width=14,
                     bg=C["bg"], fg=C["text2"], anchor="w").pack(side="left")
            tk.Label(f, text=value, font=FONT_SMALL,
                     bg=C["bg"], fg=value_fg or C["text"], anchor="w").pack(side="left")

        info_row("동글랜드 허용", "✅ 허용", ACCENT)

        installed_ver = app_registry_version(self._app, mod["id"])
        info_row("설치된 버전", installed_ver or "미설치")

        self._latest_lbl = None
        f = tk.Frame(body, bg=C["bg"])
        f.pack(fill="x", pady=3)
        tk.Label(f, text="최신 버전", font=FONT_SMALL, width=14,
                 bg=C["bg"], fg=C["text2"], anchor="w").pack(side="left")
        self._latest_lbl = tk.Label(f, text="확인 중...", font=FONT_SMALL,
                                    bg=C["bg"], fg=C["text2"])
        self._latest_lbl.pack(side="left")

        self._author_lbl = None
        f2 = tk.Frame(body, bg=C["bg"])
        f2.pack(fill="x", pady=3)
        tk.Label(f2, text="제작자", font=FONT_SMALL, width=14,
                 bg=C["bg"], fg=C["text2"], anchor="w").pack(side="left")
        self._author_lbl = tk.Label(f2, text="로딩 중...", font=FONT_SMALL,
                                    bg=C["bg"], fg=C["text2"])
        self._author_lbl.pack(side="left")

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=12)

        tk.Label(body, text=mod["description"], font=FONT_NORMAL,
                 bg=C["bg"], fg=C["text"], justify="left",
                 wraplength=440, anchor="w").pack(fill="x")

        # 하단 버튼
        btn_frame = tk.Frame(self, bg=C["bg"])
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        status = self._app._get_status(mod["id"])

        if status in ("not_installed", "conflict"):
            disabled = (status == "conflict" or mod.get("required"))
            tk.Button(
                btn_frame, text="설치", font=FONT_NORMAL,
                bg=ACCENT if not disabled else C["surface2"],
                fg="white" if not disabled else C["text2"],
                relief="flat", padx=18, pady=6,
                state="normal" if not disabled else "disabled",
                command=lambda: self._on_install(),
            ).pack(side="left", padx=(0, 8))

        if status in ("installed", "update", "checking"):
            if status == "update":
                tk.Button(
                    btn_frame, text="업데이트", font=FONT_NORMAL,
                    bg="#71717A", fg="white", relief="flat", padx=18, pady=6,
                    command=lambda: self._on_update(),
                ).pack(side="left", padx=(0, 8))

            remove_disabled = mod.get("required", False)
            tk.Button(
                btn_frame, text="제거", font=FONT_NORMAL,
                bg=C["surface2"] if not remove_disabled else C["surface2"],
                fg=C["text2"],
                relief="flat", padx=18, pady=6,
                state="normal" if not remove_disabled else "disabled",
                command=lambda: self._on_remove(),
            ).pack(side="left")

        tk.Button(
            btn_frame, text="닫기", font=FONT_NORMAL,
            bg=self._C["surface2"], fg=self._C["text2"],
            relief="flat", padx=18, pady=6,
            command=self.destroy,
        ).pack(side="right")

    def _load_remote(self):
        slug = self._mod.get("slug")
        if not slug:
            self.after(0, lambda: self._latest_lbl and self._latest_lbl.configure(text="번들 포함 모드"))
            self.after(0, lambda: self._author_lbl and self._author_lbl.configure(text=APP_AUTHOR))
            return
        try:
            latest = modrinth_api.get_latest_compatible_version(slug, GAME_VERSION, LOADER)
            ver = latest.get("version_number", "알 수 없음") if latest else "없음"
            self.after(0, lambda v=ver: self._latest_lbl and self._latest_lbl.configure(
                text=v, fg=self._C["text"]))
        except Exception:
            self.after(0, lambda: self._latest_lbl and self._latest_lbl.configure(text="조회 실패"))

        try:
            author = modrinth_api.get_project_author(slug)
            self.after(0, lambda a=author: self._author_lbl and self._author_lbl.configure(
                text=a, fg=self._C["text"]))
        except Exception:
            self.after(0, lambda: self._author_lbl and self._author_lbl.configure(text="알 수 없음"))

    def _on_install(self):
        self.destroy()
        self._app._do_install(self._mod_id)

    def _on_update(self):
        self.destroy()
        self._app._do_update(self._mod_id)

    def _on_remove(self):
        if messagebox.askyesno("제거 확인", f"{self._mod['name']}을(를) 제거할까요?"):
            self.destroy()
            self._app._do_remove(self._mod_id)


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def app_registry_version(app: ModInstallerApp, mod_id: str) -> str | None:
    if app._registry:
        return app._registry.get_installed_version(mod_id)
    return None


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main():
    app = ModInstallerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
