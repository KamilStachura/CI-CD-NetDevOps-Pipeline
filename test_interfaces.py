import requests
import json
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from supporting_scripts import get_credentials
from datetime import datetime
import os
import yaml


# Retrieve the interfaces information from the host_vars files and return it to the main function
def get_interface_information():

    devices_interfaces = {}
    device_list = os.listdir("host_vars/automated_individual_vars")

    # Open every device's config file and load it into the temp memory
    for device in device_list:
        host = device.split(".")
        expected_up_interfaces = []
        expected_shut_interfaces = []
        device_dict = {
            "shut_interfaces": expected_shut_interfaces, "up_interfaces": expected_up_interfaces
        }

        # Append the lists of shut and up interfaces with the appropriate expected interfaces
        with open(f"/host_vars/automated_individual_vars/{device}") as cf:
            device_config = yaml.safe_load(cf)
        for interface in device_config["interfaces"]["GigEthernet"]:
            if "shutdown" in interface:
                expected_shut_interfaces.append(f"GigabitEthernet{interface['name']}")
            else:
                expected_up_interfaces.append(f"GigabitEthernet{interface['name']}")

        devices_interfaces[host[0]] = device_dict

    return devices_interfaces


# Issue "show ip interface brief" command and use the output to compare it with the expected states of each interface
# If an interface is not in the expected state, send a fail report with the details
def interface_test(task, expected_interfaces):
    response = task.run(netmiko_send_command, command_string="show ip interface brief", use_genie=True)
    interfaces = response.result["interface"]
    other = []
    actual_interfaces = {
        task.host.name: {"shut_interfaces": [], "up_interfaces": []}
    }
    missing_interfaces = {
        task.host.name: {"shut_interfaces": [], "up_interfaces": []}
    }

    for interface in interfaces:
        if interfaces[interface]["protocol"] == "up" and interfaces[interface]["status"] == "up":
            actual_interfaces[task.host.name]["up_interfaces"].append(interface)
        elif interfaces[interface]["protocol"] == "down" and interfaces[interface]["status"] == "administratively down":
            actual_interfaces[task.host.name]["shut_interfaces"].append(interface)
        else:
            other.append(interface)
    for up_interface in expected_interfaces[task.host.name]["up_interfaces"]:
        if up_interface in actual_interfaces[task.host.name]["up_interfaces"]:
            continue
        else:
            missing_interfaces[task.host.name]["up_interfaces"].append(up_interface)
    for shut_interface in expected_interfaces[task.host.name]["shut_interfaces"]:
        if shut_interface in actual_interfaces[task.host.name]["shut_interfaces"]:
            continue
        else:
            missing_interfaces[task.host.name]["shut_interfaces"].append(shut_interface)

    if missing_interfaces[task.host.name]["up_interfaces"]:
        print(f"{task.host.name} Failed Up Interface Test")
        fail_report(
            task.host.name, "UP INTERFACE",
            f"The following interface(s) are not up {missing_interfaces[task.host.name]['up_interfaces']}")
    else:
        print(f"{task.host.name} Passed Up Interface Test")

    if missing_interfaces[task.host.name]["shut_interfaces"]:
        print(f"{task.host.name} Failed Shut Interface Test")
        fail_report(
            task.host.name, "SHUT INTERFACE",
            f"The following interface(s) are not shut {missing_interfaces[task.host.name]['shut_interfaces']}")
    else:
        print(f"{task.host.name} Passed Shut Interface Test")


# Create a fail report by providing the device name, feature and optional details
# The report is sent via WebEx bot to specified roomID
def fail_report(device_name, feature, details=None):
    header = {"Authorization": "Bearer Zjc0YmQxODItNmYxNy00Y2FkLTk1NTEtMzY0MjQ2MmNjZjVjZjk5Y2QyYWItM2U2_PF84_consumer",
              "Content-Type": "application/json"}

    data = {"roomId": "Y2lzY29zcGFyazovL3VzL1JPT00vNTlmNGExYjAtMTA0ZS0xMWViLWJhMDYtN2I0ZTU2ODFiMzhi",
            "text": f'{device_name} FAILED {feature} TEST ON {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'
                    f'\nAdditional Details: {details}'}

    return requests.post("https://api.ciscospark.com/v1/messages/", headers=header, data=json.dumps(data), verify=True)


def main():
    # Decrypt the credentials for all devices from the encrypted file via Ansible vault
    credentials = get_credentials.get_credentials()

    # Instantiate Nornir with given config file
    nr = InitNornir(config_file="nornir_data/config.yaml")

    # Assign the decrypted credentials to default username/password values for the devices in Nornir inventory
    nr.inventory.defaults.username = credentials["username"]
    nr.inventory.defaults.password = credentials["password"]

    # Retrieve expected interfaces information (shut and up states)
    expected_interfaces = get_interface_information()

    # Run a test to verify if the interfaces that are expected to be either shut or up, are in the expected state.
    interface_test_results = nr.run(
        task=interface_test, expected_interfaces=expected_interfaces
    )
    # print_result(interface_test_results)


if __name__ == "__main__":
    main()
