import requests
from nornir_scrapli.tasks import netconf_edit_config, netconf_unlock, netconf_lock, netconf_discard, netconf_commit
from nornir_utils.plugins.functions import print_result
from nornir import InitNornir
from nornir_utils.plugins.tasks.data import load_yaml
from nornir_jinja2.plugins.tasks import template_file
from nornir.core.filter import F
from supporting_scripts import get_credentials
from datetime import datetime
import json


# Select which features are to be pushed onto the devices
# Load the host_vars from the devices' respective files & temporarily save them under the "facts" key of each device
def load_vars(task):
    features_to_push = ["ntp", "router", "interface", "crypto", "enable", "ip", "line"]
    host_data = task.run(task=load_yaml, file=f"host_vars/automated_individual_vars/{task.host}.yaml")
    task.host["facts"] = host_data.result
    for feature in features_to_push:
        configure_feature(task, feature)


# Build the configuration to be pushed from the Jinja2 templates & device's "facts"
def configure_feature(task, feature):
    feature_get_template = task.run(task=template_file,
            name=f"Building {feature} configuration",
            template=f"{feature}.j2",
            path="templates_test",)

    feature_template = feature_get_template.result

# Push the configuration to the device's candidate configuration
    task.run(task=netconf_edit_config,
             target="candidate",
             name="Editing Candidate Configuration",
             config=feature_template)


# Lock the configuration of all devices to prevent other users from issuing any changes
def config_lock(task):
    task.run(task=netconf_lock, target="candidate", name="Locking Candidate Configuration")


# Discard the candidate configuration
def config_discard(task):
    task.run(task=netconf_discard, name="Discarding Candidate Configuration")


# Commit the candidate configuration to the devices' running configuration
def config_commit(task):
    task.run(task=netconf_commit, name="Committing Candidate Configuration")


# Unlock the devices configuration
def config_unlock(task):
    task.run(task=netconf_unlock, target="candidate", name="Unlocking Candidate Configuration")


# Create a fail report by providing the device name, feature and optional details
# The report is sent via WebEx bot to specified roomID
def fail_report(device_name, stage=""):
    header = {"Authorization": "Bearer Zjc0YmQxODItNmYxNy00Y2FkLTk1NTEtMzY0MjQ2MmNjZjVjZjk5Y2QyYWItM2U2_PF84_consumer",
              "Content-Type": "application/json"}

    data = {"roomId": "Y2lzY29zcGFyazovL3VzL1JPT00vNTlmNGExYjAtMTA0ZS0xMWViLWJhMDYtN2I0ZTU2ODFiMzhi",
            "text": f'{device_name} FAILED {stage} ON {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'}

    return requests.post("https://api.ciscospark.com/v1/messages/", headers=header, data=json.dumps(data), verify=True)


def main():
    # Decrypt the credentials for all devices from the encrypted file via Ansible vault
    credentials = get_credentials.get_credentials()

    # Instantiate Nornir with given config file
    nr = InitNornir(config_file="nornir_data/config.yaml")
    # Assign the decrypted credentials to default username/password values for the devices in Nornir inventory
    nr.inventory.defaults.username = credentials["username"]
    nr.inventory.defaults.password = credentials["password"]

    # Lock the configuration of all devices to prevent other users from issuing any changes
    lock = nr.run(task=config_lock)
    print_result(lock)

    # Load host variables, build templates for all specified features and push to the candidate configuration
    results = nr.run(task=load_vars)
    print_result(results)

    # Verify if any config build or config push has failed
    # If everything was successful, commit the configuration from candidate to running
    # Otherwise, discard the candidate configuration and issue a fail report
    failed_changes = nr.data.failed_hosts
    if failed_changes:
        revert = nr.run(task=config_discard)
        print_result(revert)
        for device in failed_changes:
            fail_report(device, results[device].exception,)
    else:
        commit_config = nr.run(task=config_commit)
        print_result(commit_config)

    # Unlock the devices configuration
    unlock = nr.run(task=config_unlock)
    print_result(unlock)


if __name__ == "__main__":
    main()
