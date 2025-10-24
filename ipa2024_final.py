#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IPA2025 Final – Part 1 (update on top of IPA2024)
Single main file:
- เลือก method ผ่านข้อความ: /<id> restconf | /<id> netconf
- สั่งงานจริง: /<id> <router_ip> <command>
- ถ้าไม่ระบุ method -> "Error: No method specified"
- ถ้าไม่ระบุ IP     -> "Error: No IP specified"
- Commands: create | delete | enable | disable | status
- ส่งข้อความตอบกลับในห้อง Webex เดิม

ENV (ใช้ .env ได้):
  WEBEX_ACCESS_TOKEN=...
  WEBEX_ROOM_ID=...
  STUDENT_ID=66070273
"""

import os
import time
import logging
from typing import Dict, Set, Optional

import requests
from dotenv import load_dotenv

# ใช้ import แบบทั้งโมดูล เพื่อไม่ผูกกับชื่อฟังก์ชันย่อยผิดพลาด
import restconf_final as restconf
import netconf_final as netconf

# ----------------- ENV & logging -----------------
load_dotenv()
WEBEX_TOKEN   = os.getenv("WEBEX_ACCESS_TOKEN", "").strip()
WEBEX_ROOM_ID = os.getenv("WEBEX_ROOM_ID", "").strip()
STUDENT_ID    = os.getenv("STUDENT_ID", "").strip()

if not WEBEX_TOKEN or not WEBEX_ROOM_ID or not STUDENT_ID:
    raise SystemExit("Missing env: WEBEX_ACCESS_TOKEN / WEBEX_ROOM_ID / STUDENT_ID")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE = "https://webexapis.com/v1"
HEADERS = {"Authorization": f"Bearer {WEBEX_TOKEN}"}
SEEN_IDS: Set[str] = set()

# จดจำ method ต่อ user id (/6607xxxx restconf|netconf)
method_state: Dict[str, Optional[str]] = {}

VALID_COMMANDS = {"create", "delete", "enable", "disable", "status"}

# ----------------- Webex helpers -----------------
def me_id() -> str:
    r = requests.get(f"{BASE}/people/me", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()["id"]

ME_PERSON_ID = me_id()

def send_message(text: str) -> None:
    try:
        requests.post(f"{BASE}/messages", headers=HEADERS,
                      json={"roomId": WEBEX_ROOM_ID, "text": text},
                      timeout=20).raise_for_status()
        logging.info("Sent: %s", text)
    except Exception as e:
        logging.error("Send failed: %s", e)

def list_messages(limit: int = 30):
    r = requests.get(f"{BASE}/messages", headers=HEADERS,
                     params={"roomId": WEBEX_ROOM_ID, "max": limit},
                     timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])

# ----------------- Parse helpers -----------------
def parse_text(text: str):
    """
    รูปแบบที่รองรับ:
      /<id> restconf
      /<id> netconf
      /<id> <ip> <command>

    return dict:
      {student_id, method_select, router_ip, command}
    """
    if not text:
        return {}

    parts = text.strip().split()
    if not parts or not parts[0].startswith("/"):
        return {}

    student_id = parts[0][1:]
    res = {
        "student_id": student_id,
        "method_select": None,
        "router_ip": None,
        "command": None
    }

    # method select
    if len(parts) == 2 and parts[1].lower() in ("restconf", "netconf"):
        res["method_select"] = parts[1].lower()
        return res

    # /id <ip> <command>
    if len(parts) >= 2 and parts[1].count(".") == 3:
        res["router_ip"] = parts[1]
        if len(parts) >= 3:
            res["command"] = parts[2].lower()
        return res

    # อื่นๆ ไม่แมตช์
    return res

def is_my_id(sid: str) -> bool:
    return sid == STUDENT_ID

# ----------------- Message Formatting -----------------
def fmt_success(cmd: str, sid: str, method: str) -> str:
    iface = f"Interface loopback {sid}"
    m = "Restconf" if method == "restconf" else "Netconf"
    if cmd == "create":
        return f"{iface} is created successfully using {m}"
    if cmd == "delete":
        return f"{iface} is deleted successfully using {m}"
    if cmd == "enable":
        return f"{iface} is enabled successfully using {m}"
    if cmd == "disable":
        return f"{iface} is shutdowned successfully using {m}"
    return f"Ok: {m}"

def fmt_cannot(cmd: str, sid: str) -> str:
    iface = f"Interface loopback {sid}"
    if cmd == "create":
        return f"Cannot create: {iface}"
    if cmd == "delete":
        return f"Cannot delete: {iface}"
    if cmd == "enable":
        return f"Cannot enable: {iface}"
    if cmd == "disable":
        return f"Cannot shutdown: {iface}"
    return "Cannot process"

def fmt_status(raw: str, sid: str, method: str) -> str:
    base = "(checked by Restconf)" if method == "restconf" else "(checked by Netconf)"
    low = (raw or "").lower()

    if any(k in low for k in ["no interface", "not found", "absent"]):
        return f"No Interface loopback {sid} {base}"
    if "enabled" in low or "up" in low:
        return f"Interface loopback {sid} is enabled {base}"
    if any(k in low for k in ["disabled", "shutdown", "down"]):
        return f"Interface loopback {sid} is disabled {base}"
    return f"Interface loopback {sid} is {raw} {base}"

def interpret(cmd: str, sid: str, method: str, raw: str) -> str:
    if cmd == "status":
        return fmt_status(raw, sid, method)

    low = (raw or "").lower()
    cannot_markers = ["already exists", "cannot", "not found", "absent",
                      "does not exist", "error", "failed"]
    if any(k in low for k in cannot_markers):
        return fmt_cannot(cmd, sid)

    # assume success
    return fmt_success(cmd, sid, method)

# ----------------- Dispatch -----------------
def do_restconf(cmd: str, ip: str, sid: str) -> str:
    try:
        if cmd == "create":
            raw = restconf.create(ip, sid)
        elif cmd == "delete":
            raw = restconf.delete(ip, sid)
        elif cmd == "enable":
            raw = restconf.enable(ip, sid)
        elif cmd == "disable":
            raw = restconf.disable(ip, sid)
        elif cmd == "status":
            raw = restconf.status(ip, sid)
        else:
            return "Error: No command found."
        return interpret(cmd, sid, "restconf", raw)
    except Exception as e:
        logging.exception("RESTCONF %s failed: %s", cmd, e)
        return f"Error: {e}"

def do_netconf(cmd: str, ip: str, sid: str) -> str:
    try:
        if cmd == "create":
            raw = netconf.create(ip, sid)
        elif cmd == "delete":
            raw = netconf.delete(ip, sid)
        elif cmd == "enable":
            raw = netconf.enable(ip, sid)
        elif cmd == "disable":
            raw = netconf.disable(ip, sid)
        elif cmd == "status":
            raw = netconf.status(ip, sid)
        else:
            return "Error: No command found."
        return interpret(cmd, sid, "netconf", raw)
    except Exception as e:
        logging.exception("NETCONF %s failed: %s", cmd, e)
        return f"Error: {e}"

# ----------------- Core handler -----------------
def handle_text(text: str) -> None:
    p = parse_text(text)
    if not p or "student_id" not in p:
        return

    sid = p["student_id"]
    if not is_my_id(sid):
        return

    # set method
    if p["method_select"]:
        method_state[sid] = p["method_select"]
        send_message(f"Ok: {p['method_select'].capitalize()}")
        return

    # require method first
    if method_state.get(sid) is None:
        send_message("Error: No method specified")
        return

    # require IP
    ip = p.get("router_ip")
    if not ip:
        send_message("Error: No IP specified")
        return

    # require command
    cmd = p.get("command")
    if not cmd or cmd not in VALID_COMMANDS:
        send_message("Error: No command found.")
        return

    # dispatch
    method = method_state[sid]
    if method == "restconf":
        send_message(do_restconf(cmd, ip, sid))
    elif method == "netconf":
        send_message(do_netconf(cmd, ip, sid))
    else:
        send_message("Error: No method specified")

# ----------------- Main loop -----------------
def main():
    logging.info("IPA2025 Part1 bot running | Room=%s | StudentID=%s", WEBEX_ROOM_ID, STUDENT_ID)
    while True:
        try:
            items = list_messages(limit=30)
            for m in reversed(items):
                mid = m.get("id")
                if mid in SEEN_IDS:
                    continue
                SEEN_IDS.add(mid)

                # skip my own
                if m.get("personId") == ME_PERSON_ID:
                    continue

                text = (m.get("text") or "").strip()
                if not text:
                    continue

                if text.startswith(f"/{STUDENT_ID}"):
                    logging.info("Recv: %s", text)
                    handle_text(text)
        except Exception as e:
            logging.exception("loop error: %s", e)
        time.sleep(3)

if __name__ == "__main__":
    main()
