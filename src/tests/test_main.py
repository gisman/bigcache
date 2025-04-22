import pytest
import os
from fastapi.testclient import TestClient
from src.main import app, connect_db

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def initialize_db():
    """테스트 실행 전에 데이터베이스를 초기화합니다."""
    db_path = "./test_data"  # 테스트용 데이터베이스 경로
    if not os.path.exists(db_path):
        os.makedirs(db_path)
    app.db = connect_db(db_path)  # main.py의 connect_db 함수 호출
    yield
    # 테스트 종료 후 데이터 정리
    import shutil

    shutil.rmtree(db_path)


@pytest.fixture
def setup_cache():
    """테스트 전에 캐시를 초기화합니다."""
    client.delete("/cache/test_key")  # 테스트 키 삭제
    yield
    client.delete("/cache/test_key")  # 테스트 후 정리


def test_set_cache(setup_cache):
    """캐시에 데이터를 저장하는 테스트."""
    response = client.post(
        "/cache/test_key", json={"value": "test_value", "duration": "10s"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "test_key"
    assert data["value"] == "test_value"
    assert "expire" in data


def test_get_cache(setup_cache):
    """캐시에서 데이터를 조회하는 테스트."""
    # 먼저 데이터를 저장
    client.post("/cache/test_key", json={"value": "test_value", "duration": "10s"})
    # 데이터를 조회
    response = client.get("/cache/test_key")
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "test_key"
    assert data["value"] == "test_value"


def test_get_cache_expired(setup_cache):
    """만료된 데이터를 조회하는 테스트."""
    # 데이터를 저장
    client.post("/cache/test_key", json={"value": "test_value", "duration": "1s"})
    # 만료될 때까지 대기
    import time

    time.sleep(2)
    # 만료된 데이터를 조회
    response = client.get("/cache/test_key")
    assert response.status_code == 404
    assert response.json()["detail"] == "캐시된 데이터가 만료되었습니다."


def test_delete_cache(setup_cache):
    """캐시에서 데이터를 삭제하는 테스트."""
    # 데이터를 저장
    client.post("/cache/test_key", json={"value": "test_value", "duration": "10s"})
    # 데이터를 삭제
    response = client.delete("/cache/test_key")
    assert response.status_code == 200
    assert response.json()["message"] == "키 'test_key'가 캐시에서 삭제되었습니다."
    # 삭제된 데이터를 조회
    response = client.get("/cache/test_key")
    assert response.status_code == 404


def test_get_stats():
    """Hit 및 Miss 통계를 조회하는 테스트."""
    response = client.get("/stat")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    assert "hit" in data["stats"]
    assert "miss" in data["stats"]
    assert "expire" in data["stats"]
