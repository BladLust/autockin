import os
import platform
import sys

import requests

BASE_URL = "https://glados.cloud"
CHECKIN_URL = f"{BASE_URL}/api/user/checkin"
STATUS_URL = f"{BASE_URL}/api/user/status"
CHECKIN_PAGE_URL = f"{BASE_URL}/console/checkin"
CHECKIN_BODY = b'{"token":"glados.cloud"}'
TIMEOUT = 15

SUCCESS_MESSAGES = (
    "checkin! got",
    "checkin repeats!",
    "today's observation logged",
)


def build_user_agent():
    runtime = platform.platform(aliased=True, terse=True)
    return (
        f"autockin/1.0 ({runtime}; python-requests/{requests.__version__}; "
        "https://github.com/BladLust/autockin)"
    )


def build_checkin_headers(cookie):
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=utf-8",
        "Origin": BASE_URL,
        "Referer": CHECKIN_PAGE_URL,
        "User-Agent": build_user_agent(),
        "Cookie": cookie,
    }


def build_status_headers(cookie):
    headers = build_checkin_headers(cookie)
    headers.pop("Content-Type", None)
    return headers


def parse_cookies(raw_cookies):
    """Parse `COOKIES` env var: cookie strings joined by `&&`."""
    if not raw_cookies:
        raise RuntimeError("COOKIES is not configured")

    cookies = [cookie.strip() for cookie in raw_cookies.split("&&")]

    if any(not cookie for cookie in cookies):
        raise RuntimeError("COOKIES contains an empty entry")

    return cookies


def request_json(session, method, url, headers, **kwargs):
    response = session.request(
        method,
        url,
        headers=headers,
        timeout=TIMEOUT,
        **kwargs,
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{url} returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"{url} returned an unexpected response")

    return payload


def checkin(session, cookie):
    result = request_json(
        session,
        "POST",
        CHECKIN_URL,
        headers=build_checkin_headers(cookie),
        data=CHECKIN_BODY,
    )

    message = str(result.get("message", "")).strip()
    normalized = message.lower()

    if not any(marker in normalized for marker in SUCCESS_MESSAGES):
        raise RuntimeError(f"Check-in failed: code={result.get('code')!r}, message={message!r}")

    return message


def get_status(session, cookie):
    result = request_json(
        session,
        "GET",
        STATUS_URL,
        headers=build_status_headers(cookie),
    )

    data = result.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Invalid account status")

    if data.get("leftDays") is None:
        raise RuntimeError("Missing remaining days")

    try:
        return int(float(data["leftDays"]))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid remaining days") from exc


def run_account(cookie, index):
    with requests.Session() as session:
        session.headers.clear()
        message = checkin(session, cookie)
        remaining_days = get_status(session, cookie)
    print(f"Account {index}: {message}\nRemaining days: {remaining_days}")


def start():
    raw_cookies = os.environ.get("COOKIES", "").strip()

    try:
        cookies = parse_cookies(raw_cookies)
    except RuntimeError as exc:
        print(f"::error::{exc}")
        return 1

    failures = 0
    for index, cookie in enumerate(cookies, start=1):
        try:
            run_account(cookie, index)
        except Exception as exc:
            print(f"::error::Account {index} failed: {exc}", file=sys.stderr)
            failures += 1

    if failures:
        print(f"{failures}/{len(cookies)} accounts failed")
        return 1

    print(f"All {len(cookies)} accounts checked in successfully")
    return 0


def main_handler(event, context):
    return start()


if __name__ == "__main__":
    sys.exit(start())
