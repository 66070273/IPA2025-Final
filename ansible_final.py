# -*- coding: utf-8 -*-
"""
Run Ansible playbook to save running-config into
  show_run_[studentID]_[router_name].txt
Return: (ok: bool, filepath: str|None, router_name: str|None)
"""

import os, subprocess, json, tempfile, pathlib

ROUTER_USERNAME = os.getenv("ROUTER_USERNAME", "admin")
ROUTER_PASSWORD = os.getenv("ROUTER_PASSWORD", "cisco")

PLAYBOOK = "playbook_showrun.yml"   # ต้องอยู่ในโฟลเดอร์เดียวกัน
INVENTORY = "hosts"                 # ใช้ host: target

def run_showrun(router_ip: str, student_id: str):
    env = os.environ.copy()
    env["ANSIBLE_HOST_KEY_CHECKING"] = "False"

    extra = {
        "router_ip": router_ip,
        "router_username": ROUTER_USERNAME,
        "router_password": ROUTER_PASSWORD,
        "student_id": student_id,
    }
    cmd = [
        "ansible-playbook", "-i", INVENTORY, PLAYBOOK,
        "--extra-vars", json.dumps(extra),
    ]

    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    except Exception as e:
        return False, None, None

    if proc.returncode != 0:
        return False, None, None

    # playbook จะบอก path กับ hostname ออกมาในไฟล์ sentinel .json
    sentinel = pathlib.Path(".ansible_showrun_result.json")
    if not sentinel.exists():
        return False, None, None
    data = json.loads(sentinel.read_text(encoding="utf-8"))
    filepath = data.get("filepath")
    router_name = data.get("router_name")
    if not filepath or not os.path.exists(filepath):
        return False, None, None
    return True, filepath, router_name
