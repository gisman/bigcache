import json
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


async def connect_db(db_path: str):
    """데이터베이스에 연결합니다."""
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
    # 애플리케이션 시작 시 실행
    # app.state.db = await connect_db()
    app.state.db = await connect_db(os.environ.get("DB_PATH") or "./data")
    cache_db = app.state.db
    print("DB 연결이 초기화되었습니다.")
    yield

    app.state.db.close()  # DB 연결 종료
    print("DB 연결이 해제되었습니다.")


app = FastAPI(lifespan=lifespan)


class CacheItem(BaseModel):
    value: object
    expire: Optional[float] = None  # 만료 시간 (Unix timestamp)
    duration: Optional[str] = None  # 유효 기간 (예: '10s', '1m', '1d')

    # @field_validator("expire")
    # def parse_expire(cls, expire: Optional[str]) -> Optional[float]:
    def _parse_duration(self) -> Optional[float]:
        if self.duration is None:
            return None
        try:
            match = re.match(r"(\d+)([smhd])", self.duration)
            if not match:
                raise ValueError(
                    "유효하지 않은 만료 시간 형식입니다. (예: '10s', '1m', '1d')"
                )
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
            raise ValueError(f"만료 시간 처리 오류: {e}")

    def parse_duration(self):
        # 기존의 duration를 Unix timestamp로 저장
        if self.duration is None:
            return

        self.expire = self._parse_duration()
        # # data = self.model_dump()
        # data["expire"] = self.parse_expire()
        # return data


@app.post("/cache/{key:path}")
async def set_cache(key: str, item: CacheItem):
    """캐시에 키-값 쌍을 저장합니다."""
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
    """캐시에 키-값 쌍을 저장합니다."""
    try:
        body = await request.body()
        # item.parse_duration()
        value_to_store = body
        # value_to_store = json.dumps(item.model_dump_json()).encode()
        key = key.lstrip("/").rstrip("/")  # 선행 / 제거, 뒤의 /도 제거

        # app.state.db.put(key.encode(), value_to_store)
        # 블로킹 작업을 별도의 스레드에서 실행
        await asyncio.to_thread(app.state.db.put, key.encode(), value_to_store)

        return {"key": key, "expire": "not set"}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"캐시 저장 오류: {e}")


# @app.get("/stat/count")
# async def get_count():
#     """캐시된 데이터의 개수를 조회합니다."""
#     try:
#         count = 0
#         for _ in app.state.db.iterator():
#             count += 1
#         return {"count": count}
#     except plyvel.Error as e:
#         raise HTTPException(status_code=500, detail=f"캐시 개수 조회 오류: {e}")


@app.get("/pickle/{key:path}")
async def get_pickle(key: str):
    """캐시에서 키에 해당하는 값을 조회합니다."""
    try:
        # 선행 / 제거, 뒤의 /도 제거
        key = key.lstrip("/").rstrip("/")
        value_bytes = await asyncio.to_thread(app.state.db.get, key.encode())

        if value_bytes:
            hit_stats["hit"] += 1
            return Response(content=value_bytes)
        else:
            hit_stats["miss"] += 1
            raise HTTPException(
                status_code=404, detail="캐시된 데이터를 찾을 수 없습니다."
            )
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"캐시 조회 오류: {e}")


@app.get("/cache/{key:path}")
async def get_cache(key: str):
    """캐시에서 키에 해당하는 값을 조회합니다."""
    try:
        # 선행 / 제거, 뒤의 /도 제거
        key = key.lstrip("/").rstrip("/")
        value_bytes = await asyncio.to_thread(app.state.db.get, key.encode())

        if value_bytes:
            item = CacheItem.model_validate_json(value_bytes.decode())
            # item = CacheItem.model_validate_json(json.loads(value_bytes.decode()))
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
                hit_stats["expire"] += 1
                await asyncio.to_thread(app.state.db.delete, key.encode())
                raise HTTPException(
                    status_code=404, detail="캐시된 데이터가 만료되었습니다."
                )
        else:
            hit_stats["miss"] += 1
            raise HTTPException(
                status_code=404, detail="캐시된 데이터를 찾을 수 없습니다."
            )
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"캐시 조회 오류: {e}")


@app.get("/close")
async def get_close():
    """DB 연결을 종료합니다."""
    try:
        # 블로킹 작업을 별도의 스레드에서 실행
        await asyncio.to_thread(app.state.db.close)
        return {"message": "DB 연결이 종료되었습니다."}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"DB 종료 오류: {e}")


@app.get("/clear")
async def get_clear():
    """캐시를 모두 삭제합니다."""
    try:
        # 블로킹 작업을 별도의 스레드에서 실행
        app.state.db.close()
        os.remove(app.state.db.path)  # DB 파일 삭제

        # await asyncio.to_thread(app.state.db.close)
        cache_db = connect_db(app.state.db.path)  # DB 재연결
        return {"message": "모든 캐시가 삭제되었습니다."}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"캐시 삭제 오류: {e}")


@app.get("/stat")
async def get_stats():
    """Hit 및 Miss 통계를 조회합니다."""

    stats = hit_stats.copy()
    hit_rate = (
        hit_stats["hit"] / (hit_stats["hit"] + hit_stats["miss"])
        if (hit_stats["hit"] + hit_stats["miss"]) > 0
        else 0
    )
    stats["hit_rate"] = f"{hit_rate * 100:.2f}%"
    return {"stats": stats}


@app.get("/stat/count")
async def get_count():
    """캐시된 데이터의 개수를 조회합니다."""
    try:
        # 블로킹 작업을 별도의 스레드에서 실행
        count = await asyncio.to_thread(lambda: sum(1 for _ in app.state.db.iterator()))
        return {"count": count}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"캐시 개수 조회 오류: {e}")


@app.delete("/cache/{key:path}")
async def delete_cache(key: str):
    """캐시에서 키에 해당하는 데이터를 삭제합니다."""
    try:
        key = key.lstrip("/").rstrip("/")  # 선행 / 제거, 뒤의 /도 제거
        if await asyncio.to_thread(app.state.db.get, key.encode()) is not None:
            await asyncio.to_thread(app.state.db.delete, key.encode())
            hit_stats["delete"] += 1
            return {"message": f"키 '{key}'가 캐시에서 삭제되었습니다."}
        else:
            raise HTTPException(
                status_code=404, detail="삭제할 캐시 데이터를 찾을 수 없습니다."
            )
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"캐시 삭제 오류: {e}")


if __name__ == "__main__":
    # 1. 명령줄 인자 처리
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
    cache_db = connect_db(args.db_path)

    # 3. FastAPI 애플리케이션 실행
    uvicorn.run(app, host="0.0.0.0", port=args.port)
