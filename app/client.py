import asyncio
import socket
import random
import ipaddress
from elasticsearch import AsyncElasticsearch
from elasticsearch import ConnectionError
from .config import settings
from .flow_record import FlowRecord


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


ds_type = 'logs'
ds_data_set = 'netflow.log'
ds_namespace = 'test'
ds = '{}-{}-{}'.format(ds_type, ds_data_set, ds_namespace)

local_host_name = 'A'
local_network = '192.168.0.0/24'
local_network_address = ipaddress.ip_network(local_network)

num_of_client = 3
num_of_interfaces = 4

tasks = []
clients = [{'ip': ipaddress.ip_address(int(local_network_address.network_address) + i)} for i in range(num_of_client)]

async def executeClient(client):
  print(client)
  destination_ip = external_ips[random.randrange(0, len(external_ips))]
  record = FlowRecord(host_name=local_host_name,
    ingress_interface=random.randrange(0, num_of_interfaces),
    egress_interface=random.randrange(0, num_of_interfaces),
    client_bytes=random.randrange(200, 4096), client_ip=str(client['ip']), client_port=random.randrange(49152, 65536),
    destination_bytes=random.randrange(1024, 10240), destination_ip=destination_ip, destination_port=443)
  doc = record.toEcs()
  doc['data_stream'] = {'type': ds_type, 'dataset': ds_data_set, 'namespace': ds_namespace}

  try:
      res = await es.index(index=ds, document=doc)
      print(res)
  except (ConnectionError) as e:
      print('Elasticsearch data ingestion failed.')
      print(e)



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
