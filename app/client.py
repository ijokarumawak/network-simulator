import asyncio
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

async def executeClient(client):
  print(client)
  record = FlowRecord(host_name='A', interface_name='a0',
    client_bytes=0, client_ip='192.168.10.10', client_port=33456,
    destination_bytes=123, destination_ip='8.8.8.8', destination_port=443)
  doc = record.toEcs()
  doc['data_stream'] = {'type': ds_type, 'dataset': ds_data_set, 'namespace': ds_namespace}

  try:
      res = await es.index(index=ds, document=doc)
      print(res)
  except (ConnectionError) as e:
      print('Elasticsearch data ingestion failed.')
      print(e)



tasks = []
clients = [{'name': 'jello'}]

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
