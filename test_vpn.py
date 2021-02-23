import requests
import json
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from supporting_scripts import get_credentials
from datetime import datetime
import time


# Issue "show crypto ipsec sa" command on each device and verify if the packets have been encapsulated
def verify_vpn_tunnel(task):
    time.sleep(10)
    response = task.run(
        netmiko_send_command, command_string="show crypto ipsec sa",
    )
    if "#pkts encaps: 0" in response.result:
        print(f"{task.host} Failed VPN Test")
        # Send a fail report if the packets are not being encapsulated/the tunnel is not active
        fail_report(task.host, "VPN", f"The VPN Tunnel is inactive")
    else:
        print(f"{task.host} Passed VPN Test")


# Issue "clear crypto sa" command on specified devices and initiate the vpn tunnel by sending interesting traffic
def vpn_test(task):
    clear_up = task.run(netmiko_send_command, command_string="clear crypto sa", expect_string=r".")
    if task.host.name == "Core1":
        response = task.run(
            netmiko_send_command, command_string="ping 172.168.200.1 source 172.168.100.1 repeat 5", expect_string=r"."
        )
        verify_vpn_tunnel(task)
    elif task.host.name == "Core2":
        response = task.run(
            netmiko_send_command, command_string="ping 172.168.100.1 source 172.168.200.1 repeat 5", expect_string=r"."
        )
        verify_vpn_tunnel(task)
    else:
        pass


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

    # Run the VPN test with Nornir
    vpn_test_results = nr.run(
        task=vpn_test,
    )
    print_result(vpn_test_results)


if __name__ == "__main__":
    main()
