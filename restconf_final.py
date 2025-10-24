# -*- coding: utf-8 -*-
import os, json, requests
from requests.auth import HTTPBasicAuth

USERNAME = os.getenv("ROUTER_USERNAME", "admin")
PASSWORD = os.getenv("ROUTER_PASSWORD", "cisco")

requests.packages.urllib3.disable_warnings()

HEADERS = {
    "Content-Type": "application/yang-data+json",
    "Accept": "application/yang-data+json",
}

def _base(ip): return f"https://{ip}/restconf/data"
def _ifname(sid): return f"Loopback{sid}"

def _mask(prefix: int) -> str:
    bits = (0xffffffff >> (32 - prefix)) << (32 - prefix)
    return ".".join(str((bits >> (24 - 8*i)) & 0xff) for i in range(4))

def _sid_ip(sid: str):
    last3 = sid[-3:]
    x = int(last3[0]); y = int(last3[1:])
    return f"172.{x}.{y}.1", 24

def create(router_ip: str, sid: str):
    name = _ifname(sid)
    ip, pfx = _sid_ip(sid)
    url_if = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"

    # pre-check
    r_chk = requests.get(url_if, headers=HEADERS,
                         auth=HTTPBasicAuth(USERNAME, PASSWORD),
                         verify=False, timeout=15)
    if r_chk.status_code == 200:
        return "already exists"

    payload = {
        "ietf-interfaces:interface": {
            "name": name,
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {"address": [{"ip": ip, "netmask": _mask(pfx)}]}
        }
    }
    r = requests.put(url_if, headers=HEADERS,
                     auth=HTTPBasicAuth(USERNAME, PASSWORD),
                     data=json.dumps(payload), verify=False, timeout=20)
    if r.status_code in (200, 201, 204): return "created"
    if r.status_code == 409:             return "already exists"
    if r.status_code == 404:             return "not found"
    return f"error {r.status_code} {r.text}"

def delete(router_ip: str, sid: str):
    name = _ifname(sid)
    url = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"
    r = requests.delete(url, headers=HEADERS,
                        auth=HTTPBasicAuth(USERNAME, PASSWORD),
                        verify=False, timeout=20)
    if r.status_code in (200, 204): return "deleted"
    if r.status_code == 404:        return "not found"
    return f"error {r.status_code} {r.text}"

def enable(router_ip: str, sid: str):
    name = _ifname(sid)
    url = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"
    payload = {"ietf-interfaces:interface": {"enabled": True}}
    r = requests.patch(url, headers=HEADERS,
                       auth=HTTPBasicAuth(USERNAME, PASSWORD),
                       data=json.dumps(payload), verify=False, timeout=20)
    if r.status_code in (200, 204): return "enabled"
    if r.status_code == 404:        return "not found"
    return f"error {r.status_code} {r.text}"

def disable(router_ip: str, sid: str):
    name = _ifname(sid)
    url = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"
    payload = {"ietf-interfaces:interface": {"enabled": False}}
    r = requests.patch(url, headers=HEADERS,
                       auth=HTTPBasicAuth(USERNAME, PASSWORD),
                       data=json.dumps(payload), verify=False, timeout=20)
    if r.status_code in (200, 204): return "shutdowned"
    if r.status_code == 404:        return "not found"
    return f"error {r.status_code} {r.text}"

def status(router_ip: str, sid: str):
    name = _ifname(sid)
    url = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"
    r = requests.get(url, headers=HEADERS,
                     auth=HTTPBasicAuth(USERNAME, PASSWORD),
                     verify=False, timeout=20)
    if r.status_code == 404: return "no interface"
    if r.status_code != 200: return f"error {r.status_code} {r.text}"
    data = r.json().get("ietf-interfaces:interface", {})
    en = data.get("enabled", False)
    return "enabled" if en else "disabled"
