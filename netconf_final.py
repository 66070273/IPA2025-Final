import os
from ncclient import manager

USERNAME = os.getenv("ROUTER_USERNAME", "admin")
PASSWORD = os.getenv("ROUTER_PASSWORD", "cisco")

IETF_IF = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
NATIVE  = "http://cisco.com/ns/yang/Cisco-IOS-XE-native"

def _ifname(sid: str) -> str:
    return f"Loopback{sid}"

def _mask(prefix: int) -> str:
    bits = (0xffffffff >> (32 - prefix)) << (32 - prefix)
    return ".".join(str((bits >> (24 - 8*i)) & 0xFF) for i in range(4))

def _sid_ip(sid: str):
    last3 = sid[-3:]
    x = int(last3[0]); y = int(last3[1:])
    return f"172.{x}.{y}.1", 24

def _connect(host: str):
    return manager.connect(
        host=host, port=830,
        username=USERNAME, password=PASSWORD,
        hostkey_verify=False, device_params={"name": "csr"},
        allow_agent=False, look_for_keys=False, timeout=20
    )

# ---------- existence / enabled checks ----------
def _get_ietf_if_cfg(mgr, name: str) -> str:
    subtree = f"""
      <interfaces xmlns="{IETF_IF}">
        <interface><name>{name}</name></interface>
      </interfaces>
    """.strip()
    rsp = mgr.get_config(source="running", filter=("subtree", subtree))
    return getattr(rsp, "data_xml", str(rsp))

def _get_native_if_cfg(mgr, loop_num: str) -> str:
    subtree = f"""
      <native xmlns="{NATIVE}">
        <interface>
          <Loopback><name>{loop_num}</name></Loopback>
        </interface>
      </native>
    """.strip()
    rsp = mgr.get_config(source="running", filter=("subtree", subtree))
    return getattr(rsp, "data_xml", str(rsp))

def _exists(mgr, name: str) -> bool:
    loop_num = name.replace("Loopback", "")
    xml_all = getattr(mgr.get_config(source="running"), "data_xml", "")
    if f"<name>{name}</name>" in xml_all: return True
    if f"<Loopback><name>{loop_num}</name>" in xml_all: return True
    if f"<name>{loop_num}</name></Loopback>" in xml_all: return True
    if f"<name>{name}</name>" in _get_ietf_if_cfg(mgr, name): return True
    if f"<name>{loop_num}</name>" in _get_native_if_cfg(mgr, loop_num): return True
    return False

def _enabled(mgr, name: str):
    xml_ietf = _get_ietf_if_cfg(mgr, name)
    if "<enabled>true</enabled>" in xml_ietf:  return True
    if "<enabled>false</enabled>" in xml_ietf: return False
    loop_num = name.replace("Loopback", "")
    xml_native = _get_native_if_cfg(mgr, loop_num)
    if xml_native:
        if "<shutdown" in xml_native or "<shutdown/>" in xml_native: return False
        return True
    return None

# ---------- commands ----------
def create(router_ip: str, sid: str):
    name = _ifname(sid)
    ip, pfx = _sid_ip(sid); netmask = _mask(pfx)
    with _connect(router_ip) as m:
        if _exists(m, name):
            return "already exists"
        cfg = f"""
<config>
  <interfaces xmlns="{IETF_IF}">
    <interface>
      <name>{name}</name>
      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:softwareLoopback</type>
      <enabled>true</enabled>
      <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip">
        <address><ip>{ip}</ip><netmask>{netmask}</netmask></address>
      </ipv4>
    </interface>
  </interfaces>
</config>
""".strip()
        r = str(m.edit_config(target="running", config=cfg))
        if "<ok/>" in r:       return "created"
        if "data-exists" in r: return "already exists"
        return r

def delete(router_ip: str, sid: str):
    name = _ifname(sid)
    with _connect(router_ip) as m:
        if not _exists(m, name):
            return "not found"
        cfg = f"""
<config>
  <interfaces xmlns="{IETF_IF}">
    <interface operation="delete">
      <name>{name}</name>
    </interface>
  </interfaces>
</config>
""".strip()
        r = str(m.edit_config(target="running", config=cfg))
        if "<ok/>" in r:  return "deleted"
        return r

def enable(router_ip: str, sid: str):
    name = _ifname(sid)
    with _connect(router_ip) as m:
        if not _exists(m, name): return "not found"
        cfg = f"""
<config>
  <interfaces xmlns="{IETF_IF}">
    <interface><name>{name}</name><enabled>true</enabled></interface>
  </interfaces>
</config>
""".strip()
        r = str(m.edit_config(target="running", config=cfg))
        if "<ok/>" in r:  return "enabled"
        return r

def disable(router_ip: str, sid: str):
    name = _ifname(sid)
    with _connect(router_ip) as m:
        if not _exists(m, name): return "not found"
        cfg = f"""
<config>
  <interfaces xmlns="{IETF_IF}">
    <interface><name>{name}</name><enabled>false</enabled></interface>
  </interfaces>
</config>
""".strip()
        r = str(m.edit_config(target="running", config=cfg))
        if "<ok/>" in r:  return "shutdowned"
        return r

def status(router_ip: str, sid: str):
    name = _ifname(sid)
    with _connect(router_ip) as m:
        if not _exists(m, name):
            return "no interface"
        en = _enabled(m, name)
        if en is True:  return "enabled"
        if en is False: return "disabled"
        subtree = f"""
          <interfaces-state xmlns="{IETF_IF}">
            <interface><name>{name}</name></interface>
          </interfaces-state>
        """.strip()
        data = getattr(m.get(filter=("subtree", subtree)), "data_xml", "")
        if "<oper-status>up</oper-status>" in data:   return "enabled"
        if "<oper-status>down</oper-status>" in data: return "disabled"
        return "disabled"
