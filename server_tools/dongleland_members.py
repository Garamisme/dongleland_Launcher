"""dongleland_members.py — 운영자용 멤버 관리 + whitelist.json export CLI.

⚠️ 이 도구는 **운영자/서버 측 전용**이다. 런처 배포물에 절대 포함하지 말 것.
   (HANDOFF_AUTH_WHITELIST.md §6-4: 클라이언트 불신 원칙 — DB/화이트리스트
    원본은 운영자 측에서만 관리한다.)

원칙 (HANDOFF_AUTH_WHITELIST.md):
  - source of truth = SQLite DB (schema.sql). whitelist.json 은 파생물.
  - 멤버는 삭제하지 않는다 → status 변경으로 제외 (이력·부가데이터 보존).
    그래서 이 CLI 에는 delete 명령이 아예 없다.
  - UUID 는 DB 에 하이픈 없는 소문자 32자로 저장, export 시 v_whitelist 뷰가
    8-4-4-4-12 형식으로 변환.

의존성: Python 표준 라이브러리만 (운영자 PC 에 pip 불필요).
UUID 조회: Mojang 공개 API (api.mojang.com) — 닉네임만 알아도 등록 가능.

사용 예:
  py dongleland_members.py init
  py dongleland_members.py add Garamisme                  # UUID 는 Mojang 에서 자동 조회
  py dongleland_members.py add Friend1 --uuid a1b2...     # UUID 직접 지정
  py dongleland_members.py set-status Friend1 suspended   # 정지 (삭제 아님)
  py dongleland_members.py whitelist Friend1 off
  py dongleland_members.py list
  py dongleland_members.py list --status suspended
  py dongleland_members.py info Garamisme
  py dongleland_members.py export                          # ./whitelist.json
  py dongleland_members.py export --server-dir C:/mc_server # <dir>/whitelist.json
  py dongleland_members.py sync-name Garamisme             # 닉변 반영
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "members.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

STATUSES = ("active", "suspended", "banned", "pending")
_UUID32 = re.compile(r"^[0-9a-f]{32}$")


def norm_uuid(u: str) -> str:
    """하이픈 유무 무관 입력 → 하이픈 없는 소문자 32자 (DB 저장 규칙)."""
    s = u.replace("-", "").strip().lower()
    if not _UUID32.match(s):
        raise SystemExit(f"[오류] UUID 형식이 아닙니다: {u!r} (16진수 32자 필요)")
    return s


def mojang_lookup(username: str) -> tuple[str, str]:
    """닉네임 → (uuid 32자, 정확한 표기 닉네임). Mojang 공개 API."""
    url = f"https://api.mojang.com/users/profiles/minecraft/{urllib.request.quote(username)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            if r.status == 200:
                data = json.loads(r.read().decode("utf-8"))
                return norm_uuid(data["id"]), data["name"]
    except urllib.error.HTTPError as e:
        if e.code in (204, 404):
            raise SystemExit(f"[오류] Mojang 에 '{username}' 닉네임이 없습니다. 정품 닉네임인지 확인해주세요.")
        raise SystemExit(f"[오류] Mojang API 오류: HTTP {e.code}")
    except Exception as e:
        raise SystemExit(f"[오류] Mojang API 조회 실패: {e}\n"
                         "네트워크를 확인하거나 --uuid 로 직접 지정해주세요.")
    raise SystemExit(f"[오류] Mojang 에 '{username}' 닉네임이 없습니다.")


def open_db(path: str) -> sqlite3.Connection:
    exists = os.path.isfile(path)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    if not exists:
        print(f"[안내] DB 가 없어 새로 만듭니다: {path}")
        apply_schema(con)
    return con


def apply_schema(con: sqlite3.Connection):
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        con.executescript(f.read())
    con.commit()


def find_member(con, key: str) -> sqlite3.Row:
    """닉네임 또는 UUID(하이픈 유무 무관)로 멤버 1명 조회."""
    k = key.replace("-", "").lower()
    if _UUID32.match(k):
        row = con.execute("SELECT * FROM members WHERE mc_uuid=?", (k,)).fetchone()
    else:
        row = con.execute(
            "SELECT * FROM members WHERE lower(mc_username)=lower(?)", (key,)).fetchone()
    if not row:
        raise SystemExit(f"[오류] 멤버를 찾을 수 없습니다: {key}")
    return row


# ── 명령들 ────────────────────────────────────────────────────────────────

def cmd_init(args):
    con = sqlite3.connect(args.db)
    apply_schema(con)
    print(f"[완료] 스키마 적용: {args.db}")


def cmd_add(args):
    con = open_db(args.db)
    if args.uuid:
        uuid, name = norm_uuid(args.uuid), args.username
    else:
        uuid, name = mojang_lookup(args.username)
        if name != args.username:
            print(f"[안내] Mojang 정식 표기로 저장합니다: {args.username} → {name}")
    dup = con.execute("SELECT mc_username FROM members WHERE mc_uuid=?", (uuid,)).fetchone()
    if dup:
        raise SystemExit(f"[오류] 이미 등록된 UUID 입니다 (닉네임: {dup['mc_username']}).")
    status = "pending" if args.pending else "active"
    wl = 0 if (args.no_whitelist or args.pending) else 1
    con.execute(
        "INSERT INTO members (mc_uuid, mc_username, status, is_whitelisted, role, note) "
        "VALUES (?,?,?,?,?,?)",
        (uuid, name, status, wl, args.role, args.note))
    con.commit()
    print(f"[완료] 추가: {name} ({uuid}) status={status} whitelist={'O' if wl else 'X'}")
    _remind_export()


def cmd_set_status(args):
    con = open_db(args.db)
    m = find_member(con, args.member)
    con.execute("UPDATE members SET status=? WHERE id=?", (args.status, m["id"]))
    con.commit()
    print(f"[완료] {m['mc_username']}: {m['status']} → {args.status}"
          + ("  (whitelist export 에서 자동 제외됩니다)" if args.status != "active" else ""))
    _remind_export()


def cmd_whitelist(args):
    con = open_db(args.db)
    m = find_member(con, args.member)
    wl = 1 if args.onoff == "on" else 0
    con.execute("UPDATE members SET is_whitelisted=? WHERE id=?", (wl, m["id"]))
    con.commit()
    print(f"[완료] {m['mc_username']}: whitelist {'포함' if wl else '제외'}")
    _remind_export()


def cmd_list(args):
    con = open_db(args.db)
    q = "SELECT mc_username, mc_uuid, status, is_whitelisted, role, joined_at FROM members"
    params = ()
    if args.status:
        q += " WHERE status=?"; params = (args.status,)
    rows = con.execute(q + " ORDER BY id").fetchall()
    if not rows:
        print("(멤버 없음)"); return
    print(f"{'닉네임':<18} {'상태':<10} {'WL':<3} {'역할':<7} 가입일")
    for r in rows:
        print(f"{r['mc_username']:<18} {r['status']:<10} "
              f"{'O' if r['is_whitelisted'] else 'X':<3} {r['role']:<7} {r['joined_at'][:10]}")
    n_export = con.execute("SELECT COUNT(*) FROM v_whitelist").fetchone()[0]
    print(f"— 총 {len(rows)}명 / export 대상 {n_export}명")


def cmd_info(args):
    con = open_db(args.db)
    m = find_member(con, args.member)
    for k in m.keys():
        print(f"{k:>16}: {m[k]}")


def cmd_export(args):
    con = open_db(args.db)
    rows = con.execute("SELECT name, uuid FROM v_whitelist ORDER BY name").fetchall()
    payload = [{"uuid": r["uuid"], "name": r["name"]} for r in rows]
    out = (os.path.join(args.server_dir, "whitelist.json")
           if args.server_dir else args.out)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out)  # 서버가 읽는 도중 반쪽 파일을 보지 않도록 원자적 교체
    print(f"[완료] {len(payload)}명 export → {out}")
    if not args.server_dir:
        print("       마크 서버 폴더에 복사 후, 콘솔에서 /whitelist reload 실행")
    else:
        print("       서버 콘솔에서 /whitelist reload 실행 (재시작 불필요)")


def cmd_sync_name(args):
    con = open_db(args.db)
    m = find_member(con, args.member)
    uuid, current_name = _name_by_uuid(m["mc_uuid"])
    if current_name == m["mc_username"]:
        print(f"[안내] 변경 없음: {current_name}")
        return
    con.execute("UPDATE members SET mc_username=? WHERE id=?", (current_name, m["id"]))
    con.commit()
    print(f"[완료] 닉변 반영: {m['mc_username']} → {current_name}")
    _remind_export()


def _name_by_uuid(uuid32: str) -> tuple[str, str]:
    """UUID → 현재 닉네임 (sessionserver 프로필 조회)."""
    url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid32}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            return uuid32, data["name"]
    except Exception as e:
        raise SystemExit(f"[오류] Mojang 프로필 조회 실패: {e}")


def _remind_export():
    print("       (변경은 export 후 서버 반영 시 적용됩니다: export 명령)")


def main(argv=None):
    p = argparse.ArgumentParser(
        description="동글랜드 멤버 관리 + whitelist.json export (운영자 전용)")
    p.add_argument("--db", default=DEFAULT_DB, help=f"DB 경로 (기본: {DEFAULT_DB})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="스키마 적용 (최초 1회)").set_defaults(fn=cmd_init)

    a = sub.add_parser("add", help="멤버 추가 (UUID 미지정 시 Mojang 자동 조회)")
    a.add_argument("username")
    a.add_argument("--uuid", help="UUID 직접 지정 (하이픈 유무 무관)")
    a.add_argument("--role", default="member", choices=("member", "vip", "staff", "admin"))
    a.add_argument("--note", default=None, help="운영자 메모")
    a.add_argument("--pending", action="store_true", help="승인 대기로 추가 (WL 제외)")
    a.add_argument("--no-whitelist", action="store_true", help="WL 제외 상태로 추가")
    a.set_defaults(fn=cmd_add)

    s = sub.add_parser("set-status", help="상태 변경 (삭제 대신 이걸 쓸 것)")
    s.add_argument("member", help="닉네임 또는 UUID")
    s.add_argument("status", choices=STATUSES)
    s.set_defaults(fn=cmd_set_status)

    w = sub.add_parser("whitelist", help="WL 포함/제외 토글")
    w.add_argument("member"); w.add_argument("onoff", choices=("on", "off"))
    w.set_defaults(fn=cmd_whitelist)

    l = sub.add_parser("list", help="멤버 목록")
    l.add_argument("--status", choices=STATUSES)
    l.set_defaults(fn=cmd_list)

    i = sub.add_parser("info", help="멤버 상세")
    i.add_argument("member"); i.set_defaults(fn=cmd_info)

    e = sub.add_parser("export", help="whitelist.json 생성 (v_whitelist 뷰)")
    e.add_argument("--out", default="whitelist.json")
    e.add_argument("--server-dir", default=None,
                   help="마크 서버 폴더 — 지정 시 <dir>/whitelist.json 에 직접 기록")
    e.set_defaults(fn=cmd_export)

    n = sub.add_parser("sync-name", help="Mojang 닉변을 DB 에 반영")
    n.add_argument("member"); n.set_defaults(fn=cmd_sync_name)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
