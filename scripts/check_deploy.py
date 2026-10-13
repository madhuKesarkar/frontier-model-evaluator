"""Scripted checks for the read-only public demo (Phase 5 done-when, D-13).

    python scripts/check_deploy.py https://<site>.netlify.app https://<api>.onrender.com

Checks: health; leaderboard has rows; SPA routes load; writes refused (405); CORS allows the
site and refuses other origins; the JS bundle has no localhost URL and no key-like string and
points at the API. Standard library only. Exit 1 on any failure.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request

SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{30,})")
# A dev server URL always has a port; react-router's internal "http://localhost" base has none.
LOCAL = re.compile(r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0):\d+")


def fetch(url: str, method: str = "GET", headers: dict[str, str] | None = None,
          body: bytes | None = None) -> tuple[int, dict[str, str], str]:  # fmt: skip
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"not an http(s) URL: {url}")
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310 - https URLs given by the architect
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read().decode()


def main(site: str, api: str) -> int:
    site, api = site.rstrip("/"), api.rstrip("/")
    results: list[tuple[bool, str]] = []

    def check(ok: bool, label: str) -> None:
        results.append((ok, label))
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

    print("API (the first call may take ~1 min while the free instance wakes up)")
    code, _, body = fetch(f"{api}/api/v1/health")
    check(code == 200 and json.loads(body).get("status") == "ok", "health returns ok")
    code, _, body = fetch(f"{api}/api/v1/leaderboard")
    data = json.loads(body) if code == 200 else {}
    check(bool(data.get("rows")), f"leaderboard has rows (source: {data.get('run_source')})")
    code, _, body = fetch(f"{api}/api/v1/runs", "POST", {"Content-Type": "application/json"}, b"{}")
    check(code == 405 and "read-only" in body, "writes are refused (405 read-only)")
    code, _, _ = fetch(f"{api}/api/v1/fit", "POST", {"Content-Type": "application/json"},
                       b'{"profile_id": "tpl-code-assistant"}')  # fmt: skip
    check(code == 200, "POST /fit still works (allowed in read-only mode)")
    _, headers, _ = fetch(f"{api}/api/v1/health", headers={"Origin": site})
    check(headers.get("access-control-allow-origin") == site, "CORS allows the site")
    _, headers, _ = fetch(f"{api}/api/v1/health", headers={"Origin": "https://evil.example"})
    check("access-control-allow-origin" not in headers, "CORS refuses other origins")

    print("Site")
    for path in ("/", "/fit", "/models/any-model"):
        code, _, html = fetch(f"{site}{path}")
        check(code == 200 and '<div id="root">' in html, f"{path} loads the app")
    code, _, html = fetch(f"{site}/")
    bundles = re.findall(r'src="(/assets/[^"]+\.js)"', html)
    js = "".join(fetch(f"{site}{b}")[2] for b in bundles)
    check(bool(js), f"JS bundle found ({len(bundles)} file)")
    check(not LOCAL.search(js), "bundle has no localhost API URL")
    check(not SECRET.search(js), "bundle has no key-like string")
    check(api in js, "bundle points at the API")

    failed = [label for ok, label in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
