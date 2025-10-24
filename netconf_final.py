# -*- coding: utf-8 -*-
"""
NETCONF operations using ncclient with IETF interfaces model
"""

from ncclient import manager

USERNAME = "admin"
PASSWORD = "cisco"

def _iface_name(student_id: str) -> str:
    return f"Loopback{student_id}"

def _connect(host):
    return manager.connect(
        host=host, port=830, username=USERNAME, password=PASSWORD,
        hostkey_verify=False, device_params={"name": "csr"}, allow_agent=False, look_for_keys=False, timeout=20
    )

def create(router_ip: str, student_id: str, ip_addr: str, prefix: int):
    name = _iface_name(student_id)
    netmask = _mask(prefix)
    cfg = f"""
<config>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{name}</name>
      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:softwareLoopback</type>
      <enabled>true</enabled>
      <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip">
        <address>
          <ip>{ip_addr}</ip>
          <netmask>{netmask}</netmask>
        </address>
      </ipv4>
    </interface>
  </interfaces>
</config>
"""
    with _connect(router_ip) as m:
        r = m.edit_config(target="running", config=cfg)
        if "<ok/>" in str(r):
            return "created"
        return str(r)

def delete(router_ip: str, student_id: str):
    name = _iface_name(student_id)
    cfg = f"""
<config>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface operation="delete">
      <name>{name}</name>
    </interface>
  </interfaces>
</config>
"""
    with _connect(router_ip) as m:
        r = m.edit_config(target="running", config=cfg)
        if "<ok/>" in str(r):
            return "deleted"
        return str(r)

def enable(router_ip: str, student_id: str):
    name = _iface_name(student_id)
    cfg = f"""
<config>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{name}</name>
      <enabled>true</enabled>
    </interface>
  </interfaces>
</config>
"""
    with _connect(router_ip) as m:
        r = m.edit_config(target="running", config=cfg)
        if "<ok/>" in str(r):
            return "enabled"
        return str(r)

def disable(router_ip: str, student_id: str):
    name = _iface_name(student_id)
    cfg = f"""
<config>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{name}</name>
      <enabled>false</enabled>
    </interface>
  </interfaces>
</config>
"""
    with _connect(router_ip) as m:
        r = m.edit_config(target="running", config=cfg)
        if "<ok/>" in str(r):
            return "shutdowned"
        return str(r)

def status(router_ip: str, student_id: str):
    name = _iface_name(student_id)
    filter_xml = f"""
<filter>
  <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{name}</name>
    </interface>
  </interfaces-state>
</filter>
"""
    with _connect(router_ip) as m:
        r = m.get(filter=filter_xml)
        s = str(r)
        if "<data/>" in s:
            return "no interface"
        if "<oper-status>up</oper-status>" in s:
            return "enabled"
        return "disabled"

def _mask(prefix: int) -> str:
    bits = (0xffffffff >> (32 - prefix)) << (32 - prefix)
    return ".".join(str((bits >> (24 - 8*i)) & 0xff) for i in range(4))
