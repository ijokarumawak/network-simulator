import asyncio
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from elasticsearch import AsyncElasticsearch
from elasticsearch import ConnectionError
from .config import settings


if settings.es_cloud_id:
    es = AsyncElasticsearch(cloud_id=settings.es_cloud_id, api_key=settings.es_api_key)
elif settings.es_hosts:
    es = AsyncElasticsearch(hosts=settings.es_hosts, api_key=settings.es_api_key)
else:
    raise Exception('Either ES_CLOUD_ID or ES_HOSTS is required.')


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/items/{id}", response_class=HTMLResponse)
async def read_item(request: Request, id: str):
    return templates.TemplateResponse("item.html", {"request": request, "id": id})

