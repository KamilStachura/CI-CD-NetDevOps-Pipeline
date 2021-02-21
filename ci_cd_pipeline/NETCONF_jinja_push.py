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

def load_vars(task):
    features_to_push = ["ntp", "router", "interface", "crypto", "enable", "ip", "line"]
    host_data = task.run(task=load_yaml, file=f"host_vars/automated_individual_vars/{task.host}.yaml")
    task.host["facts"] = host_data.result
    for feature in features_to_push:
        configure_feature(task, feature)


def configure_feature(task, feature):
    feature_get_template = task.run(task=template_file,
            name=f"Building {feature} configuration",
            template=f"{feature}.j2",
            path="templates",)

    feature_template = feature_get_template.result

    task.run(task=netconf_edit_config,
             target="candidate",
             name="Editing Candidate Configuration",
             config=feature_template)


def config_lock(task):
    task.run(task=netconf_lock, target="candidate", name="Locking Candidate Configuration")


def config_discard(task):
    task.run(task=netconf_discard, name="Discarding Candidate Configuration")


def config_commit(task):
    task.run(task=netconf_commit, name="Committing Candidate Configuration")


def config_unlock(task):
    task.run(task=netconf_unlock, target="candidate", name="Unlocking Candidate Configuration")


def fail_report(device_name, feature, details=None):
    header = {"Authorization": "Bearer Zjc0YmQxODItNmYxNy00Y2FkLTk1NTEtMzY0MjQ2MmNjZjVjZjk5Y2QyYWItM2U2_PF84_consumer",
              "Content-Type": "application/json"}

    data = {"roomId": "Y2lzY29zcGFyazovL3VzL1JPT00vNTlmNGExYjAtMTA0ZS0xMWViLWJhMDYtN2I0ZTU2ODFiMzhi",
            "text": f'{device_name} FAILED {feature} ON {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'}

    return requests.post("https://api.ciscospark.com/v1/messages/", headers=header, data=json.dumps(data), verify=True)

def main():
    credentials = get_credentials.get_credentials()
    nr = InitNornir(config_file="nornir_data/config.yaml")
    nr.inventory.defaults.username = credentials["username"]
    nr.inventory.defaults.password = credentials["password"]
    #nr = nr.filter(F(groups__contains="test_subject"))
    lock = nr.run(task=config_lock)
    print_result(lock)
    results = nr.run(task=load_vars)
    print_result(results)
    failed_changes = nr.data.failed_hosts
    if failed_changes:
        revert = nr.run(task=config_discard)
        print_result(revert)
        for device in failed_changes:
            fail_report(device, results[device].exception,)
    else:
        commit_config = nr.run(task=config_commit)
        print_result(commit_config)

    unlock = nr.run(task=config_unlock)
    print_result(unlock)


if __name__ == "__main__":
    main()
