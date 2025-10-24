#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time, logging, requests
from typing import Dict, Optional, Set
from dotenv import load_dotenv

import restconf_final as restconf
import netconf_final as netconf
import ansible_final as ansible_runner   # NEW

load_dotenv()

WEBEX_TOKEN   = os.getenv("WEBEX_BOT_TOKEN", "").strip()
WEBEX_ROOM_ID = os.getenv("WEBEX_ROOM_ID", "").strip()
STUDENT_ID    = os.getenv("STUDENT_ID", "").strip()
if not WEBEX_TOKEN or not WEBEX_ROOM_ID or not STUDENT_ID:
    raise SystemExit("Missing env: WEBEX_BOT_TOKEN / WEBEX_ROOM_ID / STUDENT_ID")

BASE = "https://webexapis.com/v1"
HEADERS = {"Authorization": f"Bearer {WEBEX_TOKEN}"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ALLOWED_IPS = {f"10.0.15.{i}" for i in range(61, 66)}
VALID_COMMANDS = {"create", "delete", "enable", "disable", "status", "showrun", "gigabit_status", "motd"}
method_state: Dict[str, Optional[str]] = {}
SEEN_IDS: Set[str] = set()

# ---------- Webex helpers ----------
def send_message(text: str) -> None:
    try:
        requests.post(f"{BASE}/messages", headers=HEADERS,
                      json={"roomId": WEBEX_ROOM_ID, "text": text}, timeout=20).raise_for_status()
    except Exception as e:
        logging.error("send_message: %s", e)

def send_long(text: str, chunk=3500):
    for i in range(0, len(text), chunk):
        send_message(text[i:i+chunk])

def send_file(filepath: str, caption: str = ""):
    try:
        with open(filepath, "rb") as f:
            files = {"files": (os.path.basename(filepath), f, "text/plain")}
            data = {"roomId": WEBEX_ROOM_ID, "text": caption} if caption else {"roomId": WEBEX_ROOM_ID}
            requests.post(f"{BASE}/messages", headers={"Authorization": f"Bearer {WEBEX_TOKEN}"},
                          files=files, data=data, timeout=60).raise_for_status()
    except Exception as e:
        logging.error("send_file: %s", e)
        send_message(f"Error: cannot upload file {os.path.basename(filepath)}")

def list_messages(limit=50):
    r = requests.get(f"{BASE}/messages", headers=HEADERS,
                     params={"roomId": WEBEX_ROOM_ID, "max": limit}, timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])

# ---------- Parser ----------
def parse_text(text: str):
    parts = (text or "").strip().split()
    if not parts or not parts[0].startswith("/"):
        return {}
    sid = parts[0][1:]
    out = {"student_id": sid, "method_select": None, "router_ip": None, "command": None}
    if len(parts) == 2 and parts[1].lower() in ("restconf", "netconf"):
        out["method_select"] = parts[1].lower()
        return out
    if len(parts) >= 2 and parts[1].count(".") == 3:
        out["router_ip"] = parts[1]
        if len(parts) >= 3:
            out["command"] = parts[2].lower()
    return out

# ---------- Format helpers ----------
def _iface(sid): return f"Interface loopback {sid}"
def _checked(m): return "(checked by Restconf)" if m == "restconf" else "(checked by Netconf)"
def fmt_success(cmd, sid, m):
    M = "Restconf" if m == "restconf" else "Netconf"
    if cmd == "create":  return f"{_iface(sid)} is created successfully using {M}"
    if cmd == "delete":  return f"{_iface(sid)} is deleted successfully using {M}"
    if cmd == "enable":  return f"{_iface(sid)} is enabled successfully using {M}"
    if cmd == "disable": return f"{_iface(sid)} is shutdowned successfully using {M}"
    return f"Ok: {M}"
def fmt_status(raw, sid, m):
    s = (raw or "").lower()
    if any(k in s for k in ["no interface", "not found", "absent"]):
        return f"No Interface loopback {sid} {_checked(m)}"
    if "enabled" in s or "up" in s:  return f"{_iface(sid)} is enabled {_checked(m)}"
    if any(k in s for k in ["disabled", "shutdown", "down"]):
        return f"{_iface(sid)} is disabled {_checked(m)}"
    return f"{_iface(sid)} is {raw} {_checked(m)}"
def interpret(cmd, sid, m, raw):
    if cmd == "status": return fmt_status(raw, sid, m)
    cannot = {"create":f"Cannot create: {_iface(sid)}","delete":f"Cannot delete: {_iface(sid)}",
              "enable":f"Cannot enable: {_iface(sid)}","disable":f"Cannot shutdown: {_iface(sid)}"}[cmd]
    s = (raw or "").lower()
    if any(k in s for k in ["already exists","cannot","not found","absent","does not exist","error","failed"]):
        if cmd == "disable" and any(k in s for k in ["not found","no interface","absent"]):
            return f"{cannot} {_checked(m)}"
        return cannot
    return fmt_success(cmd, sid, m)

# ---------- Dispatch ----------
def do_restconf(cmd, ip, sid):
    try:
        raw = {"create":restconf.create, "delete":restconf.delete, "enable":restconf.enable,
               "disable":restconf.disable, "status":restconf.status}[cmd](ip, sid)
        return interpret(cmd, sid, "restconf", raw)
    except Exception as e: return f"Error: {e}"

def do_netconf(cmd, ip, sid):
    try:
        raw = {"create":netconf.create, "delete":netconf.delete, "enable":netconf.enable,
               "disable":netconf.disable, "status":netconf.status}[cmd](ip, sid)
        return interpret(cmd, sid, "netconf", raw)
    except Exception as e: return f"Error: {e}"

# ---------- Core handler ----------
def handle_text(text: str) -> None:
    p = parse_text(text)
    if not p or "student_id" not in p:
        return
    sid = p["student_id"]
    if sid != STUDENT_ID:
        return  # ตอบเฉพาะของเรา

    ip = p.get("router_ip")
    cmd = p.get("command")

    # ----- ตรวจรูปแบบพื้นฐาน -----
    if not cmd:
        send_message("Error: No command found.")
        return
    if cmd not in VALID_COMMANDS:
        send_message("Error: No command found.")
        return
    if not ip:
        send_message("Error: No IP specified")
        return
    if ip not in ALLOWED_IPS:
        send_message("Error: No IP specified")
        return

    # ----- คำสั่ง Part 2: motd -----
    if cmd == "motd":
        # รูปแบบข้อความ: "/<sid> <ip> motd <ข้อความ...>"  (อาจไม่มีข้อความ)
        parts = text.strip().split(" ", 3)
        motd_msg = parts[3] if len(parts) == 4 else None

        if motd_msg:  # ตั้งค่า MOTD ด้วย Ansible
            try:
                ok = ansible_runner.run_set_motd(ip, motd_msg)
                send_message("Ok: success" if ok else "Error: Ansible")
            except Exception:
                send_message("Error: Ansible")
        else:        # อ่านค่า MOTD ด้วย Netmiko/TextFSM
            try:
                from netmiko_final import get_motd
                msg = get_motd(ip)
                send_message(msg if msg else "Error: No MOTD Configured")
            except Exception:
                send_message("Error: No MOTD Configured")
        return

    # ----- reporting cmds (เดิม) -----
    if cmd == "gigabit_status":
        try:
            from netmiko_final import gigabit_status
            msg = gigabit_status(ip)
            send_message(msg if len(msg) < 3500 else msg[:3500])
        except Exception as e:
            send_message(f"Error: {e}")
        return

    if cmd == "showrun":
        ok, filepath, router_name = ansible_runner.run_showrun(ip, STUDENT_ID)
        if ok and filepath:
            send_file(filepath, f"show_run_{STUDENT_ID}_{router_name}.txt")
        else:
            send_message("Error: Ansible")
        return

    # ----- Part1 (ต้องมี method) -----
    if method_state.get(sid) is None:
        send_message("Error: No method specified"); return

    method = method_state[sid]
    if method == "restconf":
        send_message(do_restconf(cmd, ip, sid))
    elif method == "netconf":
        send_message(do_netconf(cmd, ip, sid))
    else:
        send_message("Error: No method specified")

# ---------- Main loop ----------
def main():
    logging.info("Bot running | Room=%s | StudentID=%s", WEBEX_ROOM_ID, STUDENT_ID)
    while True:
        try:
            for m in reversed(list_messages(50)):
                key = f"{m.get('id')}:{m.get('updated') or ''}"
                if key in SEEN_IDS: continue
                SEEN_IDS.add(key)
                txt = (m.get("text") or "").strip() or (m.get("markdown") or "").strip()
                if not txt: continue
                handle_text(txt)
        except Exception as e:
            logging.exception("loop error: %s", e)
        time.sleep(3)

if __name__ == "__main__":
    main()
