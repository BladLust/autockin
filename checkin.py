import json
import os
import sys

import requests

# 推送开关，填off不开启(默认)，填on同时开启cookie失效通知和签到成功通知
sever = os.environ["SERVE"]

# 填写pushplus的sckey,不开启推送则不用填
sckey = os.environ["SCKEY"]

# 填入glados账号对应cookie
COOKIES = os.environ["COOKIES"]
cookies = COOKIES.split("&&")


# GlaDOS签到
def checkin(cookie):
    checkin_url = "https://glados.cloud/api/user/checkin"
    state_url = "https://glados.cloud/api/user/status"
    referer = "https://glados.cloud/console/checkin"
    origin = "https://glados.cloud"
    useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.75 Safari/537.36"
    payload = {"token": "glados.cloud"}
    try:
        checkin = requests.post(
            checkin_url,
            headers={
                "cookie": cookie,
                "referer": referer,
                "origin": origin,
                "user-agent": useragent,
                "content-type": "application/json;charset=UTF-8",
            },
            data=json.dumps(payload),
        )
        state = requests.get(
            state_url,
            headers={
                "cookie": cookie,
                "referer": referer,
                "origin": origin,
                "user-agent": useragent,
            },
        )
    except Exception as e:
        print(f"签到失败，请检查网络：{e}")
        return None, None, None

    try:
        mess = checkin.json()["message"]
        mail = state.json()["data"]["email"]
        time = state.json()["data"]["leftDays"].split(".")[0]
    except Exception as e:
        print(f"解析登录结果失败：{e}")
        sys.exit(1)
        return None, None, None

    return mess, time, mail


def start():
    contents = []
    for cookie in cookies:
        ret, remain, email = checkin(cookie)
        if not ret:
            continue

        content = f"账号：{email}\n签到结果：{ret}\n剩余天数：{remain}\n"
        print(content)
        contents.append(content)

    contents_str = "".join(contents)
    return contents_str


def main_handler(event, context):
    return start()


if __name__ == "__main__":
    start()
