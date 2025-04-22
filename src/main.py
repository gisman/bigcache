import json
import time
import re
import os
import uvicorn
import argparse  # 명령줄 인자 처리를 위해 추가
from fastapi import FastAPI, HTTPException
import plyvel
from typing import Optional
from pydantic import BaseModel, field_validator

app = FastAPI()
hit_stats = {
    "hit": 0,
    "miss": 0,
    "expire": 0,
}
# db_path = "/disk/ssd2t/bigcache"
# db = plyvel.DB(db_path, create_if_missing=True)


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
        db.put(key.encode(), value_to_store)
        return {"key": key, "value": item.value, "expire": item.expire}
    except plyvel.Error as e:
        raise HTTPException(status_code=500, detail=f"캐시 저장 오류: {e}")


@app.get("/cache/{key:path}")
async def get_cache(key: str):
    """캐시에서 키에 해당하는 값을 조회합니다."""
    try:
        # 선행 / 제거, 뒤의 /도 제거
        key = key.lstrip("/").rstrip("/")
        value_bytes = db.get(key.encode())
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
                db.delete(key.encode())
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


@app.get("/stat")
async def get_stats():
    """Hit 및 Miss 통계를 조회합니다."""
    return {"stats": hit_stats}


@app.delete("/cache/{key:path}")
async def delete_cache(key: str):
    """캐시에서 키에 해당하는 데이터를 삭제합니다."""
    try:
        if db.get(key.encode()) is not None:
            db.delete(key.encode())
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
        default="./data",
        help="Path to the database",
    )
    args = parser.parse_args()

    # 2. 동적으로 db_path 설정
    db_path = args.db_path
    os.makedirs(db_path, exist_ok=True)  # 디렉토리 생성
    db = plyvel.DB(db_path, create_if_missing=True)

    # 3. FastAPI 애플리케이션 실행
    uvicorn.run(app, host="0.0.0.0", port=args.port)
