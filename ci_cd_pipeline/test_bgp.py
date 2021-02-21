import requests
import json
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from supporting_scripts import get_credentials
from datetime import datetime
import yaml
import os
import time


# code to convert netmask ip to cidr number
def netmask_to_cidr(netmask):
    '''
    :param netmask: netmask ip addr (eg: 255.255.255.0)
    :return: equivalent cidr number to given netmask ip (eg: 24)
    '''
    return sum([bin(int(x)).count('1') for x in netmask.split('.')])


def get_bgp_information():

    bgp_expected_routers = {}
    bgp_expected_networks = []
    device_list = os.listdir("host_vars/automated_individual_vars")
    for device in device_list:
        with open(f"/home/kamil/Hons/host_vars/automated_individual_vars/{device}") as cf:
            device_config = yaml.safe_load(cf)

# Get expected BGP routers

        bgp_expected_routers[device_config["bgp"]["rid"]] = device_config["bgp"]["id"]

# Get expected BGP networks

        for network in device_config["bgp"]["networks"]:
            bgp_expected_networks.append(f"{network['number']}/{netmask_to_cidr(network['mask'])}")

    return bgp_expected_routers, bgp_expected_networks


def reset_bgp(task):
    response = task.run(
        netmiko_send_command, command_string="clear ip bgp *",
    )


def bgp_routers_test(task, bgp_expected_routers):
    missing_routers = {}
    bgp_routers = {}

    response = task.run(netmiko_send_command, command_string="show ip bgp summary", use_genie=True)
    response = response.result
    response = response["vrf"]["default"]["neighbor"]

    for router in response:

        if response[router]["address_family"][""]["state_pfxrcd"] != "Idle":
            bgp_routers[router] = str(response[router]["address_family"][""]["as"])

    for router_id, router_as in bgp_expected_routers.items():
        if router_id == f"1.1.1.{task.host.name[-1]}":
            continue
        elif router_id in bgp_routers and bgp_routers[router_id] == router_as:
            continue
        else:
            missing_routers[router_id] = router_as
    if missing_routers:
        fail_report(task.host, "BGP ROUTER CHECK", f"Missing BGP Routers (ID:AS) {missing_routers}")
        return print(f"{task.host} FAILED BGP ROUTERS TEST. Missing BGP Routers (ID:AS) {missing_routers}")
    else:
        return print(f"{task.host} Passed BGP Routers Test\n")


def bgp_networks_test(task, bgp_expected_networks):
    missing_networks = []
    bgp_networks = []
    response = task.run(netmiko_send_command, command_string="show ip bgp", use_genie=True)
    response = response.result
    present_networks = response["vrf"]["default"]["address_family"][""]["routes"]

    for network in present_networks:
        bgp_networks.append(network)

    for network in bgp_expected_networks:
        if network in bgp_networks:
            continue
        else:
            missing_networks.append(network)
    if missing_networks:
        fail_report(task.host, "BGP NETWORK CHECK", f"Missing BGP Networks {missing_networks}")
        return print(f"{task.host} FAILED BGP NETWORKS TEST. Missing BGP Networks {missing_networks}")
    else:
        return print(f"{task.host} Passed BGP Networks Test\n")


def fail_report(device_name, feature, details=None):
    header = {"Authorization": "Bearer Zjc0YmQxODItNmYxNy00Y2FkLTk1NTEtMzY0MjQ2MmNjZjVjZjk5Y2QyYWItM2U2_PF84_consumer",
              "Content-Type": "application/json"}

    data = {"roomId": "Y2lzY29zcGFyazovL3VzL1JPT00vNTlmNGExYjAtMTA0ZS0xMWViLWJhMDYtN2I0ZTU2ODFiMzhi",
            "text": f'{device_name} FAILED {feature} TEST ON {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'
                    f'\nAdditional Details: {details}'}

    return requests.post("https://api.ciscospark.com/v1/messages/", headers=header, data=json.dumps(data), verify=True)


def main():
    credentials = get_credentials.get_credentials()
    nr = InitNornir(config_file="nornir_data/config.yaml")
    nr.inventory.defaults.username = credentials["username"]
    nr.inventory.defaults.password = credentials["password"]

    reset_bgp_result = nr.run(
        task=reset_bgp, name="BGP PROCESS RESET STARTED"
    )
    # print_result(reset_bgp_result)
    bgp_expected_routers, bgp_expected_networks = get_bgp_information()
    time.sleep(90)

    bgp_routers_test_results = nr.run(
        task=bgp_routers_test, bgp_expected_routers=bgp_expected_routers, name="BGP ROUTERS TEST STARTED"
    )
    # print_result(bgp_routers_test)

    bgp_networks_test_results = nr.run(
        task=bgp_networks_test, bgp_expected_networks=bgp_expected_networks, name="BGP NETWORKS TEST STARTED"
    )
    # print_result(bgp_networks_test)


if __name__ == "__main__":
    main()