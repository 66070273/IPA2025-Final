#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IPA2025 Part 1 (update on top of IPA2024)
- เลือก method: /<id> restconf | /<id> netconf
- สั่งงานจริง: /<id> <ip> <command>
- Commands: create | delete | enable | disable | status
- IP อนุญาต: 10.0.15.61–65
- อ่านทุกข้อความในห้อง (รองรับข้อความที่แก้ไข)

ENV (.env):
  WEBEX_BOT_TOKEN=...     # ไม่ต้องมีคำว่า Bearer
  WEBEX_ROOM_ID=...
  STUDENT_ID=6607xxxx
  ROUTER_USERNAME=admin
  ROUTER_PASSWORD=cisco
"""

import os
import time
import logging
from typing import Dict, Set, Optional

import requests
from dotenv import load_dotenv

import restconf_final as restconf
import netconf_final as netconf

# ===== Config =====
ALLOWED_IPS = {f"10.0.15.{i}" for i in range(61, 66)}   # 61–65
VALID_COMMANDS = {"create", "delete", "enable", "disable", "status"}
method_state: Dict[str, Optional[str]] = {}             # จำ method ต่อ student id

# ===== ENV & logging =====
load_dotenv()
WEBEX_TOKEN   = os.getenv("WEBEX_BOT_TOKEN", "").strip()
WEBEX_ROOM_ID = os.getenv("WEBEX_ROOM_ID", "").strip()
STUDENT_ID    = os.getenv("STUDENT_ID", "").strip()

if not WEBEX_TOKEN or not WEBEX_ROOM_ID or not STUDENT_ID:
    raise SystemExit("Missing env: WEBEX_BOT_TOKEN / WEBEX_ROOM_ID / STUDENT_ID")

BASE = "https://webexapis.com/v1"
HEADERS = {"Authorization": f"Bearer {WEBEX_TOKEN}"}
SEEN_IDS: Set[str] = set()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ===== Webex helpers =====
def send_message(text: str) -> None:
    try:
        requests.post(
            f"{BASE}/messages",
            headers=HEADERS,
            json={"roomId": WEBEX_ROOM_ID, "text": text},
            timeout=20,
        ).raise_for_status()
    except Exception as e:
        logging.error("Send failed: %s", e)

def list_messages(limit: int = 50):
    r = requests.get(
        f"{BASE}/messages",
        headers=HEADERS,
        params={"roomId": WEBEX_ROOM_ID, "max": limit},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("items", [])

# ===== Parser =====
def parse_text(text: str):
    """
    รองรับ:
      /<id> restconf
      /<id> netconf
      /<id> <ip> <command>
    """
    if not text:
        return {}
    parts = text.strip().split()
    if not parts or not parts[0].startswith("/"):
        return {}
    student_id = parts[0][1:]

    out = {"student_id": student_id, "method_select": None, "router_ip": None, "command": None}

    # เลือกวิธี
    if len(parts) == 2 and parts[1].lower() in ("restconf", "netconf"):
        out["method_select"] = parts[1].lower()
        return out

    # /id <ip> <command>
    if len(parts) >= 2 and parts[1].count(".") == 3:
        out["router_ip"] = parts[1]
        if len(parts) >= 3:
            out["command"] = parts[2].lower()
        return out

    return out

# ===== Message formatting =====
def _iface(sid): return f"Interface loopback {sid}"
def _checked(method): return "(checked by Restconf)" if method == "restconf" else "(checked by Netconf)"

def fmt_success(cmd: str, sid: str, method: str) -> str:
    m = "Restconf" if method == "restconf" else "Netconf"
    if cmd == "create":  return f"{_iface(sid)} is created successfully using {m}"
    if cmd == "delete":  return f"{_iface(sid)} is deleted successfully using {m}"
    if cmd == "enable":  return f"{_iface(sid)} is enabled successfully using {m}"
    if cmd == "disable": return f"{_iface(sid)} is shutdowned successfully using {m}"
    return f"Ok: {m}"

def fmt_status(raw: str, sid: str, method: str) -> str:
    low = (raw or "").lower()
    if any(k in low for k in ["no interface", "not found", "absent"]):
        return f"No Interface loopback {sid} {_checked(method)}"
    if "enabled" in low or "up" in low:
        return f"{_iface(sid)} is enabled {_checked(method)}"
    if any(k in low for k in ["disabled", "shutdown", "down"]):
        return f"{_iface(sid)} is disabled {_checked(method)}"
    return f"{_iface(sid)} is {raw} {_checked(method)}"

def interpret(cmd: str, sid: str, method: str, raw: str) -> str:
    if cmd == "status":
        return fmt_status(raw, sid, method)

    low = (raw or "").lower()
    cannot = {
        "create":  f"Cannot create: {_iface(sid)}",
        "delete":  f"Cannot delete: {_iface(sid)}",
        "enable":  f"Cannot enable: {_iface(sid)}",
        "disable": f"Cannot shutdown: {_iface(sid)}",
    }[cmd]

    # trigger cannot
    if any(k in low for k in ["already exists", "cannot", "not found", "absent", "does not exist", "error", "failed"]):
        # ตัวอย่างต้องการ: disable fail → เติม checked
        if cmd == "disable" and any(k in low for k in ["not found", "no interface", "absent"]):
            return f"{cannot} {_checked(method)}"
        return cannot

    # success (default)
    return fmt_success(cmd, sid, method)

# ===== Dispatch =====
def do_restconf(cmd: str, ip: str, sid: str) -> str:
    try:
        if   cmd == "create":  raw = restconf.create(ip, sid)
        elif cmd == "delete":  raw = restconf.delete(ip, sid)
        elif cmd == "enable":  raw = restconf.enable(ip, sid)
        elif cmd == "disable": raw = restconf.disable(ip, sid)
        elif cmd == "status":  raw = restconf.status(ip, sid)
        else: return "Error: No command found."
        return interpret(cmd, sid, "restconf", raw)
    except Exception as e:
        return f"Error: {e}"

def do_netconf(cmd: str, ip: str, sid: str) -> str:
    try:
        if   cmd == "create":  raw = netconf.create(ip, sid)
        elif cmd == "delete":  raw = netconf.delete(ip, sid)
        elif cmd == "enable":  raw = netconf.enable(ip, sid)
        elif cmd == "disable": raw = netconf.disable(ip, sid)
        elif cmd == "status":  raw = netconf.status(ip, sid)
        else: return "Error: No command found."
        return interpret(cmd, sid, "netconf", raw)
    except Exception as e:
        return f"Error: {e}"

# ===== Core handler =====
def handle_text(text: str) -> None:
    p = parse_text(text)
    if not p or "student_id" not in p:
        return

    sid = p["student_id"]

    # ✅ ตอบเฉพาะของเราเท่านั้น
    if sid != STUDENT_ID:
        return

    # /<sid> restconf|netconf
    if p["method_select"]:
        method_state[sid] = p["method_select"]
        send_message(f"Ok: {p['method_select'].capitalize()}")
        return

    # ยังไม่เลือก method
    if method_state.get(sid) is None:
        send_message("Error: No method specified")
        return

    # ยังไม่ใส่ IP
    ip = p.get("router_ip")
    if not ip:
        send_message("Error: No IP specified")
        return

    # IP ต้องอยู่ใน 10.0.15.61–65
    if ip not in ALLOWED_IPS:
        send_message("Error: No IP specified")
        return

    # ยังไม่ใส่คำสั่ง
    cmd = p.get("command")
    if not cmd:
        send_message("Error: No command found.")
        return

    if cmd not in VALID_COMMANDS:
        send_message("Error: No command found.")
        return

    method = method_state[sid]
    if method == "restconf":
        send_message(do_restconf(cmd, ip, sid))
    elif method == "netconf":
        send_message(do_netconf(cmd, ip, sid))
    else:
        send_message("Error: No method specified")


# ===== Main loop (อ่านทุกข้อความ + รองรับข้อความถูกแก้ไข) =====
def main():
    logging.info("IPA2025 Part1 bot running | Room=%s | StudentID=%s", WEBEX_ROOM_ID, STUDENT_ID)
    while True:
        try:
            items = list_messages(limit=50)
            for m in reversed(items):
                mid = m.get("id")
                upd = m.get("updated") or ""     # ถ้าแก้ไขข้อความจะมีค่านี้
                key = f"{mid}:{upd}"
                if key in SEEN_IDS:
                    continue
                SEEN_IDS.add(key)

                text = (m.get("text") or "").strip() or (m.get("markdown") or "").strip()
                if not text:
                    continue

                handle_text(text)

        except Exception as e:
            logging.exception("loop error: %s", e)
        time.sleep(3)

if __name__ == "__main__":
    main()
