import os, subprocess, json, tempfile, pathlib

ROUTER_USERNAME = os.getenv("ROUTER_USERNAME", "admin")
ROUTER_PASSWORD = os.getenv("ROUTER_PASSWORD", "cisco")

PLAYBOOK = "playbook_showrun.yml"  
INVENTORY = "hosts"              

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

    sentinel = pathlib.Path(".ansible_showrun_result.json")
    if not sentinel.exists():
        return False, None, None
    data = json.loads(sentinel.read_text(encoding="utf-8"))
    filepath = data.get("filepath")
    router_name = data.get("router_name")
    if not filepath or not os.path.exists(filepath):
        return False, None, None
    return True, filepath, router_name

def run_set_motd(router_ip: str, motd_text: str) -> bool:
    """
    เรียก ansible เพื่อ set MOTD (banner motd)
    คืน True ถ้าสำเร็จ
    """
    import json, os, subprocess
    env = os.environ.copy()
    env["ANSIBLE_HOST_KEY_CHECKING"] = "False"

    extra = {
        "router_ip": router_ip,
        "router_username": os.getenv("ROUTER_USERNAME", "admin"),
        "router_password": os.getenv("ROUTER_PASSWORD", "cisco"),
        "motd_text": motd_text,
    }
    cmd = ["ansible-playbook", "-i", "hosts", "playbook_motd.yml", "--extra-vars", json.dumps(extra)]
    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
        return r.returncode == 0
    except Exception:
        return False
