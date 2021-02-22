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


# Retrieve the OSPF information from the host_vars files and return it to the main function
def get_ospf_information():

    ospf_expected_database = []
    ospf_expected_neighbors_dict = {}
    device_list = os.listdir("host_vars/automated_individual_vars")

    # Open every device's config file and load it into the temp memory
    for device in device_list:
        with open(f"host_vars/automated_individual_vars/{device}") as cf:
            device_config = yaml.safe_load(cf)

# Get expected OSPF routers

        ospf_expected_database.append(device_config["ospf"]["rid"])

# Get expected OSPF neighbors based on the number of P2P OSPF interfaces
        host = device.split(".")
        ospf_expected_neighbors_dict[host[0]] = {"interfaces": []}
        interfaces_list = device_config["interfaces"]["GigEthernet"]

        for interface in interfaces_list:
            if "ospf_network" in interface:
                int_name = "GigabitEthernet" + str(interface["name"])
                ospf_expected_neighbors_dict[host[0]]["interfaces"].append(int_name)

        ospf_expected_neighbors_dict[host[0]]["neighbor_count"] = len(ospf_expected_neighbors_dict[host[0]]["interfaces"])

    return ospf_expected_database, ospf_expected_neighbors_dict


# Issue "clear ip ospf process" command on every device and confirm to reset the OSPF process
def reset_ospf(task):
    reset_process = task.run(
        netmiko_send_command, command_string="clear ip ospf process", expect_string=r"."
    )
    confirm = task.run(
        netmiko_send_command, command_string="yes", expect_string=r"."
    )


# Issue "show ip ospf database" command and verify if every device has all the OSPF devices in their database
def ospf_routing_test(task, comparison_list):
    error_list = []
    ospf_database = []
    response = task.run(netmiko_send_command, command_string="show ip ospf database", use_genie=True)
    response = response.result
    response = response["vrf"]["default"]["address_family"]["ipv4"]["instance"]["1"]["areas"]["0.0.0.0"]["database"]["lsa_types"][1]["lsas"]

    for ospf_router in response:
        ospf_database.append(ospf_router)

    for entry in comparison_list:
        if entry in ospf_database:
            continue
        else:
            error_list.append(entry)

    if error_list:
        fail_report(task.host, "OSPF_ROUTING", f"Missing OSPF Routers {error_list}")
    else:
        print(f"{task.host} Passed OSPF Routing Test")

    return response


# Issue "show ip ospf neighbor" command and verify if each device has the expected number of OSPF neighbors
def ospf_neighbor_test(task, ospf_expected_neighbors_dict):
    response = task.run(netmiko_send_command, command_string="show ip ospf neighbor", use_genie=True)
    if response.result:
        interfaces = response.result["interfaces"]
        actual_neighbors_dict = {"interfaces": []}
        missing_neighbors = []
        for interface in interfaces:
            actual_neighbors_dict["interfaces"].append(interface)

        actual_neighbors_dict["neighbor_count"] = len(actual_neighbors_dict["interfaces"])

        for ospf_interface in ospf_expected_neighbors_dict[str(task.host)]["interfaces"]:
            if ospf_interface in actual_neighbors_dict["interfaces"]:
                pass
            else:
                missing_neighbors.append(ospf_interface)

        if actual_neighbors_dict["neighbor_count"] == ospf_expected_neighbors_dict[str(task.host)]["neighbor_count"]:
            print(f"{task.host} Passed OSPF Neighbor Test")
        else:
            print(f"{task.host} Failed OSPF Neighbor Test")
            # Send a fail report if the device has less OSPF neighbors than expected
            fail_report(task.host, "OSPF NEIGHBOR", f"Missing OSPF Neighbor/s on interface/s {missing_neighbors}")
        return response
    else:
        print(f"{task.host} Failed OSPF Neighbor Test")
        # Send a fail report if the device doesn't have any OSPF neighbors, while it should have
        fail_report(task.host, "OSPF NEIGHBOR", f"Missing All OSPF Neighbors")


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

    # Retrieve expected OSPF information
    ospf_expected_routes, ospf_expected_neighbors_dict = get_ospf_information()

    # Reset current ospf process to ensure that any changes are currently active for testing purposes
    ospf_reset_result = nr.run(
        task=reset_ospf, name="OSPF PROCESS RESET STARTED"
    )
    # print_result(ospf_reset_result)

    # Wait a minute, to allow the devices to complete OSPF process
    time.sleep(90)

    # Run OSPF database test to verify if every device has all of the expected OSPF routes
    ospf_routing_test_results = nr.run(
        task=ospf_routing_test, comparison_list=ospf_expected_routes
    )
    # print_result(ospf_routing_test_results)

    # Run OSPF neighbor test to verify if every device has the expected number of neighbors
    ospf_neighbor_test_results = nr.run(
       task=ospf_neighbor_test, ospf_expected_neighbors_dict=ospf_expected_neighbors_dict
    )
    # print_result(ospf_neighbor_test_results)


if __name__ == "__main__":
    main()


