import json

import requests
import uvicorn
from aioredis import ConnectionsPool, create_redis_pool
from fastapi import Depends, FastAPI, Request, Response

from bot import Bot, get_config

app = FastAPI()
config = get_config()


@app.post("/")
async def webhook(request: Request):
    """
    This endpoint is for processing incoming messaging events.
    """
    data = await request.json()
    if data.get("object") != "page":
        return Response(status_code=400)

    the_bla_bla = data.get("entry")[0]["messaging"][0]
    sender = the_bla_bla.get("sender")
    redis_as_memory = await create_redis_pool(f"redis://{config.redis_host}")
    bot = Bot(redis_as_memory, sender.get("id"))
    await bot.chat(the_bla_bla)

    return Response(status_code=200)


@app.get("/")
async def verify(request: Request):
    """
    when the endpoint is registered as a webhook, it must echo back
    the 'hub.challenge' value it receives in the query arguments
    """
    qp = request.query_params
    if qp.get("hub.mode") == "subscribe" and qp.get("hub.challenge"):
        if qp.get("hub.verify_token") == config.facebook_verify_token:
            return Response(content=qp["hub.challenge"])
        return Response(content="Verification token mismatch", status_code=403)

    return Response(content="Nothing to see here!")


@app.get("/init")
async def init():
    params = {"access_token": config.facebook_page_access_token}
    data = {
        "greeting": [
            {
                "locale": "ar_AR",
                "text": "التشخيص الذاتي لفيروس كورونا المستجد (حسب الأعراض فقط)",
            },
            {
                "locale": "fr_FR",
                "text": "Testez vous contre Covid-19 (Symptômes uniquement)",
            },
            {
                "locale": "default",
                "text": "Self check againt Covid-19 (Symptoms only)",
            },
        ],
        "get_started": {"payload": "start"},
    }

    _ = requests.post(config.facebook_graph_url_profile, params=params, json=data,)


@app.get("/menu")
async def setup_menu():
    params = {"access_token": config.facebook_page_access_token}
    headers = {"Content-Type": "application/json"}
    data = json.dumps(
        {
            "persistent_menu": [
                {
                    "locale": "default",
                    "composer_input_disabled": False,
                    "call_to_actions": [
                        {
                            "type": "postback",
                            "title": "Recommencez - أعد التشخيص",
                            "payload": "start",
                        },
                        {
                            "type": "postback",
                            "title": "Appelez le 3030 اتصل بـ",
                            "payload": "do_call",
                        },
                        {
                            "type": "web_url",
                            "title": "موقع وزارة الصحة",
                            "url": "http://www.sante.gov.dz",
                            "webview_height_ratio": "full",
                        },
                    ],
                },
            ]
        }
    )
    r = requests.post(
        config.facebook_graph_url_profile, params=params, headers=headers, data=data,
    )
    print(r.status_code)
    print(r.text)
    return "ok"
