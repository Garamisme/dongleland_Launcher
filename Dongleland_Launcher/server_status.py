"""마인크래프트 서버 상태 조회 (Server List Ping 프로토콜).

외부 API 없이 서버에 직접 TCP 로 접속해 상태(온라인 여부, 접속자 수, MOTD)를
가져온다. 표준 SLP(핸드셰이크 → 상태 요청 → JSON 응답) 절차를 따른다.

참고: 이 모듈은 표준 라이브러리(socket, struct, json)만 사용한다.
"""

import json
import os
import socket
import struct
import time


def _write_varint(value: int) -> bytes:
    """정수를 마인크래프트 프로토콜의 VarInt(가변 길이 정수)로 인코딩."""
    out = b""
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out += bytes([b | 0x80])
        else:
            out += bytes([b])
            break
    return out


def _read_varint(sock: socket.socket) -> int:
    """소켓에서 VarInt 를 읽어 정수로 디코딩."""
    num = 0
    for i in range(5):
        byte = sock.recv(1)
        if not byte:
            raise IOError("소켓이 닫혔습니다")
        b = byte[0]
        num |= (b & 0x7F) << (7 * i)
        if not (b & 0x80):
            break
    return num


def _pack_string(s: str) -> bytes:
    data = s.encode("utf-8")
    return _write_varint(len(data)) + data


def _extract_motd(desc) -> str:
    """description 필드는 문자열이거나 {text, extra:[...]} 형태일 수 있다."""
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        text = desc.get("text", "")
        for part in desc.get("extra", []) or []:
            if isinstance(part, dict):
                text += part.get("text", "")
            elif isinstance(part, str):
                text += part
        return text
    return ""


def _resolve_srv_nslookup(host: str, timeout: float = 4.0):
    """Windows 시스템 리졸버(nslookup)로 SRV 조회. (subprocess)
    파이썬 수동 UDP DNS 가 방화벽에 막히는 환경 대비용 1차 수단.
    반환 (target, port) 또는 None."""
    import subprocess
    import re as _re
    qname = f"_minecraft._tcp.{host}"
    try:
        # -type=srv 로 조회. Windows/유닉스 nslookup 모두 유사 출력.
        out = subprocess.run(
            ["nslookup", "-type=srv", qname],
            capture_output=True, timeout=timeout,
            creationflags=(0x08000000 if os.name == "nt" else 0),  # CREATE_NO_WINDOW
        )
        text = (out.stdout or b"").decode("utf-8", "ignore") + \
               (out.stderr or b"").decode("utf-8", "ignore")
    except Exception:
        return None
    # 출력에서 port 와 target(svr hostname) 추출
    port = None
    target = None
    for line in text.splitlines():
        low = line.lower()
        m = _re.search(r"port\s*[:=]\s*(\d+)", low)
        if m:
            port = int(m.group(1))
        # "svr hostname" 또는 "hostname" 라인
        m2 = _re.search(r"(?:svr hostname|hostname)\s*[:=]\s*([\w.\-]+)", low)
        if m2:
            target = m2.group(1)
    if target and port:
        return (target, port)
    return None


def _resolve_srv(host: str, timeout: float = 3.0):
    """마인크래프트 SRV 레코드(_minecraft._tcp.<host>)를 조회해
    (실제 호스트, 포트)를 반환. 없으면 None.

    많은 커스텀 도메인 서버는 SRV 로 실제 IP:포트를 가리키므로,
    도메인:25565 직접 접속만으로는 실패할 수 있다.
    1) 시스템 nslookup (방화벽 친화적) → 2) 파이썬 UDP DNS 순으로 시도.
    """
    # 1) 시스템 리졸버 우선
    r = _resolve_srv_nslookup(host, timeout=min(timeout + 1.5, 5.0))
    if r:
        return r
    # 2) 파이썬 UDP DNS 폴백
    return _resolve_srv_udp(host, timeout=timeout)


def _resolve_srv_udp(host: str, timeout: float = 3.0):
    """파이썬 표준 라이브러리만으로 UDP DNS SRV 질의."""
    import random
    qname = f"_minecraft._tcp.{host}"
    tid = random.randint(0, 0xFFFF)
    header = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    q = b""
    for label in qname.split("."):
        q += bytes([len(label)]) + label.encode("ascii")
    q += b"\x00"
    q += struct.pack(">HH", 33, 1)
    packet = header + q

    for dns in ("8.8.8.8", "1.1.1.1"):
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(timeout)
            s.sendto(packet, (dns, 53))
            data, _ = s.recvfrom(512)
        except Exception:
            continue
        finally:
            if s:
                try: s.close()
                except Exception: pass
        try:
            ancount = struct.unpack(">H", data[6:8])[0]
            if ancount == 0:
                continue
            idx = 12
            while data[idx] != 0:
                idx += 1 + data[idx]
            idx += 1 + 4
            if data[idx] & 0xC0 == 0xC0:
                idx += 2
            else:
                while data[idx] != 0:
                    idx += 1 + data[idx]
                idx += 1
            rtype, _rclass, _ttl, rdlen = struct.unpack(">HHIH", data[idx:idx+10])
            idx += 10
            if rtype != 33:
                continue
            priority, weight, port = struct.unpack(">HHH", data[idx:idx+6])
            tidx = idx + 6
            labels = []
            guard = 0
            while guard < 128:
                guard += 1
                ln = data[tidx]
                if ln == 0:
                    break
                if ln & 0xC0 == 0xC0:
                    tidx = struct.unpack(">H", data[tidx:tidx+2])[0] & 0x3FFF
                    continue
                labels.append(data[tidx+1:tidx+1+ln].decode("ascii", "ignore"))
                tidx += 1 + ln
            target = ".".join(labels)
            if target:
                return (target, port)
        except Exception:
            continue
    return None


def ping(host: str, port: int = 25565, timeout: float = 4.0) -> dict:
    """서버 상태를 조회한다. SRV 레코드가 있으면 먼저 사용.

    반환:
      온라인: {"online": True, "players_online": int, "players_max": int,
               "motd": str, "version": str, "latency_ms": int}
      오프라인/실패: {"online": False, "error": str}
    """
    # SRV 우선 조회 (실패해도 직접 접속으로 폴백). DNS 가 막힌 환경에서
    # 지연되지 않도록 짧은 타임아웃 사용.
    connect_host, connect_port = host, port
    try:
        srv = _resolve_srv(host, timeout=1.5)
        if srv:
            connect_host, connect_port = srv
    except Exception:
        pass
    return _ping_direct(host, connect_host, connect_port, timeout)


def _ping_direct(vhost: str, host: str, port: int, timeout: float) -> dict:
    """실제 TCP SLP 핑. vhost 는 핸드셰이크에 넣을 원래 도메인."""
    start = time.time()
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(timeout)

        # 1) 핸드셰이크 (next_state = 1 : status)
        handshake = (
            b"\x00"
            + _write_varint(0)
            + _pack_string(vhost)
            + struct.pack(">H", port)
            + _write_varint(1)
        )
        sock.sendall(_write_varint(len(handshake)) + handshake)
        # 2) 상태 요청
        sock.sendall(_write_varint(1) + b"\x00")
        # 3) 응답 읽기
        _read_varint(sock)
        _read_varint(sock)
        json_len = _read_varint(sock)
        data = b""
        while len(data) < json_len:
            chunk = sock.recv(json_len - len(data))
            if not chunk:
                break
            data += chunk
        status = json.loads(data.decode("utf-8", errors="ignore"))
        players = status.get("players", {}) or {}
        version = status.get("version", {}) or {}
        latency = int((time.time() - start) * 1000)
        return {
            "online": True,
            "players_online": int(players.get("online", 0)),
            "players_max": int(players.get("max", 0)),
            "motd": _extract_motd(status.get("description", "")),
            "version": version.get("name", ""),
            "latency_ms": latency,
        }
    except (socket.timeout, ConnectionRefusedError, socket.gaierror, OSError) as e:
        return {"online": False, "error": str(e)}
    except Exception as e:
        return {"online": False, "error": str(e)}
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


if __name__ == "__main__":
    import sys
    h = sys.argv[1] if len(sys.argv) > 1 else "donglegleland.com"
    print(ping(h))
