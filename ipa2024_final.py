#######################################################################################
# Yourname:
# Your student ID:
# Your GitHub Repo: 
#######################################################################################

# 1. Import libraries for API requests, JSON formatting, time, os, (restconf_final or netconf_final), netmiko_final, and ansible_final.

import os
import time
import json
import requests
from dotenv import load_dotenv
from restconf_final import create, delete, enable, disable, status
from requests_toolbelt.multipart.encoder import MultipartEncoder
from netmiko_final import gigabit_status
from ansible_final import showrun  # ✅ เพิ่มส่วนนี้เข้ามา

#######################################################################################
# 2. Assign the Webex access token to the variable ACCESS_TOKEN using environment variables.

load_dotenv()  # โหลดค่าจากไฟล์ .env (ถ้ามี)
WEBEX_TOKEN = os.getenv("WEBEX_TOKEN")

if not WEBEX_TOKEN:
    raise SystemExit("ไม่พบ WEBEX_TOKEN ใน environment/.env")

ACCESS_TOKEN = f"Bearer {WEBEX_TOKEN}"

#######################################################################################
# 3. Prepare parameters get the latest message for messages API.

roomIdToGetMessages = os.getenv("WEBEX_ROOM_ID")
if not roomIdToGetMessages:
    raise SystemExit("ไม่พบ WEBEX_ROOM_ID ใน .env")

while True:
    time.sleep(1)

    getParameters = {"roomId": roomIdToGetMessages, "max": 1}
    getHTTPHeader = {"Authorization": ACCESS_TOKEN}

    # 4. Webex API: get latest message
    r = requests.get(
        "https://webexapis.com/v1/messages",
        params=getParameters,
        headers=getHTTPHeader,
    )

    if not r.status_code == 200:
        raise Exception(f"Incorrect reply from Webex Teams API. Status code: {r.status_code}")

    json_data = r.json()
    if len(json_data["items"]) == 0:
        raise Exception("There are no messages in the room.")

    messages = json_data["items"]
    message = messages[0]["text"]
    print("Received message:", message)

    if message.startswith("/66070273 "):
        command = message.split(" ")[1].strip()
        print("Command:", command)

        #######################################################################################
        # 5. Logic for each command
        #######################################################################################

        if command == "create":
            responseMessage = create()
            responseMessage = "Interface loopback 66070273 is created successfully" if responseMessage == "ok" else "Cannot create: Interface loopback 66070273"

        elif command == "delete":
            responseMessage = delete()
            responseMessage = "Interface loopback 66070273 is deleted successfully" if responseMessage == "ok" else "Cannot delete: Interface loopback 66070273"

        elif command == "enable":
            responseMessage = enable()
            responseMessage = "Interface loopback 66070273 is enabled successfully" if responseMessage == "ok" else "Cannot enable: Interface loopback 66070273"

        elif command == "disable":
            responseMessage = disable()
            responseMessage = "Interface loopback 66070273 is shutdowned successfully" if responseMessage == "ok" else "Cannot shutdown: Interface loopback 66070273"

        elif command == "status":
            responseMessage = status()

        elif command == "gigabit_status":
            responseMessage = gigabit_status()

        elif command == "showrun":
            filename = showrun()  # ✅ เรียกใช้ฟังก์ชันจาก ansible_final.py
            if filename.endswith(".txt"):
                responseMessage = "ok"  # ให้ส่วน postData ด้านล่างรู้ว่าต้องแนบไฟล์
            else:
                responseMessage = filename  # เช่น 'Error: Ansible'

        else:
            responseMessage = "Error: No command or unknown command"

        #######################################################################################
        # 6. Post message (ส่งกลับไปยัง Webex Room)
        #######################################################################################

        if command == "showrun" and responseMessage == 'ok':
            # ใช้ชื่อไฟล์จริงจาก showrun()
            fileobject = open(filename, "rb")
            filetype = "text/plain"

            postData = {
                "roomId": roomIdToGetMessages,
                "text": "show running config",
                "files": (filename, fileobject, filetype),
            }

            postData = MultipartEncoder(postData)
            HTTPHeaders = {
                "Authorization": ACCESS_TOKEN,
                "Content-Type": postData.content_type,
            }

        else:
            postData = {"roomId": roomIdToGetMessages, "text": responseMessage}
            postData = json.dumps(postData)
            HTTPHeaders = {
                "Authorization": ACCESS_TOKEN,
                "Content-Type": "application/json"
            }

        r = requests.post(
            "https://webexapis.com/v1/messages",
            data=postData,
            headers=HTTPHeaders,
        )

        if not r.status_code == 200:
            raise Exception(f"Incorrect reply from Webex Teams API. Status code: {r.status_code}")
        else:
            print("Message sent successfully!")
