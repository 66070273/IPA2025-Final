import json
import requests
requests.packages.urllib3.disable_warnings()

# Router IP Address is 10.0.15.181-184
api_url = "https://10.0.15.65/restconf/data/ietf-interfaces:interfaces/interface=Loopback66070273"

# the RESTCONF HTTP headers, including the Accept and Content-Type
# Two YANG data formats (JSON and XML) work with RESTCONF 
headers = {
    "Content-Type": "application/yang-data+json",
    "Accept": "application/yang-data+json"
}
basicauth = ("admin", "cisco")


def create():
    yangConfig = {
        "ietf-interfaces:interface": {
            "name": "Loopback66070273",
            "description": "Loopback interface created by RESTCONF",
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {
                "address": [
                    {"ip": "172.2.73.1", "netmask": "255.255.255.0"}
                ]
            },
            "ietf-ip:ipv6": {}
        }
    }

    resp = requests.put(
        api_url, 
        data=json.dumps(yangConfig), 
        auth=basicauth, 
        headers=headers, 
        verify=False
    )

    if(resp.status_code >= 200 and resp.status_code <= 299):
        print("STATUS OK: {}".format(resp.status_code))
        return "ok"
    else:
        print('Error. Status Code: {}'.format(resp.status_code))
        return "error"


def delete():
    # เช็กว่ามี interface อยู่ไหมก่อน
    pre = requests.get(api_url, auth=basicauth, headers=headers, verify=False)
    if pre.status_code == 404:
        return "notfound"

    resp = requests.delete(
        api_url, 
        auth=basicauth, 
        headers=headers, 
        verify=False
    )

    if(resp.status_code >= 200 and resp.status_code <= 299):
        print("STATUS OK: {}".format(resp.status_code))
        return "ok"
    else:
        print('Error. Status Code: {}'.format(resp.status_code))
        return "error"


def enable():
    yangConfig = {
        "ietf-interfaces:interface": {
            "enabled": True
        }
    }

    resp = requests.patch(
        api_url, 
        data=json.dumps(yangConfig), 
        auth=basicauth, 
        headers=headers, 
        verify=False
    )

    if(resp.status_code >= 200 and resp.status_code <= 299):
        print("STATUS OK: {}".format(resp.status_code))
        return "ok"
    else:
        print('Error. Status Code: {}'.format(resp.status_code))
        return "error"


def disable():
    yangConfig = {
        "ietf-interfaces:interface": {
            "enabled": False
        }
    }

    resp = requests.patch(
        api_url, 
        data=json.dumps(yangConfig), 
        auth=basicauth, 
        headers=headers, 
        verify=False
    )

    if(resp.status_code >= 200 and resp.status_code <= 299):
        print("STATUS OK: {}".format(resp.status_code))
        return "ok"
    else:
        print('Error. Status Code: {}'.format(resp.status_code))
        return "error"


def status():
    api_url_status = "https://10.0.15.65/restconf/data/ietf-interfaces:interfaces-state/interface=Loopback66070273"

    resp = requests.get(
        api_url_status, 
        auth=basicauth, 
        headers=headers, 
        verify=False
    )

    if(resp.status_code >= 200 and resp.status_code <= 299):
        print("STATUS OK: {}".format(resp.status_code))
        data = resp.json()

        # ในบางเวอร์ชัน key นี้เป็น list, บางเวอร์ชันเป็น dict
        iface = data.get("ietf-interfaces:interface")
        if isinstance(iface, list):
            iface = iface[0] if iface else {}

        admin_status = (iface or {}).get("admin-status")
        oper_status  = (iface or {}).get("oper-status")

        if admin_status == 'up' and oper_status == 'up':
            return "Interface loopback 66070273 is enabled"
        elif admin_status == 'down' and oper_status == 'down':
            return "Interface loopback 66070273 is disabled"
        else:
            # กรณีค่าไม่ครบ/ไม่ตรง spec
            return f"Interface loopback 66070273 is {admin_status}/{oper_status}"

    elif(resp.status_code == 404):
        print("STATUS NOT FOUND: {}".format(resp.status_code))
        return "No Interface loopback 66070273"
    else:
        print('Error. Status Code: {}'.format(resp.status_code))
        return "error"
