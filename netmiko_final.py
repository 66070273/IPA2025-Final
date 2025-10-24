import os, re
from netmiko import ConnectHandler
from typing import Optional

USERNAME = os.getenv("ROUTER_USERNAME", "admin")
PASSWORD = os.getenv("ROUTER_PASSWORD", "cisco")
NET_TEMPLATES = os.getenv("NET_TEXTFSM")

def _connect(ip: str):
    dev = {
        "device_type": "cisco_ios",
        "host": ip,
        "username": USERNAME,
        "password": PASSWORD,
        "fast_cli": False,
    }
    return ConnectHandler(**dev)

def showrun(ip: str) -> str:
    with _connect(ip) as conn:
        out = conn.send_command("show running-config", use_textfsm=False, delay_factor=1.2)
    return out.strip()

def gigabit_status(ip: str) -> str:
    """
    สรุปสถานะ GigabitEthernet ทั้งหมดเป็นรูป:
    Gi1 up, Gi2 administratively down, ... -> X up, Y down, Z administratively down
    * อ่านอย่างเดียว ห้ามเปลี่ยนคอนฟิก (ตามข้อกำหนด)
    """
    import re
    with _connect(ip) as conn:
        raw = conn.send_command("show ip interface brief | include GigabitEthernet",
                                use_textfsm=False, delay_factor=1.0)
        if not raw.strip():
            raw = conn.send_command("show ip interface brief",
                                    use_textfsm=False, delay_factor=1.0)

    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if ("GigabitEthernet" in s) or re.match(r"^Gi[\d/]+", s):
            lines.append(s)

    if not lines:
        with _connect(ip) as conn:
            raw2 = conn.send_command("show interfaces status | include Gi|Gigabit",
                                     use_textfsm=False, delay_factor=1.0)
        for line in raw2.splitlines():
            s = line.strip()
            if s.startswith(("Gi", "Gigabit")):
                parts = s.split()
                if parts:
                    ifname = parts[0]
                    stat_l = " ".join(parts[1:]).lower()
                    if "connected" in stat_l:
                        status = "up"
                    elif "disabled" in stat_l or "err-disabled" in stat_l:
                        status = "administratively down"
                    else:
                        status = "down"
                    lines.append(f"{ifname} - - - {status} -")

    if not lines:
        return "No GigabitEthernet found"

    items = []
    for s in lines:
        parts = s.split()
        if len(parts) < 5:
            m = re.match(r"^(GigabitEthernet[\d/]+|Gi[\d/]+)", s)
            ifname = m.group(1) if m else parts[0]
            items.append((ifname, "down"))
            continue

        ifname = parts[0]
        status = " ".join(parts[4:-1]).strip().lower() if len(parts) > 5 else parts[4].lower()

        if "administratively down" in status:
            st = "administratively down"
        elif "up" in status:
            st = "up"
        else:
            st = "down"

        items.append((ifname, st))

    pieces, up, down, admin = [], 0, 0, 0
    def _key(t):
        import re
        nums = re.findall(r"\d+", t[0])
        return tuple(int(n) for n in nums) if nums else (9999,)
    items.sort(key=_key)

    for ifname, st in items:
        if ifname.startswith("Gi"):
            ifname = ifname.replace("Gi", "GigabitEthernet")
        if st == "up":
            up += 1; pieces.append(f"{ifname} up")
        elif st == "administratively down":
            admin += 1; pieces.append(f"{ifname} administratively down")
        else:
            down += 1; pieces.append(f"{ifname} down")

    return f"{', '.join(pieces)} -> {up} up, {down} down, {admin} administratively down"

    """
    ใช้ 'show ip interface brief' (use_textfsm=True ถ้ามี template)
    ตกแต่งผลลัพธ์ให้อยู่ในรูปแบบที่ระบุ
    """
    with _connect(ip) as conn:
        try:
            rows = conn.send_command("show ip interface brief", use_textfsm=True, delay_factor=1.0)
        except Exception:
            rows = None
        if not rows or isinstance(rows, str):
            raw = conn.send_command("show ip interface brief", use_textfsm=False, delay_factor=1.0)
            rows = []
            for line in raw.splitlines():
                if re.match(r"^(GigabitEthernet|Gi)\S+\s+", line.strip()):
                    parts = line.split()
                    if len(parts) >= 6:
                        rows.append({
                            "intf": parts[0],
                            "ipaddr": parts[1],
                            "status": " ".join(parts[4:-1]) if len(parts) > 5 else parts[4],
                            "protocol": parts[-1],
                        })

    gi = [r for r in rows if str(r.get("intf","")).lower().startswith(("gigabit", "gi"))]
    if not gi:
        return "No GigabitEthernet found"

    pieces = []
    up = down = admin = 0
    for r in gi:
        name = r.get("intf")
        status = str(r.get("status","")).lower()
        if "administratively down" in status:
            pieces.append(f"{name} administratively down"); admin += 1
        elif "up" in status:
            pieces.append(f"{name} up"); up += 1
        else:
            pieces.append(f"{name} down"); down += 1

    summary = f"{up} up, {down} down, {admin} administratively down"
    return f"{', '.join(pieces)} -> {summary}"

def get_motd(ip: str) -> Optional[str]:
    """
    อ่าน MOTD บนอุปกรณ์ IOS XE ให้พยายามวิธีที่เสถียรก่อน:
      1) 'show banner motd'  (ส่วนใหญ่จะพิมพ์ข้อความออกมาตรงๆ)
      2) fallback: 'show running-config | section banner motd'
         รองรับ delimiter ทุกตัว เช่น ^C, !, %, # และหลายบรรทัด
    คืนข้อความ MOTD ถ้าเจอ, ถ้าไม่พบให้คืน None
    """
    with _connect(ip) as conn:
        out1 = conn.send_command("show banner motd", use_textfsm=False, delay_factor=1.0)
        if out1 is not None:
            s = out1.strip()
            low = s.lower()
            if s and ("no such banner" not in low) and ("not set" not in low):
                return s

        out2 = conn.send_command("show running-config | section banner motd",
                                 use_textfsm=False, delay_factor=1.0)
        if out2 and "banner motd" in out2:
            m = re.search(r"banner\s+motd\s+(\S)\r?\n(.*?)\r?\n\1",
                          out2, re.DOTALL | re.IGNORECASE)
            if m:
                body = m.group(2).strip()
                if body:
                    return body

            m2 = re.search(r"banner\s+motd\s+(.)(.*?)(?:\r?\n\1|\1\r?\n)$",
                           out2, re.DOTALL | re.IGNORECASE)
            if m2:
                body = m2.group(2).strip()
                if body:
                    body = re.sub(r"^\s*[\^#!%/|].*\n", "", body).strip()
                    body = re.sub(r"\n\s*[\^#!%/|]\s*$", "", body).strip()
                    if body:
                        return body

    return None
