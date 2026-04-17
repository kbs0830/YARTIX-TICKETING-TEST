import argparse
import json
import random
import string
import time
from datetime import date, timedelta
from urllib import request, error

FIXED_TEST_EMAIL = "1394kbs@gmail.com"

LAST_NAMES = [
    "LIN", "CHEN", "WANG", "LI", "CHANG", "HSU", "YU", "HUANG", "TSENG", "HSIAO"
]
FIRST_NAMES = [
    "MING", "YU", "TING", "JIA", "WEI", "HAO", "XIN", "AN", "KAI", "NINA"
]


def http_json(method, url, payload=None, timeout=20):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text)
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"ok": False, "message": body}


def random_dob():
    start = date(1950, 1, 1)
    end = date(2008, 12, 31)
    days = (end - start).days
    d = start + timedelta(days=random.randint(0, days))
    return d.isoformat()


def random_id_number(gender):
    letter = random.choice(string.ascii_uppercase)
    second = "1" if gender == "男" else "2"
    tail = "".join(random.choice(string.digits) for _ in range(8))
    return f"{letter}{second}{tail}"


def random_phone():
    return "09" + "".join(random.choice(string.digits) for _ in range(8))


def random_name():
    return f"{random.choice(LAST_NAMES)} {random.choice(FIRST_NAMES)}"


def build_participant(ticket_types, food_types, addons):
    gender = random.choice(["男", "女"])
    addon_payload = {}
    for key in addons:
        addon_payload[key] = random.randint(0, 2)

    return {
        "name": random_name(),
        "gender": gender,
        "dob": random_dob(),
        "id_number": random_id_number(gender),
        "phone": random_phone(),
        "email": FIXED_TEST_EMAIL,
        "ticket_type": random.choice(ticket_types),
        "food_types": random.choice(food_types),
        "bank_name": "",
        "bank_last4": "",
        "note": "",
        "addons": addon_payload,
    }


def run_once(base_url, min_count, max_count):
    status, boot = http_json("GET", f"{base_url}/api/bootstrap")
    if status != 200 or not boot.get("ok"):
        raise RuntimeError(f"bootstrap failed: {boot}")

    ticket_types = list((boot.get("ticket_types") or {}).keys())
    food_types = list(boot.get("food_types") or [])
    addons = boot.get("addons") or {}

    if not ticket_types or not food_types:
        raise RuntimeError("bootstrap 缺少票種或飲食設定")

    count = random.randint(min_count, max_count)
    participants = [build_participant(ticket_types, food_types, addons) for _ in range(count)]

    status, result = http_json("POST", f"{base_url}/api/register", {"participants": participants})
    return status, result, participants


def main():
    parser = argparse.ArgumentParser(description="Yartix 自動隨機報名測試機器人")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="後端 API 位址")
    parser.add_argument("--rounds", type=int, default=1, help="執行回合數")
    parser.add_argument("--min-participants", type=int, default=1, help="每回合最少人數")
    parser.add_argument("--max-participants", type=int, default=3, help="每回合最多人數")
    parser.add_argument("--sleep", type=float, default=0.5, help="每回合間隔秒數")
    args = parser.parse_args()

    if args.rounds < 1:
        raise SystemExit("--rounds 必須 >= 1")
    if args.min_participants < 1 or args.max_participants < args.min_participants:
        raise SystemExit("人數參數不合法")

    print("=== Yartix Test Bot ===")
    print(f"base_url: {args.base_url}")
    print(f"fixed email (forced): {FIXED_TEST_EMAIL}")

    success = 0
    for i in range(1, args.rounds + 1):
        status, result, participants = run_once(args.base_url, args.min_participants, args.max_participants)
        ok = status == 200 and result.get("ok") is True

        print(f"\n[round {i}] status={status} ok={ok}")
        print(f"participants={len(participants)}")

        if ok:
            success += 1
            serials = [str(x.get("報名序號", "")) for x in result.get("data", [])]
            print("serials:", ", ".join(serials) if serials else "(none)")
            print("total_amount:", result.get("total_amount"))
            print("email_sent:", result.get("email_sent"))
        else:
            print("error:", result.get("message", result))

        if i < args.rounds:
            time.sleep(max(0.0, args.sleep))

    print(f"\nDone. success={success}/{args.rounds}")


if __name__ == "__main__":
    main()
