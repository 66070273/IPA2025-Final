from netmiko import ConnectHandler
from pprint import pprint

device_ip = "10.0.15.65"
username = "admin"
password = "cisco"

device_params = {
    "device_type": "cisco_ios",
    "ip": device_ip,
    "username": username,
    "password": password,
    "port": 22,
    "timeout": 30,
    "banner_timeout": 30,
    "auth_timeout": 30,
    "conn_timeout": 30,
}

def gigabit_status():
    with ConnectHandler(**device_params) as ssh:
        up = down = admin_down = 0
        result = ssh.send_command("show ip interface brief", use_textfsm=True)

        gig = []  # เก็บ (iface, status)

        if isinstance(result, list) and result and isinstance(result[0], dict):
            for row in result:
                iface = row.get("intf") or row.get("interface")
                if iface and iface.startswith("GigabitEthernet"):
                    s = row.get("status", "").strip().lower()
                    gig.append((iface, s))
                    if s == "up":
                        up += 1
                    elif s == "down":
                        down += 1
                    elif s == "administratively down":
                        admin_down += 1
        else:
            raw = ssh.send_command("show ip interface brief", use_textfsm=False)
            for line in raw.splitlines():
                line = line.strip()
                if not line.startswith("GigabitEthernet"):
                    continue
                parts = line.split()
                if len(parts) < 6:
                    continue
                iface = parts[0]
                s = " ".join(parts[4:-1]).lower()
                gig.append((iface, s))
                if s == "up":
                    up += 1
                elif s == "down":
                    down += 1
                elif s == "administratively down":
                    admin_down += 1

        want = [f"GigabitEthernet{i}" for i in range(1, 5)]
        present = {i: s for i, s in gig}
        ordered = [(ifn, present.get(ifn, "unknown")) for ifn in want]

        detail = ", ".join(f"{i} {s}" for i, s in ordered)
        summary = f"-> {up} up, {down} down, {admin_down} administratively down"
        ans = f"{detail} {summary}"
        pprint(ans)
        return ans
