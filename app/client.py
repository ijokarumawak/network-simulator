import asyncio
import socket
import random
import ipaddress
import yaml
import requests
from elasticsearch import AsyncElasticsearch
from elasticsearch import ConnectionError
from .config import settings
from .model import NetworkRequest


if settings.es_cloud_id:
    es = AsyncElasticsearch(cloud_id=settings.es_cloud_id, api_key=settings.es_api_key)
elif settings.es_hosts:
    es = AsyncElasticsearch(hosts=settings.es_hosts, api_key=settings.es_api_key)
else:
    raise Exception('Either ES_CLOUD_ID or ES_HOSTS is required.')

external_ips = []
external_hosts = open('external_hosts.txt', 'r')
for external_host in external_hosts.read().splitlines():
  external_ip = socket.gethostbyname(external_host)
  print(external_host + '=' + external_ip)
  external_ips.append(external_ip)

with open('topology.yml', 'r') as file:
  topology = yaml.safe_load(file)

print(topology)

# https://stackoverflow.com/questions/37512182/how-can-i-periodically-execute-a-function-with-asyncio
async def repeat(interval, func, *args, **kwargs):
    """Run func every interval seconds.

    If func has not finished before *interval*, will run again
    immediately when the previous iteration finished.

    *args and **kwargs are passed as the arguments to func.
    """
    while True:
        await asyncio.gather(
            func(*args, **kwargs),
            asyncio.sleep(interval),
        )


tasks = []
clients = []

for network in topology['networks']:
  local_network = network['network']
  local_network_address = ipaddress.ip_network(local_network)

  clients.extend([{
    'network_id': network['id'],
    'ip': ipaddress.ip_address(int(local_network_address.network_address) + i),
    'gateway': network['gateway']
  } for i in range(network['num_of_clients'])])

async def executeClient(client):
  print(client)
  target_network = random.randrange(-1, len(topology['networks']))
  if target_network < 0:
    # external traffic
    destination_ip = external_ips[random.randrange(0, len(external_ips))]
  else:
    # local traffic
    destination_network = topology['networks'][target_network]['network']
    destination_network_address = ipaddress.ip_network(destination_network)
    num_of_local_ips = int(destination_network_address.hostmask)
    destination_ip = str(ipaddress.ip_address(int(destination_network_address.network_address)
                                                + random.randrange(1, num_of_local_ips)))

  request = NetworkRequest(source_ip=str(client['ip']), source_port=random.randrange(49152, 65536),
                            destination_ip=destination_ip, destination_port=443)

  print(request)
  res = requests.post('http://localhost:8000/' + client['network_id'] + '/send/', json=request.dict())
  print(res)




async def main():
    for client in clients:

        task = asyncio.ensure_future(
            repeat(10, executeClient, client))
        tasks.append(task)

    await asyncio.gather(*tasks)


async def close():
    await es.close()


loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    for task in tasks:
        task.cancel()
finally:
    loop.run_until_complete(close())
    loop.close()
