import json

"""
This script implements a FastAPI-based caching service with LevelDB as the backend.
It provides endpoints for storing, retrieving, deleting, and managing cached data.

Suitable for websites that serve a very large number of pages that take a long time to generate.

The cache remains fast even as the number of cached items grows, using minimal memory and CPU time.

Functions:
    - connect_db(db_path: str): Asynchronously connects to the LevelDB database.
    - lifespan(app: FastAPI): Manages the application lifecycle, including database initialization and cleanup.
    - set_cache(key: str, item: CacheItem): Stores a key-value pair in the cache with optional expiration.
    - set_pickle(key: str, request: Request): Stores raw binary data in the cache.
    - get_pickle(key: str): Retrieves raw binary data from the cache.
    - get_cache(key: str): Retrieves a key-value pair from the cache, checking for expiration.
    - get_close(): Closes the database connection.
    - get_clear(): Clears all cached data and resets the database.
    - get_stats(): Retrieves hit and miss statistics for the cache.
    - get_count(): Counts the number of items in the cache.
    - delete_cache(key: str): Deletes a specific key-value pair from the cache.
    - delete_prefix(prefix: str): Deletes all key-value pairs with a specific prefix.

Classes:
    - CacheItem: A Pydantic model representing a cache item with optional expiration and duration.

Endpoints:
    - GET /cache/{key:path}: Retrieves a JSON Data from the cache. sutable for HTML.
    - POST /cache/{key:path}: 만료 시간과 함께 JSON 데이터를 캐시에 저장합니다. sutable for HTML.
    - GET /pickle/{key:path}: Retrieves raw binary data from the cache. sutable for Pickle.
    - POST /pickle/{key:path}: 만료 시간 없이 원시 이진 데이터를 캐시에 저장합니다. sutable for Pickle.
    - GET /close: Closes the database connection.
    - GET /clear: Clears all cached data.
    - GET /stat: Retrieves cache hit and miss statistics.
    - GET /stat/count: Counts the number of cached items.
    - DELETE /cache/{key:path}: Deletes a specific key-value pair from the cache.
    - DELETE /prefix/{prefix:path}: Deletes all key-value pairs with a specific prefix.

Command-line Arguments:
    - --port: Specifies the port to run the FastAPI application on (default: 36379).
    - --db_path: Specifies the path to the LevelDB database (default: "./data" or the value of the DB_PATH environment variable).

Usage:
    Run the script with optional command-line arguments to start the FastAPI application.
    Example: python main.py --port 8080 --db_path ./my_database
    
    Example (uvicorn): 
        export DB_PATH='./my_database'
        uvicorn src.main:app --host=0.0.0.0 --port=8080 --workers=1

Note:
    - Bigcache uses LevelDB for caching. LevelDB is designed for single-process use. Do not use it in multi-process environments.
    - Since there is no limit on the number of items, ensure sufficient disk space is available.
    - When a page is updated, call /cache/{key:path} to delete the cache.
"""
import time
import re
import os
import uvicorn
import argparse  # 명령줄 인자 처리를 위해 추가
import plyvel
from typing import Optional
from pydantic import BaseModel, field_validator
import asyncio
from fastapi import FastAPI, HTTPException, Request, Response
from contextlib import asynccontextmanager
import httpx


async def connect_db(db_path: str):
    """데이터베이스에 연결합니다.
    Connects to the LevelDB database at the specified path.
    """
    try:
        db_path = db_path
        os.makedirs(db_path, exist_ok=True)  # 디렉토리 생성
        db = plyvel.DB(db_path, create_if_missing=True)
        return db
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"DB 연결 오류: {e}")


cache_db = None
hit_stats: dict = {
    "hit": 0,
    "miss": 0,
    "expire": 0,
    "delete": 0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """application lifespan"""
    app.state.db = await connect_db(os.environ.get("DB_PATH") or "./data")
    cache_db = app.state.db
    print("DB Connected.")
    yield

    app.state.db.close()
    print("DB Closed.")


TITLE = "BigCache Service"
DESCRIPTION = "FastAPI Cache Service with LevelDB"
VERSION = "0.1.0"
app = FastAPI(lifespan=lifespan, title=TITLE, description=DESCRIPTION, version=VERSION)


class CacheItem(BaseModel):
    value: object
    expire: Optional[float] = None  # 만료 시간 (Unix timestamp)
    duration: Optional[str] = None  # 유효 기간 (예: '10s', '1m', '1d')

    def _parse_duration(self) -> Optional[float]:
        if self.duration is None:
            return None
        try:
            match = re.match(r"(\d+)([smhd])", self.duration)
            if not match:
                raise ValueError("Invalid duration format. (ex: '10s', '1m', '1d')")
            num, unit = match.groups()
            num = int(num)
            if unit == "s":
                return time.time() + num
            elif unit == "m":
                return time.time() + num * 60
            elif unit == "h":
                return time.time() + num * 3600
            elif unit == "d":
                return time.time() + num * 86400
        except Exception as e:
            raise ValueError("duration error")

    def parse_duration(self):
        # duration to Unix timestamp
        if self.duration is None:
            return

        self.expire = self._parse_duration()


@app.post("/cache/{key:path}")
async def set_cache(key: str, item: CacheItem):
    """캐시에 JSON Data를 저장합니다.
    Stores JSON data in the cache with an expiration time. Suitable for HTML.
    """
    try:
        item.parse_duration()
        value_to_store = item.model_dump_json().encode()
        # value_to_store = json.dumps(item.model_dump_json()).encode()
        key = key.lstrip("/").rstrip("/")  # 선행 / 제거, 뒤의 /도 제거

        # app.state.db.put(key.encode(), value_to_store)
        # 블로킹 작업을 별도의 스레드에서 실행
        await asyncio.to_thread(app.state.db.put, key.encode(), value_to_store)

        return {"key": key, "value": item.value, "expire": item.expire}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"캐시 저장 오류: {e}")


# @app.post("/pickle/")
@app.post("/pickle/{key:path}")
async def set_pickle(key: str, request: Request):
    """캐시에 바이너리 스트림을 저장합니다.
    Stores raw binary data in the cache without expiration. Suitable for Pickle."""

    try:
        body = await request.body()
        # item.parse_duration()
        value_to_store = body
        # value_to_store = json.dumps(item.model_dump_json()).encode()
        key = key.lstrip("/").rstrip("/")  # 선행 / 제거, 뒤의 /도 제거

        # 블로킹 작업을 별도의 스레드에서 실행
        # run blocking I/O in a separate thread
        await asyncio.to_thread(app.state.db.put, key.encode(), value_to_store)

        return {"key": key, "expire": "not set"}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail="cache save error")


@app.get("/pickle/{key:path}")
async def get_pickle(key: str):
    """캐시에서 키에 해당하는 값을 조회합니다.
    Retrieves raw binary data from the cache. Suitable for Pickle.
    """
    try:
        # 선행 / 제거, 뒤의 /도 제거
        # remove leading / and trailing /
        key = key.lstrip("/").rstrip("/")
        value_bytes = await asyncio.to_thread(app.state.db.get, key.encode())

        if value_bytes:
            hit_stats["hit"] += 1
            return Response(content=value_bytes)
        else:
            hit_stats["miss"] += 1
            raise HTTPException(status_code=404, detail="cache miss")
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail="cache get error")


@app.get("/cache/{key:path}")
async def get_cache(key: str):
    """캐시에서 키에 해당하는 값을 조회합니다.
    Retrieves a JSON Data from the cache."""
    try:
        # 선행 / 제거, 뒤의 /도 제거
        # remove leading / and trailing /
        key = key.lstrip("/").rstrip("/")
        value_bytes = await asyncio.to_thread(app.state.db.get, key.encode())

        if value_bytes:
            item = CacheItem.model_validate_json(value_bytes.decode())

            if item.expire is None or item.expire > time.time():
                hit_stats["hit"] += 1
                return {
                    "key": key,
                    "value": item.value,
                    "expire": item.expire,
                    "duration": item.duration,
                }
            else:
                # 만료된 데이터 삭제
                # remove expired data
                hit_stats["expire"] += 1
                await asyncio.to_thread(app.state.db.delete, key.encode())
                raise HTTPException(
                    status_code=404, detail="캐시된 데이터가 만료되었습니다.(expired)"
                )
        else:
            hit_stats["miss"] += 1
            raise HTTPException(
                status_code=404, detail="캐시된 데이터를 찾을 수 없습니다.(miss)"
            )
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail="캐시 조회 오류")


@app.get("/close")
async def get_close():
    """DB 연결을 종료합니다.
    Closes the database connection.
    """
    try:
        # 블로킹 작업을 별도의 스레드에서 실행
        await asyncio.to_thread(app.state.db.close)
        app.state.db = None
        return {"message": "DB connection closed."}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail="DB close error")


@app.get("/clear")
async def get_clear():
    """캐시를 모두 삭제합니다.
    Deletes all cached data and resets the database.
    """
    try:
        app.state.db.close()
        os.remove(app.state.db.path)  # DB 파일 삭제

        # await asyncio.to_thread(app.state.db.close)
        app.state.db = connect_db(app.state.db.path)  # DB 재연결
        return {"message": "All cache deleted."}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail="Cache clear error")


@app.get("/stat")
async def get_stats():
    """Hit 및 Miss 통계를 조회합니다.
    Retrieves hit and miss statistics.
    """

    stats = hit_stats.copy()
    hit_rate = (
        hit_stats["hit"] / (hit_stats["hit"] + hit_stats["miss"])
        if (hit_stats["hit"] + hit_stats["miss"]) > 0
        else 0
    )
    stats["hit_rate"] = f"{hit_rate * 100:.2f}%"
    return {"stats": stats}


@app.get("/build")
async def build():
    """Cache all items in the ckan"""
    offset = 0
    while True:
        print(f"offset: {offset}")
        url = "https://catalog.gimi9.com/api/3/action/package_list?limit=10000"
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}&offset={offset}")
            if response.status_code == 200:
                result = response.json()
                all_dataset = result.get("result", [])
            else:
                raise HTTPException(
                    status_code=response.status_code, detail="Failed to fetch data"
                )
        if not all_dataset:
            break

        for dataset in all_dataset:
            key = f"dataset_page/{dataset}"

            if await asyncio.to_thread(app.state.db.get, key.encode()) is not None:
                print(f"key: {key} already exists")
                continue
            url = f"https://gimi9.com/dataset/{dataset}/"
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        print(dataset)
                    else:
                        print(f"Failed to fetch data for {dataset}")
            except httpx.ConnectTimeout as e:
                print(f"ConnectTimeout for {url}")
            except httpx.HTTPError as e:
                print(f"HTTPError for {url}")

        offset += 10000


@app.get("/stat/count")
async def get_count():
    """Retrieves the number of cached items.
    Counts the number of items in the cache. This operation may take a long time.
    """
    try:
        # 블로킹 작업을 별도의 스레드에서 실행
        # run blocking I/O in a separate thread
        count = await asyncio.to_thread(lambda: sum(1 for _ in app.state.db.iterator()))
        return {"count": count}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail="Cache counting error")


@app.delete("/cache/{key:path}")
async def delete_cache(key: str):
    """캐시에서 키에 해당하는 데이터를 삭제합니다.
    Deletes a specific key-value pair from the cache.
    """
    try:
        key = key.lstrip("/").rstrip("/")  # 선행 / 제거, 뒤의 /도 제거
        if await asyncio.to_thread(app.state.db.get, key.encode()) is not None:
            await asyncio.to_thread(app.state.db.delete, key.encode())
            hit_stats["delete"] += 1
            # return {"message": f"키 '{key}'가 캐시에서 삭제되었습니다."}
            return {"message": f"'{key}' removed from cache."}
        else:
            raise HTTPException(
                status_code=404, detail="cannot find cache data to delete"
            )
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail="cache delete error")


def _delete_prefix(prefix: str):
    """이터레이터를 사용하여 해당 접두사로 시작하는 키를 찾고 즉시 삭제합니다.
    Uses an iterator to find and delete keys that start with the given prefix.
    """

    BATCH_SIZE = 1000  # 배치 크기
    deleted_count = 0

    with app.state.db.write_batch() as wb:
        for key in app.state.db.iterator(start=prefix, include_value=False):
            if key.startswith(prefix):
                wb.delete(key)
                print(f"Deleted key: {key.decode()}")
                deleted_count += 1
                if deleted_count % BATCH_SIZE == 0:
                    wb.write()  # batch write
                    print(
                        f"Successfully deleted {BATCH_SIZE} keys matching '{prefix.decode()}'"
                    )
            else:
                break  # 더 이상 일치하는 키가 없으면 순회 종료. stop iteration

    return deleted_count


@app.delete("/prefix/{prefix:path}")
async def delete_prefix(prefix: str):
    """캐시에서 패턴에 해당하는 데이터를 삭제합니다.
    Deletes all key-value pairs with a specific prefix."""
    deleted_count = 0
    prefix = prefix.encode()
    if not prefix:
        raise HTTPException(status_code=400, detail="prefix is empty")

    try:
        # run long blocking I/O in a separate thread
        deleted_count = await asyncio.to_thread(_delete_prefix, prefix)

        hit_stats["delete"] += deleted_count
        return {
            "message": f"prefix '{prefix.decode()}': {deleted_count} keys deleted.",
        }
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail="cache delete error")


if __name__ == "__main__":
    # 1. 명령줄 인자 처리
    # 1. Command-line argument parsing
    parser = argparse.ArgumentParser(description="Run the FastAPI application.")
    parser.add_argument(
        "--port", type=int, default=36379, help="Port to run the FastAPI application on"
    )
    parser.add_argument(
        "--db_path",
        type=str,
        default=os.environ.get("DB_PATH") or "./data",
        help="Path to the database",
    )
    args = parser.parse_args()

    # 2. 동적으로 db_path 설정
    # 2. Set db_path dynamically
    cache_db = connect_db(args.db_path)

    # 3. FastAPI 애플리케이션 실행
    # 3. Run the FastAPI application
    uvicorn.run(app, host="0.0.0.0", port=args.port)
