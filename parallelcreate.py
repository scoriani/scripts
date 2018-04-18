import os
import traceback
import asyncio
import concurrent.futures
import time
import logging

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import DiskCreateOption
from msrestazure.azure_exceptions import CloudError
from haikunator import Haikunator

haikunator = Haikunator()

LOCATION = 'eastus'

GROUP_NAME = 'parallelcreate3'

VNET_NAME = 'testvnet'
SUBNET_NAME = 'default'

OS_DISK_NAME = 'osdisk'
STORAGE_ACCOUNT_NAME = haikunator.haikunate(delimiter='')

IP_CONFIG_NAME = 'ip-config'
NIC_NAME = 'nic'
USERNAME = 'userlogin'
PASSWORD = 'Pa$$w0rd91'
VM_NAME = 'VmName'

vmnumber=500

VM_REFERENCE = {
    'linux': {
        'publisher': 'Canonical',
        'offer': 'UbuntuServer',
        'sku': '16.04.0-LTS',
        'version': 'latest'
    }
}

def get_credentials():
    subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
    credentials = ServicePrincipalCredentials(
        client_id=os.environ['AZURE_CLIENT_ID'],
        secret=os.environ['AZURE_CLIENT_SECRET'],
        tenant=os.environ['AZURE_TENANT_ID']
    )
    return credentials, subscription_id

async def run_example():

    start = time.time()

    credentials, subscription_id = get_credentials()
    resource_client = ResourceManagementClient(credentials, subscription_id)
    compute_client = ComputeManagementClient(credentials, subscription_id)
    network_client = NetworkManagementClient(credentials, subscription_id)

    resource_client.resource_groups.create_or_update(GROUP_NAME, {'location': LOCATION})

    subnet = create_vnet(network_client)

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:

        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(
                executor, 
                create_vm, 
                network_client,
                compute_client,
                subnet
            )
            for i in range(vmnumber)
        ]
        for vm in await asyncio.gather(*futures):
            pass

    end = time.time()         
 
    print('\n '+str(vmnumber)+' VMs created in '+stopWatch(end-start))


def stopWatch(value):
    valueD = (((value/365)/24)/60)
    Days = int (valueD)

    valueH = (valueD-Days)*365
    Hours = int(valueH)

    valueM = (valueH - Hours)*24
    Minutes = int(valueM)

    valueS = (valueM - Minutes)*60
    Seconds = int(valueS)

    return str(Days)+"d;"+str(Hours)+"h;"+str(Minutes)+"m;"+str(Seconds)+"s;"

def create_vm(network_client,compute_client,subnet):

    VM_NAME=haikunator.haikunate(delimiter='')
    print("\nCreate VM: "+VM_NAME)

    try:
        nic = create_nic(network_client,subnet)
        vm_parameters = create_vm_parameters(nic.id, VM_REFERENCE['linux'])
        async_vm_creation = compute_client.virtual_machines.create_or_update(GROUP_NAME, VM_NAME, vm_parameters)
    except Exception as e:
        print('A VM operation failed:', traceback.format_exc(), sep='\n')
    finally:
        return async_vm_creation.wait()

def create_vnet(network_client):

    try:
        async_vnet_creation = network_client.virtual_networks.create_or_update(
            GROUP_NAME,
            VNET_NAME,
            {
                'location': LOCATION,
                'address_space': {
                    'address_prefixes': ['10.0.0.0/16']
                }
            }
        )
        async_vnet_creation.wait()

        async_subnet_creation = network_client.subnets.create_or_update(
            GROUP_NAME,
            VNET_NAME,
            SUBNET_NAME,
            {'address_prefix': '10.0.0.0/20'}
        )
        return async_subnet_creation.result()
    except CloudError:
        return network_client.subnets.get(GROUP_NAME,VNET_NAME,SUBNET_NAME)

def create_nic(network_client, subnet):
    async_nic_creation = network_client.network_interfaces.create_or_update(
        GROUP_NAME,
        haikunator.haikunate(delimiter=''),
        {
            'location': LOCATION,
            'ip_configurations': [{
                'name': IP_CONFIG_NAME,
                'subnet': {
                    'id': subnet.id
                }
            }]
        }
    )
    return async_nic_creation.result()

def create_vm_parameters(nic_id, vm_reference):
    return {
        'location': LOCATION,
        'os_profile': {
            'computer_name': VM_NAME,
            'admin_username': USERNAME,
            'admin_password': PASSWORD
        },
        'hardware_profile': {
            'vm_size': 'Standard_DS1_v2'
        },
        'storage_profile': {
            'image_reference': {
                'publisher': vm_reference['publisher'],
                'offer': vm_reference['offer'],
                'sku': vm_reference['sku'],
                'version': vm_reference['version']
            },
        },
        'network_profile': {
            'network_interfaces': [{
                'id': nic_id,
            }]
        },
    }

if __name__ == "__main__":

    logger = logging.getLogger('msrest')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_example())