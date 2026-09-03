#!/usr/bin/env python3
"""
인증서 만료 점검

IDC에서 관리하는 도메인이 늘어나면 만료일을 사람이 기억할 수 없다.
인증서 만료는 예고 없이 오지 않는데도 가장 흔한 서비스 중단 원인 중
하나다. 갱신 담당자가 바뀌거나 자동 갱신이 조용히 멈춰 있어도 만료
당일까지 아무도 모르기 때문이다.

이 스크립트는 도메인 목록을 받아 잔여일을 계산하고, 남은 기간에 따라
종료 코드를 다르게 낸다. cron에 걸어 두면 임박한 것만 알림이 온다.

    0 = 여유    1 = 갱신 준비 (기본 30일 이내)    2 = 임박 또는 오류 (7일 이내)

사용법
    python3 cert_expiry.py example.com api.example.com
    python3 cert_expiry.py --file domains.txt --warn 45 --crit 14
    python3 cert_expiry.py example.com:8443
"""

import argparse
import socket
import ssl
import sys
from datetime import datetime, timezone

FMT = "%b %d %H:%M:%S %Y %Z"


def parse_target(text):
    text = text.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("https://"):
        text = text[8:]
    text = text.split("/")[0]
    if ":" in text:
        host, _, port = text.rpartition(":")
        try:
            return host, int(port)
        except ValueError:
            return text, 443
    return text, 443


def fetch(host, port, timeout):
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            return tls.getpeercert(), tls.version()


def field(cert, key, sub):
    for rdn in cert.get(key, ()):
        for k, v in rdn:
            if k == sub:
                return v
    return "-"


def sans(cert):
    names = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
    return names


def check(target, warn_days, crit_days, timeout):
    host, port = target
    label = host if port == 443 else f"{host}:{port}"
    try:
        cert, version = fetch(host, port, timeout)
    except ssl.SSLCertVerificationError as exc:
        return 2, label, "검증 실패", exc.verify_message or str(exc)
    except (socket.timeout, TimeoutError):
        return 2, label, "시간 초과", f"{timeout}초 내 응답 없음"
    except (OSError, ssl.SSLError) as exc:
        return 2, label, "연결 실패", str(exc)

    if not cert:
        return 2, label, "정보 없음", "인증서를 가져오지 못했습니다"

    try:
        expires = datetime.strptime(cert["notAfter"], FMT).replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return 2, label, "해석 실패", "만료일 형식을 읽지 못했습니다"

    left = (expires - datetime.now(timezone.utc)).days
    issuer = field(cert, "issuer", "organizationName")
    names = sans(cert)
    extra = f" · SAN {len(names)}개" if len(names) > 1 else ""
    detail = f"{expires:%Y-%m-%d} 만료 · {issuer} · {version}{extra}"

    if left < 0:
        return 2, label, f"만료됨 {abs(left)}일", detail
    if left <= crit_days:
        return 2, label, f"{left}일 남음", detail
    if left <= warn_days:
        return 1, label, f"{left}일 남음", detail
    return 0, label, f"{left}일 남음", detail


def main():
    ap = argparse.ArgumentParser(description="TLS 인증서 만료 점검")
    ap.add_argument("domains", nargs="*", help="도메인 (host 또는 host:port)")
    ap.add_argument("--file", help="도메인 목록 파일 (한 줄에 하나, # 주석 허용)")
    ap.add_argument("--warn", type=int, default=30, help="갱신 준비 기준일")
    ap.add_argument("--crit", type=int, default=7, help="임박 기준일")
    ap.add_argument("--timeout", type=float, default=6.0, help="연결 제한 시간(초)")
    args = ap.parse_args()

    raw = list(args.domains)
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                raw += f.read().splitlines()
        except OSError as exc:
            print(f"목록 파일을 읽지 못했습니다: {exc}", file=sys.stderr)
            return 2

    targets = [t for t in (parse_target(x) for x in raw) if t]
    if not targets:
        print("점검할 도메인이 없습니다.", file=sys.stderr)
        return 2

    print(f"\n인증서 점검 {len(targets)}건 · 준비 {args.warn}일 / 임박 {args.crit}일 기준")
    print("=" * 80)

    worst = 0
    for target in targets:
        level, label, left, detail = check(target, args.warn, args.crit, args.timeout)
        mark = {0: "여유", 1: "준비", 2: "임박"}[level]
        print(f"  [{mark}] {label:<30}{left:>12}   {detail}")
        worst = max(worst, level)

    print("-" * 80)
    print({0: "갱신이 임박한 인증서는 없습니다.",
           1: f"{args.warn}일 이내 만료 예정인 인증서가 있습니다. 갱신을 준비하십시오.",
           2: "즉시 확인이 필요한 인증서가 있습니다."}[worst])
    return worst


if __name__ == "__main__":
    sys.exit(main())
