import requests
from datetime import datetime
import time
import argparse
import getpass
import json
import os
from pprint import pprint


def api_login(username, password, ip):
    data = {"username": username, "password": password, "html5": "-1"}
    url = 'http://{}/api/auth/login'.format(ip)
    login = requests.post(url=url, data=json.dumps(data))
    if login.status_code == 200:
        cookies = login.cookies
        print("\nLogin Successful.\n")
    else:
        print(login.status_code, "Login Failure.", )
        exit(0)
    return cookies


def query_api(url, time_stamp, cookie):
    headers = {
        'Connection': 'keep-alive',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'DNT': '1',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
        'Referer': 'http://192.168.78.148/legacy/',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    api_url = 'http://192.168.78.148/api/'
    full_url = api_url + url + '?_={}'.format(time_stamp)
    nodes = requests.get(url=full_url, headers=headers, cookies=cookie)
    response = nodes.json()
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-ip', '--ip_address', type=str, dest="ip", help='Eve-NG Sever IP Address.')
    parser.add_argument('-t', '--topology', type=str, dest="topo", help='Provide topology name.')
    parser.add_argument('-n', '--nodes', dest="nodes", action='store_true', help='List nodes.')
    parser.add_argument('-u', '--up', dest="start", action='store_true', help='Provide lab name to start')
    parser.add_argument('-d', '--down', dest="stop", action='store_true', help='Provide lab name to stop')
    parser.add_argument('-a', '--all', dest="all_labs", action='store_true', help='List all labs.')
    parser.add_argument('-w', '--wipe', dest="wipe", action='store_true', help='Wipe all nodes.')
    args = parser.parse_args()

    now = datetime.now()
    time_stamp = int(datetime.timestamp(now) * 1000)
    print()
    user = os.environ.get("eve_login")
    pwd = os.environ.get("eve_pass")
    ip = args.ip
    cookie = api_login(user, pwd, ip)

    if args.topo and args.start:
        url = 'labs/{}/nodes/start'.format(args.topo)
        response = query_api(url, time_stamp, cookie)
        print(response)
        print()
    elif args.topo and args.stop:
        url = 'labs/{}/nodes/stop'.format(args.topo)
        response = query_api(url, time_stamp, cookie)
        print(response)
        print()
    elif args.topo and args.nodes:
        url = 'labs/{}/nodes'.format(args.topo)
        data = query_api(url, time_stamp, cookie)
        data = data["data"]
        for device in data.items():
            pprint(device)
        print()
    elif args.all_labs:
        url = 'folders/'
        data = query_api(url, time_stamp, cookie)
        data = data["data"]
        for i in data.items():
            pprint(i)
        print()
    elif args.topo and args.wipe:
        url = 'labs/{}/nodes/wipe'.format(args.topo)
        response = query_api(url, time_stamp, cookie)
        print(response)
        print()
    elif args.topo:
        url = 'labs/{}/nodes'.format(args.topo)
        data = query_api(url, time_stamp, cookie)
        data = data["data"]
        for key, value in data.items():
            name = value["name"]
            device_type = value["type"]
            image = value["image"]
            url = value["url"].split(":")
            ip = url[1].replace("//", "")
            port = (url[2])
            print('{} {} {} {} {} {}'.format(key, name, device_type, image, ip, port))
        print()
    else:
        print("No options given. Use -h for help.")


if __name__ == "__main__":
    main()
