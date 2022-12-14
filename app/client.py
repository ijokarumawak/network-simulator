import asyncio
import socket
import random
import ipaddress
import yaml
import time
import httpx
import math
from datetime import datetime
from elasticsearch import AsyncElasticsearch
from elasticsearch import ConnectionError
from .model import NetworkRequest
from .es import es, DataStream

ds = DataStream(type='logs', dataset='network_simulator.client')

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
networks_by_id = {}

for network in topology['networks']:
  networks_by_id[network['id']] = network
  local_network = network['network']
  local_network_address = ipaddress.ip_network(local_network)

  clients.extend([{
    'network': network,
    'name': network['id'] + str(i),
    'ip': ipaddress.ip_address(int(local_network_address.network_address) + i + 1),
    'gateway': network['gateway']
  } for i in range(network['num_of_clients'])])

async def executeClient(client, http_client):

  wave_cycle = client['network']['client_wave_cycle']
  if wave_cycle > 0:
    # Generate wave form. w ranges from 0 to 100, if a random number exceeds w, do nothing.
    w = (math.sin(math.radians((time.time() * (360 / wave_cycle)) % 360 )) + 1) * 50
    if random.randrange(0, 100) > w:
      return

  possible_targets = [client['network']['id']]

  if client['network']['gateway'] != 'internet':
    possible_targets.append(client['network']['gateway'])

  if 'routings' in client['network']:
    possible_targets.extend(client['network']['routings'])



  target_network = random.randrange(-1, len(possible_targets))
  if target_network < 0:
    # external traffic
    destination_ip = external_ips[random.randrange(0, len(external_ips))]
  else:
    # local traffic
    destination_network = networks_by_id[possible_targets[target_network]]['network']
    destination_network_address = ipaddress.ip_network(destination_network)
    num_of_local_ips = int(destination_network_address.hostmask)
    destination_ip = str(ipaddress.ip_address(int(destination_network_address.network_address)
                                                + random.randrange(1, num_of_local_ips)))

  source_ip = str(client['ip'])
  source_port = random.randrange(49152, 65536)
  destination_port = 443
  request = NetworkRequest(source_ip=source_ip, source_port=source_port,
                            destination_ip=destination_ip, destination_port=destination_port)

  start = time.time()
  res = await http_client.post('http://localhost:8000/' + client['network']['id'] + '/send/', json=request.dict())

  end = time.time()
  if res.status_code == 200:
    # Convert to ECS and sotre it into Elasticsearch
    result = res.json()
    doc = {
      '@timestamp': datetime.utcnow().isoformat(),
      'labels': {'network': client['network']['id']},
      'source': {'ip': source_ip, 'port': source_port, 'bytes': result['source_bytes']},
      'destination': {'ip': destination_ip, 'port': destination_port, 'bytes': result['destination_bytes']},
      'event': {'duration': math.ceil((end - start) * 1000), 'outcome': 'success' if result['success'] else 'failure'},
      'host': {'name': client['name'], 'hostname': client['name'], 'ip': source_ip}
    }
    ds.add_ds_fields(doc)

    try:
        res = await es.index(index=ds.name(), document=doc)
    except (ConnectionError) as e:
        print('Elasticsearch data ingestion failed.')
        print(e)


async def main():
  async with httpx.AsyncClient(timeout=None) as http_client:
    for client in clients:
      task = asyncio.ensure_future(repeat(client['network']['client_interval'], executeClient, client, http_client))
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
