import datetime
import time
import requests

from datetime import datetime


class BigCache:
    # big_cache_url = "http://localhost:36379/cache/"  # settings.WACKAN_CACHE_URL

    def __init__(self, location) -> None:
        self.big_cache_url = location
        # pass

    def get(self, key: str, version=None) -> bytes | None:
        if version:
            key = f"{key}:{version}"

        url = self.big_cache_url + key

        resp = requests.get(url)
        if resp.status_code != 200:
            return None

        return resp.json()["value"]

    def set(
        self,
        key: str,
        value: bytes,
        expires: int | datetime | None = None,
        timeout: int | None = None,
        version=None,
    ) -> None:
        if version:
            key = f"{key}:{version}"
        url = self.big_cache_url + key

        from django.http import HttpResponse

        if isinstance(value, HttpResponse):
            value = value.rendered_content

        payload = None
        if timeout:
            expires = f"{timeout}s"

        if not expires:
            payload = {
                "value": value,
            }
        elif isinstance(expires, str):
            payload = {
                "value": value,
                "duration": expires,
            }
        else:
            if expires < 946684800:  # 2000-01-01보다 작으면 초로 판단.
                expires = int(time.time() + expires)

            payload = {
                "value": value,
                "expire": expires,
            }

        try:
            # JSON 데이터를 POST 요청으로 전송
            response = requests.post(url, json=payload)
            response.raise_for_status()  # 요청 실패 시 예외 발생
        except requests.exceptions.RequestException as e:
            print(f"Error setting cache: {e}")

    def delete(self, key: str) -> None:
        url = self.big_cache_url + key
        response = requests.delete(url)

    def clear(self) -> None:
        pass

    def close(self) -> None:
        pass
