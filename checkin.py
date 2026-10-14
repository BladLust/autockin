import os
import sys

import requests

BASE_URL = "https://glados.cloud"
CHECKIN_URL = f"{BASE_URL}/api/user/checkin"
STATUS_URL = f"{BASE_URL}/api/user/status"

TIMEOUT = 15

# Default to the macOS Safari profile supplied by upstream.
# Override USER_AGENT with the value from the browser that supplied COOKIES.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/27.0 Safari/605.1.15"
)


def build_headers():
    user_agent = os.environ.get("USER_AGENT", "").strip() or USER_AGENT
    language = os.environ.get("ACCEPT_LANGUAGE", "").strip() or "zh-CN,zh-Hans;q=0.9"
    for name, value in (("USER_AGENT", user_agent), ("ACCEPT_LANGUAGE", language)):
        if "\r" in value or "\n" in value:
            raise ValueError(f"{name} must be a single-line header value")

    # Safari does not send Chromium's sec-ch-ua client hints. Only advertise
    # compression formats that this requests installation can actually decode.
    common = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": requests.utils.default_headers()["Accept-Encoding"],
        "Accept-Language": language,
        "Referer": f"{BASE_URL}/console/checkin",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": user_agent,
    }
    return (
        {**common, "Content-Type": "application/json;charset=utf-8", "Origin": BASE_URL},
        common.copy(),
    )


# Keep the compact JSON body used by the browser; requests computes its length.
CHECKIN_BODY = b'{"token":"glados.cloud"}'

SUCCESS_MESSAGES = (
    "checkin! got",
    "checkin repeats!",
    "today's observation logged",
)


def request_json(session, method, url, headers, **kwargs):
    response = session.request(
        method,
        url,
        headers=headers,
        timeout=TIMEOUT,
        allow_redirects=False,
        **kwargs,
    )

    # A login redirect must not forward a manually supplied Cookie header.
    if 300 <= response.status_code < 400:
        raise RuntimeError("Unexpected redirect; check the endpoint and account cookie")
    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{url} returned invalid JSON") from exc

    if not isinstance(result, dict):
        raise RuntimeError(f"{url} returned an unexpected response")

    return result


def checkin(session, cookie):
    checkin_headers, _ = build_headers()
    result = request_json(
        session,
        "POST",
        CHECKIN_URL,
        headers={
            **checkin_headers,
            "Cookie": cookie,
        },
        data=CHECKIN_BODY,
    )

    message = result.get("message", "")
    normalized = str(message).strip().lower()

    if not any(marker in normalized for marker in SUCCESS_MESSAGES):
        raise RuntimeError(f"Check-in failed: code={result.get('code')!r}, message={message!r}")

    return message


def get_status(session, cookie):
    _, status_headers = build_headers()
    result = request_json(
        session,
        "GET",
        STATUS_URL,
        headers={
            **status_headers,
            "Cookie": cookie,
        },
    )

    data = result.get("data")

    if not isinstance(data, dict):
        raise RuntimeError("Invalid account status")

    if not data.get("email"):
        raise RuntimeError("Missing account email")

    if data.get("leftDays") is None:
        raise RuntimeError("Missing remaining days")

    try:
        remaining_days = int(float(data["leftDays"]))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid remaining days") from exc

    return remaining_days


def run_account(cookie, index):
    with requests.Session() as session:
        # Remove default requests headers so the explicitly
        # supplied headers determine the HTTP request.
        session.headers.clear()

        message = checkin(session, cookie)
        remaining_days = get_status(session, cookie)

    # Avoid exposing email addresses or cookies in Actions logs.
    print(f"Account {index}: {message}\nRemaining days: {remaining_days}")


def main():
    raw_cookies = os.environ.get("COOKIES", "").strip()

    if not raw_cookies:
        print("::error::COOKIES is not configured")
        return 1

    cookies = [cookie.strip() for cookie in raw_cookies.split("&&")]

    if any(not cookie for cookie in cookies):
        print("::error::COOKIES contains an empty entry")
        return 1

    failures = 0

    for index, cookie in enumerate(cookies, start=1):
        try:
            run_account(cookie, index)
        except Exception as exc:
            print(
                f"::error::Account {index} failed: {exc}",
                file=sys.stderr,
            )
            failures += 1

    if failures:
        print(f"{failures}/{len(cookies)} accounts failed")
        return 1

    print(f"All {len(cookies)} accounts checked in successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
