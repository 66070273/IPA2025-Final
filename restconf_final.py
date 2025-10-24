# -*- coding: utf-8 -*-
"""
RESTCONF operations for IOS XE using IETF interfaces model.
All functions must exist and match signatures used by ipa2024_final.py

create(router_ip, student_id, ip_addr, prefix)
delete(router_ip, student_id)
enable(router_ip, student_id)
disable(router_ip, student_id)
status(router_ip, student_id)

Auth: admin / cisco (do NOT hardcode in main; this is a placeholder commonly used for lab)
"""

import requests
from requests.auth import HTTPBasicAuth
import json

USERNAME = "admin"
PASSWORD = "cisco"

# IOS XE RESTCONF base
def _base(router_ip):
    return f"https://{router_ip}/restconf/data"

HEADERS = {
    "Content-Type": "application/yang-data+json",
    "Accept": "application/yang-data+json",
}

def _iface_name(student_id: str) -> str:
    return f"Loopback{student_id}"

def create(router_ip: str, student_id: str, ip_addr: str, prefix: int):
    name = _iface_name(student_id)
    url = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"

    payload = {
        "ietf-interfaces:interface": {
            "name": name,
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {
                "address": [
                    {"ip": ip_addr, "netmask": _mask(prefix)}
                ]
            }
        }
    }

    r = requests.put(
        url, headers=HEADERS, auth=HTTPBasicAuth(USERNAME, PASSWORD),
        data=json.dumps(payload), verify=False, timeout=20
    )
    if r.status_code in (200, 201, 204):
        return "created"
    if r.status_code == 409:
        return "already exists"
    return f"error {r.status_code} {r.text}"

def delete(router_ip: str, student_id: str):
    name = _iface_name(student_id)
    url = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"
    r = requests.delete(url, headers=HEADERS, auth=HTTPBasicAuth(USERNAME, PASSWORD),
                        verify=False, timeout=20)
    if r.status_code in (200, 204):
        return "deleted"
    if r.status_code == 404:
        return "not found"
    return f"error {r.status_code} {r.text}"

def enable(router_ip: str, student_id: str):
    name = _iface_name(student_id)
    url = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"
    payload = {"ietf-interfaces:interface": {"enabled": True}}
    r = requests.patch(url, headers=HEADERS, auth=HTTPBasicAuth(USERNAME, PASSWORD),
                       data=json.dumps(payload), verify=False, timeout=20)
    if r.status_code in (200, 204):
        return "enabled"
    if r.status_code == 404:
        return "not found"
    return f"error {r.status_code} {r.text}"

def disable(router_ip: str, student_id: str):
    name = _iface_name(student_id)
    url = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"
    payload = {"ietf-interfaces:interface": {"enabled": False}}
    r = requests.patch(url, headers=HEADERS, auth=HTTPBasicAuth(USERNAME, PASSWORD),
                       data=json.dumps(payload), verify=False, timeout=20)
    if r.status_code in (200, 204):
        return "shutdowned"
    if r.status_code == 404:
        return "not found"
    return f"error {r.status_code} {r.text}"

def status(router_ip: str, student_id: str):
    name = _iface_name(student_id)
    # get oper-status & admin-status from ietf-interfaces + ietf-interfaces-state
    url = f"{_base(router_ip)}/ietf-interfaces:interfaces/interface={name}"
    r = requests.get(url, headers=HEADERS, auth=HTTPBasicAuth(USERNAME, PASSWORD),
                     verify=False, timeout=20)
    if r.status_code == 404:
        return "no interface"
    if r.status_code not in (200,):
        return f"error {r.status_code} {r.text}"
    data = r.json()
    enabled = data["ietf-interfaces:interface"].get("enabled", False)

    if enabled:
        return "enabled"
    else:
        return "disabled"

def _mask(prefix: int) -> str:
    # convert /24 -> 255.255.255.0
    bits = (0xffffffff >> (32 - prefix)) << (32 - prefix)
    return ".".join(str((bits >> (24 - 8*i)) & 0xff) for i in range(4))
