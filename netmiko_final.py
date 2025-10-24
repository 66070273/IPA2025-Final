# -*- coding: utf-8 -*-
"""
Netmiko helpers
- showrun(): คืน running-config
- gigabit_status(): สรุปสถานะพอร์ต GigabitEthernet ทั้งหมดแบบ:
  Gi1 up, Gi2 administratively down, ... -> X up, Y down, Z administratively down
"""

import os, re
from netmiko import ConnectHandler

USERNAME = os.getenv("ROUTER_USERNAME", "admin")
PASSWORD = os.getenv("ROUTER_PASSWORD", "cisco")
NET_TEMPLATES = os.getenv("NET_TEXTFSM")  # ถ้ามี ntc-templates ใส่ path ไว้ จะ parse สวยขึ้น

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
        # 1) ยิงแบบ include เพื่อลด noise ก่อน
        raw = conn.send_command("show ip interface brief | include GigabitEthernet",
                                use_textfsm=False, delay_factor=1.0)
        if not raw.strip():
            # 2) fallback: ดึงทั้งก้อน
            raw = conn.send_command("show ip interface brief",
                                    use_textfsm=False, delay_factor=1.0)

    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        # จับเฉพาะบรรทัดที่พูดถึง Gi*
        if ("GigabitEthernet" in s) or re.match(r"^Gi[\d/]+", s):
            lines.append(s)

    if not lines:
        # สุดท้ายจริงๆ ลองใช้ show interfaces status
        with _connect(ip) as conn:
            raw2 = conn.send_command("show interfaces status | include Gi|Gigabit",
                                     use_textfsm=False, delay_factor=1.0)
        for line in raw2.splitlines():
            s = line.strip()
            if s.startswith(("Gi", "Gigabit")):
                # show interfaces status ไม่มีคำว่า "administratively down"
                # ส่วนใหญ่จะเป็น connected / notconnect / disabled
                parts = s.split()
                if parts:
                    ifname = parts[0]
                    stat_l = " ".join(parts[1:]).lower()
                    # map คร่าว ๆ
                    if "connected" in stat_l:
                        status = "up"
                    elif "disabled" in stat_l or "err-disabled" in stat_l:
                        status = "administratively down"
                    else:
                        status = "down"
                    lines.append(f"{ifname} - - - {status} -")  # ให้ parser ด้านล่างอ่านได้

    if not lines:
        return "No GigabitEthernet found"

    # parse เป็น (ifname, status)
    items = []
    for s in lines:
        # รูปแบบมาตรฐาน: IF IP OK? Method Status Protocol
        # status อาจเป็นสองคำ (administratively down)
        parts = s.split()
        if len(parts) < 5:
            # พยายามดึงชื่อ iface
            m = re.match(r"^(GigabitEthernet[\d/]+|Gi[\d/]+)", s)
            ifname = m.group(1) if m else parts[0]
            items.append((ifname, "down"))
            continue

        ifname = parts[0]
        # status = join คอลัมน์ก่อนสุดท้ายทั้งหมด
        status = " ".join(parts[4:-1]).strip().lower() if len(parts) > 5 else parts[4].lower()

        # normalize
        if "administratively down" in status:
            st = "administratively down"
        elif "up" in status:
            st = "up"
        else:
            st = "down"

        items.append((ifname, st))

    # สรุปผล
    pieces, up, down, admin = [], 0, 0, 0
    # เรียงชื่อให้สวย (Gi1, Gi2, … ก่อน)
    def _key(t):  # ('GigabitEthernet1/0/1', 'up') -> tuple of ints
        import re
        nums = re.findall(r"\d+", t[0])
        return tuple(int(n) for n in nums) if nums else (9999,)
    items.sort(key=_key)

    for ifname, st in items:
        # ใช้ชื่อเต็ม GigabitEthernet... เพื่อความชัดเจน
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
            # fallback raw, parse แบบง่าย
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

    # คัดเฉพาะ GigabitEthernet*
    gi = [r for r in rows if str(r.get("intf","")).lower().startswith(("gigabit", "gi"))]
    if not gi:
        return "No GigabitEthernet found"

    # รวบรวมสถานะ
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
