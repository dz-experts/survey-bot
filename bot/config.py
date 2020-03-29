from functools import lru_cache
from typing import List

from dotenv import load_dotenv
from pydantic import BaseSettings


class Config(BaseSettings):

    facebook_page_access_token: str = None
    facebook_verify_token: str = "token"

    # For messaging
    facebook_graph_url: str = "https://graph.facebook.com/v2.6/me/messages"

    # For changing greetings text and get started payload
    facebook_graph_url_profile: str = "https://graph.facebook.com/v2.6/me/messenger_profile"

    questions_url: str = "https://mofeedz.herokuapp.com/api/public/questions/"

    backend_cors_origins_str: str = "*"  # Could be a comma-separated list of origins

    debug: bool = False

    redis_host: str = "redis"

    @property
    def backend_cors_origins(self) -> List[str]:
        return [x.strip() for x in self.backend_cors_origins_str.split(",") if x]

    class Config:
        env_prefix = ""


@lru_cache()
def get_config() -> Config:
    load_dotenv()
    return Config()  # This reads variables from environment
