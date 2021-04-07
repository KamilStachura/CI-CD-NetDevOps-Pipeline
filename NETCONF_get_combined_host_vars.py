from nornir_scrapli.tasks import netconf_get
from nornir_utils.plugins.functions import print_result
from supporting_scripts import get_credentials
from nornir import InitNornir
from nornir.core.filter import F
import xmltodict
import yaml


def append_config(task, config):
    with open(f"host_vars/automated_individual_vars/{task.host}.yaml", "a") as yf:
        yaml.safe_dump(config, yf, allow_unicode=True, sort_keys=False)
        yf.write("\n")


# Check whether there is a current host_var file for the device and if there is, check if the feature is there
# If the feature is not present in the file, append the file with the retrieved config
def check_config(task, feature, config):
    try:
        with open(f"host_vars/automated_individual_vars/{task.host}.yaml") as yf:
            present_config = yaml.safe_load(yf)
            if present_config is None:
                append_config(task, config)
            elif feature in present_config:
                pass
            else:
                append_config(task, config)
    except FileNotFoundError:
        append_config(task, config)



def retrieve_bgp(task, router_dict):
    bgp_dict = router_dict["bgp"]
    feature_dict = {
        "bgp": {"id": bgp_dict["id"], "rid": bgp_dict["bgp"]["router-id"]["ip-id"],
                "neighbors": [], "ipv4_unicast_family": [], "networks": []}
    }

    # Retrieve BGP Neighbors
    for neighbor in bgp_dict["neighbor"]:
        neighbors_dict = {"id": neighbor["id"], "as": neighbor["remote-as"],
                          "loopsource": neighbor["update-source"]["Loopback"]
                          }
        feature_dict["bgp"]["neighbors"].append(neighbors_dict)

    # Retrieve BGP IPv4 Address Family Neighbors
    for ipv4_object in bgp_dict["address-family"]["no-vrf"]["ipv4"]:
        if "ipv4-unicast" in ipv4_object:
            for neighbor in ipv4_object["ipv4-unicast"]["neighbor"]:
                ipv4_neighbors_dict = {"neighborid": neighbor["id"]
                                       }
                feature_dict["bgp"]["ipv4_unicast_family"].append(ipv4_neighbors_dict)

            # Retrieve BGP IPv4 Networks
            if isinstance(ipv4_object["ipv4-unicast"]["network"]["with-mask"], dict):
                networks_dict = {"number": ipv4_object["ipv4-unicast"]["network"]["with-mask"]["number"],
                                 "mask": ipv4_object["ipv4-unicast"]["network"]["with-mask"]["mask"]
                                 }
                feature_dict["bgp"]["networks"].append(networks_dict)
            elif isinstance(ipv4_object["ipv4-unicast"]["network"]["with-mask"], list):
                for network in ipv4_object["ipv4-unicast"]["network"]["with-mask"]:
                    networks_dict = {"number": network["number"], "mask": network["mask"]
                                     }
                    feature_dict["bgp"]["networks"].append(networks_dict)

    check_config(task, "bgp", feature_dict)


def retrieve_ospf(task, router_dict):
    ospf_dict = router_dict["ospf"]
    feature_dict = {
        "ospf": {"id": ospf_dict["id"], "rid": ospf_dict["router-id"], "networks": []}
    }

    # Retrieve OSPF Networks
    if isinstance(ospf_dict["network"], dict):
        networks_dict = {"ip": ospf_dict["network"]["ip"], "mask": ospf_dict["network"]["mask"],
                         "area": ospf_dict["network"]["area"]
                         }
        feature_dict["ospf"]["networks"].append(networks_dict)

    elif isinstance(ospf_dict["network"], list):
        for network in ospf_dict["network"]:
            networks_dict = {"ip": network["ip"], "mask": network["mask"], "area": network["area"]
                             }
            feature_dict["ospf"]["networks"].append(networks_dict)

    check_config(task, "ospf", feature_dict)


def get_router(task):
    result = task.run(task=netconf_get, filter_="/native/router", filter_type="xpath")
    router_data = xmltodict.parse(result.result)
    router_data = router_data["rpc-reply"]["data"]["native"]["router"]
    if "bgp" in router_data:
        retrieve_bgp(task, router_data)

    if "ospf" in router_data:
        retrieve_ospf(task, router_data)


def get_ntp(task):
    ntp_dict = {
        "ntp": {"servers": []}
    }
    result = task.run(task=netconf_get, filter_="/native/ntp", filter_type="xpath")
    ntp_data = xmltodict.parse(result.result)
    ntp_servers = ntp_data["rpc-reply"]["data"]["native"]["ntp"]["server"]["server-list"]

    # Retrieve Ntp Servers
    if isinstance(ntp_servers, dict):
        server_dict = {"ip": ntp_servers["ip-address"]
                       }
        ntp_dict["ntp"]["servers"].append(server_dict)

    elif isinstance(ntp_servers, list):
        for server in ntp_servers:
            server_dict = {"ip": server["ip-address"]
                           }
            ntp_dict["ntp"]["servers"].append(server_dict)

    check_config(task, "ntp", ntp_dict)


def get_interface(task):
    interface_dict = {
        "interfaces": {"GigEthernet": [], "Loopback": []}
    }
    result = task.run(task=netconf_get, filter_="/native/interface", filter_type="xpath")
    interface_data = xmltodict.parse(result.result)
    interface_data = interface_data["rpc-reply"]["data"]["native"]["interface"]

    # Retrieve GigEthernet Interfaces
    for gig_interface in interface_data["GigabitEthernet"]:

        if "shutdown" in gig_interface:
            gig_interface_dict = {
                "name": gig_interface["name"], "shutdown": "True"
            }
            interface_dict["interfaces"]["GigEthernet"].append(gig_interface_dict)

        elif "vrf" in gig_interface["ip"]:
            gig_interface_dict = {"name": gig_interface["name"], "description": gig_interface["description"],
                                  "vrf": gig_interface["ip"]["vrf"]["forwarding"]["word"],
                                  "ip": gig_interface["ip"]["address"]["primary"]["address"],
                                  "mask": gig_interface["ip"]["address"]["primary"]["mask"]
                                  }
            interface_dict["interfaces"]["GigEthernet"].append(gig_interface_dict)

        else:
            gig_interface_dict = {"name": gig_interface["name"], "description": gig_interface["description"],
                                  "unnumbered": gig_interface["ip"]["unnumbered"],
                                  "ospf_network": gig_interface["ip"]["ospf"]["network"]
                                  }
            if "crypto" in gig_interface:
                gig_interface_dict["crypto_map"] = gig_interface["crypto"]["map"]["tag"]

            interface_dict["interfaces"]["GigEthernet"].append(gig_interface_dict)

    # Retrieve Loopback Interfaces
    for lb_interface in interface_data["Loopback"]:
        lb_interface_dict = {"name": lb_interface["name"], "description": lb_interface["description"],
                             "ip": lb_interface["ip"]["address"]["primary"]["address"],
                             "mask": lb_interface["ip"]["address"]["primary"]["mask"]
                             }
        interface_dict["interfaces"]["Loopback"].append(lb_interface_dict)

    check_config(task, "interfaces", interface_dict)


def get_ip(task):
    result = task.run(task=netconf_get, filter_="/native/ip", filter_type="xpath")
    ip_data = xmltodict.parse(result.result)
    ip_data = ip_data["rpc-reply"]["data"]["native"]["ip"]
    ip_dict = {
        "ip": {"domain": ip_data["domain"]["name"],
               "tftp_source_gi_int": ip_data["tftp"]["source-interface"]["GigabitEthernet"],
               "source_interface": ip_data["http"]["client"]["source-interface"],
               "vrf": [], "static_routes": [], "extended_acl": []}
    }

    # Retrieve VRFs
    if isinstance(ip_data["vrf"], dict):
        vrf_dict = {"name": ip_data["vrf"]["name"], "description": ip_data["vrf"]["description"]
                    }
        ip_dict["ip"]["vrf"].append(vrf_dict)

    elif isinstance(ip_data["vrf"], list):
        for vrf in ip_data["vrf"]:
            vrf_dict = {"name": vrf["name"], "description": vrf["description"]
                        }
            ip_dict["ip"]["vrf"].append(vrf_dict)

    # Retrieve Static Routes
    if "route" in ip_data:
        if isinstance(ip_data["route"], dict):
            static_route_dict = {"network": ip_data["route"]["ip-route-interface-forwarding-list"]["prefix"],
                                 "mask": ip_data["route"]["ip-route-interface-forwarding-list"]["mask"],
                                 "fwd": ip_data["route"]["ip-route-interface-forwarding-list"]["fwd-list"]["fwd"]
                                 }
            ip_dict["ip"]["static_routes"].append(static_route_dict)

        elif isinstance(ip_data["route"], list):
            for route in ip_data["route"]:
                static_route_dict = {"network": route["ip-route-interface-forwarding-list"]["prefix"],
                                     "mask": route["ip-route-interface-forwarding-list"]["mask"],
                                     "fwd": route["ip-route-interface-forwarding-list"]["fwd-list"]["fwd"]
                                     }
                ip_dict["ip"]["static_routes"].append(static_route_dict)

    # Retrieve Extended ACLs
    for acl in ip_data["access-list"]["extended"]:
        if "access-list-seq-rule" in acl:
            acl_dict = {"name": acl["name"], "sequences": []}

            if isinstance(acl["access-list-seq-rule"], dict):
                sequence_dict = {"number": acl["access-list-seq-rule"]["sequence"],
                                 "action": acl["access-list-seq-rule"]["ace-rule"]["action"],
                                 "protocol": acl["access-list-seq-rule"]["ace-rule"]["protocol"]
                                 }
                if "any" in acl["access-list-seq-rule"]["ace-rule"]:
                    sequence_dict["srcany"] = "True"
                else:
                    sequence_dict["srcip"] = acl["access-list-seq-rule"]["ace-rule"]["ipv4-address"]
                    sequence_dict["srcmask"] = acl["access-list-seq-rule"]["ace-rule"]["mask"]

                if "dst-any" in acl["access-list-seq-rule"]["ace-rule"]:
                    sequence_dict["destany"] = "True"
                else:
                    sequence_dict["destip"] = acl["access-list-seq-rule"]["ace-rule"]["dest-ipv4-address"]
                    sequence_dict["destmask"] = acl["access-list-seq-rule"]["ace-rule"]["dest-mask"]

                acl_dict["sequences"].append(sequence_dict)

            elif isinstance(acl["access-list-seq-rule"], list):
                for sequence in acl["access-list-seq-rule"]:
                    sequence_dict = {"number": sequence["sequence"], "action": sequence["ace-rule"]["action"],
                                     "protocol": sequence["ace-rule"]["protocol"]
                                     }
                    if "any" in sequence["ace-rule"]:
                        sequence_dict["srcany"] = "True"
                    else:
                        sequence_dict["srcip"] = sequence["ace-rule"]["ipv4-address"]
                        sequence_dict["srcmask"] = sequence["ace-rule"]["mask"]

                    if "dst-any" in sequence["ace-rule"]:
                        sequence_dict["destany"] = "True"
                    else:
                        sequence_dict["destip"] = sequence["ace-rule"]["dest-ipv4-address"]
                        sequence_dict["destmask"] = sequence["ace-rule"]["dest-mask"]
                    acl_dict["sequences"].append(sequence_dict)

            ip_dict["ip"]["extended_acl"].append(acl_dict)

    # Check for empty dictionaries and remove those
    for key, value in list(ip_dict["ip"].items()):
        if not value:
            del ip_dict["ip"][key]

    check_config(task, "ip", ip_dict)


def get_crypto(task):
    result = task.run(task=netconf_get, filter_="/native/crypto", filter_type="xpath")
    crypto_data = xmltodict.parse(result.result)
    crypto_data = crypto_data["rpc-reply"]["data"]["native"]["crypto"]
    ss_cert = crypto_data["pki"]["certificate"]["chain"][1]["name"].split("-")
    crypto_dict = {
        "crypto": {"transform_sets": [], "isakmp_keys": [], "policy": [], "crypto_map": [],
                   "self_signed_certificate": ss_cert[3]
                   }
    }

    # Retrieve Transform Sets
    if "ipsec" in crypto_data and "transform-set" in crypto_data["ipsec"]:
        if isinstance(crypto_data["ipsec"]["transform-set"], dict):
            ts_dict = {"tag": crypto_data["ipsec"]["transform-set"]["tag"],
                       "esp": crypto_data["ipsec"]["transform-set"]["esp"],
                       "key_bit": crypto_data["ipsec"]["transform-set"]["key-bit"],
                       "esp_hmac": crypto_data["ipsec"]["transform-set"]["esp-hmac"]
                       }
            crypto_dict["crypto"]["transform_sets"].append(ts_dict)

        elif isinstance(crypto_data["ipsec"]["transform-set"], list):
            for ts in crypto_data["ipsec"]["transform-set"]:
                ts_dict = {"tag": ts["tag"], "esp": ts["esp"], "key_bit": ts["key-bit"], "esp_hmac": ts["esp-hmac"]
                           }
                crypto_dict["crypto"]["transform_sets"].append(ts_dict)

    # Retrieve Isakmp Keys
    if "isakmp" in crypto_data:

        if isinstance(crypto_data["isakmp"]["key"]["key-address"], dict):
            isakmp_keys_dict = {"key": crypto_data["isakmp"]["key"]["key-address"]["key"],
                                "peer": crypto_data["isakmp"]["key"]["key-address"]["addr4-container"]["address"]
                                }
            crypto_dict["crypto"]["isakmp_keys"].append(isakmp_keys_dict)

        elif isinstance(crypto_data["isakmp"]["key"]["key-address"], list):
            for key in crypto_data["isakmp"]["key"]["key-address"]:
                isakmp_keys_dict = {"key": key["key"], "peer": key["addr4-container"]["address"]
                                    }
                crypto_dict["crypto"]["isakmp_keys"].append(isakmp_keys_dict)

        # Retrieve Isakmp Policies
        if isinstance(crypto_data["isakmp"]["policy"], dict):
            policy_dict = {"number": crypto_data["isakmp"]["policy"]["number"],
                           "auth": crypto_data["isakmp"]["policy"]["authentication"],
                           "group": crypto_data["isakmp"]["policy"]["group"],
                           "hash": crypto_data["isakmp"]["policy"]["hash"],
                           "lifetime": crypto_data["isakmp"]["policy"]["lifetime"]
                           }
            crypto_dict["crypto"]["policy"].append(policy_dict)

        elif isinstance(crypto_data["isakmp"]["policy"], list):
            for policy in crypto_data["isakmp"]["policy"]:
                policy_dict = {"number": policy["number"], "auth": policy["authentication"], "group": policy["group"],
                               "hash": policy["hash"], "lifetime": policy["lifetime"]
                               }
                crypto_dict["crypto"]["policy"].append(policy_dict)

    # Retrieve Crypto Maps
    if "crypto-map" in crypto_data:
        if isinstance(crypto_data["crypto-map"]["map"], dict):
            crypto_map_dict = {"name": crypto_data["crypto-map"]["map"]["name"],
                               "sequence": crypto_data["crypto-map"]["map"]["sequence-number"],
                               "keying": crypto_data["crypto-map"]["map"]["keying"],
                               "match": crypto_data["crypto-map"]["map"]["match"]["address"],
                               "peer": crypto_data["crypto-map"]["map"]["set"]["peer"]["address"],
                               "pfs": crypto_data["crypto-map"]["map"]["set"]["pfs"]["group"],
                               "transform_set": crypto_data["crypto-map"]["map"]["set"]["transform-set"]
                               }
            crypto_dict["crypto"]["crypto_map"].append(crypto_map_dict)

        elif isinstance(crypto_data["crypto-map"]["map"], list):
            for map in crypto_data["crypto-map"]["map"]:
                crypto_map_dict = {"name": map["name"], "sequence": map["sequence-number"], "keying": map["keying"],
                                   "match": map["match"]["address"], "peer": map["set"]["peer"]["address"],
                                   "pfs": map["set"]["pfs"]["group"], "transform_set": map["set"]["transform-set"]
                                   }
                crypto_dict["crypto"]["crypto_map"].append(crypto_map_dict)

    # Check for empty dictionaries and remove those
    for key, value in list(crypto_dict["crypto"].items()):
        if not value:
            del crypto_dict["crypto"][key]

    check_config(task, "crypto", crypto_dict)


def main():
    # Select which get functions would you like to run to retrieve the devices' configs
    # Each of the features has a corresponding function, which retrieves key information about each feature
    # The key information is then stored in a host_var file, which combines config from all features
    list_of_features_to_get = [get_ntp, get_router, get_ip, get_interface, get_crypto]

    # Decrypt the credentials for all devices from the encrypted file via Ansible vault
    credentials = get_credentials.get_credentials()

    # Instantiate Nornir with given config file
    nr = InitNornir(config_file="nornir_data/config.yaml")
    nr.inventory.defaults.username = credentials["username"]
    nr.inventory.defaults.password = credentials["password"]

    # Retrieve all of the specified features from the list_of_features_to_get
    for feature in list_of_features_to_get:
        result = nr.run(task=feature)
        print_result(result)


if __name__ == "__main__":
    main()
