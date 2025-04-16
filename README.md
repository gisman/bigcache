# bigcache

LevelDB와 FastAPI를 활용한 고성능 캐시 서버. 단순하고 빠르며 메모리를 적게 사용.

gimi9.com 서비스에 사용중인 캐시 서버입니다. gimi9.com은 Django 기반이며, 자주 변경되지 않는 수백만개의 데이터셋을 서비스합니다. 변경 주기는 일, 월, 분기, 연 등 다양합니다.

bigcache는 데이터셋 페이지에 대한 장기간 캐시를 제공합니다.
이 캐시 서버는 자주 요청되지는 않지만 응답 시간이 오래 걸리는 웹페이지 요청에 대한 응답 속도를 크게 향상시킬 수 있습니다.

Django에 내장된 Cache Backends 중에 이런 상황에 적합한 캐시 서버는 없습니다. Django의 Cache Backends는 일반적으로 자주 변경되는 데이터에 대한 단시간 동안의 캐시에 적합합니다.

bigcache를 gimi9.com에 적용하여 평균 응답 시간을 1.5초에서 0.2초로 단축할 수 있었습니다.

## 개요

본 프로젝트는 오픈소스 key-value 저장소인 LevelDB와 Python 웹 프레임워크 FastAPI를 이용하여 빠르고 효율적인 캐시 서버를 구현합니다.

일반적인 인메모리 캐시 서버인 Redis나 Memcached와 달리, LevelDB는 디스크 기반으로 작동하여 대용량 데이터를 캐싱할 수 있다는 장점을 가집니다. FastAPI를 통해 RESTful API를 제공하므로, HTTP 요청을 통해 간편하게 데이터를 캐시하고 조회할 수 있습니다.

Django에 내장된 Cache Backend인 FileBasedCache는 대용량 데이터 저장이 가능하지만, 파일 수가 증가함에 따라 성능 저하가 발생합니다. 캐시를 추가할 때 전체 캐시 개수를 검사하므로 오랜 시간이 소요되는 단점이 있습니다.Bigcache는 LevelDB를 기반으로 이러한 문제점을 해결합니다.

**주의사항:**

* 본 캐시 서버는 캐시 삭제 기능을 기본적으로 제공하지 않으므로, 필요한 경우 직접 구현해야 합니다. 샘플로 제공되는 django_example/big_cache.py에는 참고 만료 기간이 지난 캐시를 읽을 때 캐시를 갱신하도록 구현되어 있습니다.

* 이미지, CSS, JavaScript 파일과 같은 정적 파일 서비스에는 적합하지 않습니다. 이러한 정적 파일은 Nginx와 같은 웹 서버를 통해 제공하는 것을 권장합니다.

* default CACHE BACKEND와 함께 사용할 수 있습니다. 
  예를 들어, Django의 default CACHE BACKEND를 Redis로 설정하고, Bigcache를 추가로 사용하여 캐시를 분리할 수 있습니다. 이 경우, Bigcache는 LevelDB를 사용하여 대용량 데이터를 저장하고, Redis는 일반적인 캐시 용도로 사용할 수 있습니다.

* 장기간 캐시 저장을 위해 충분한 디스크 공간을 확보해야 합니다.

* LevelDB는 단일 프로세스만 지원하므로 uWSGI나 Gunicorn과 같은 멀티 프로세스 서버로 실행할 수 없습니다. 충분히 빠르기 때문에 단일 프로세스 서버로 충분하겠지만, 
  멀티 프로세스 서버를 사용해야 하는 경우, Cassandra와 같은 다른 Key-Value 데이터베이스 사용을 고려해야 합니다.


# 실행

터미널에서 다음 명령어를 실행하여 서버를 시작합니다.

``` bash
uvicorn main:app --reload
```

기본 port는 36379입니다. main.py에 하드코딩 되어 있습니다.

# FastAPI UI를 이용한 테스트

http://localhost:36379/docs

위 주소로 접속하면 FastAPI의 Swagger UI를 통해 API를 테스트할 수 있습니다.

# curl을 이용한 테스트

## 캐시 저장 Test

``` bash
curl -X POST -H "Content-Type: application/json" -d '{"value": {"title": "example data", "notes": "example notes"}, "duration": "1m"}' http://localhost:36379/cache/mykey

curl -X POST -H "Content-Type: application/json" -d '{"value": {"title": "example data", "notes": "example notes"}}' http://localhost:36379/cache/mykey_noexpire
```

duration은 캐시 만료 시간을 설정하는 옵션입니다. 이 값을 설정하지 않으면 캐시는 만료되지 않습니다.
캐시 만료 시간은 다음과 같은 형식으로 설정할 수 있습니다.
* 1s: 1초. 60s는 1m과 같습니다.
* 1m: 1분
* 1h: 1시간
* 1d: 1일

## 캐시 읽기 Test

``` bash
curl http://localhost:36379/cache/mykey

curl http://localhost:36379/cache/mykey_noexpire
```

## 캐시 삭제 Test

``` bash
curl -X DELETE http://localhost:36379/cache/mykey

curl -X DELETE http://localhost:36379/cache/mykey_noexpire
```

# django에서 사용하기

django에서 Bigcache를 사용하기 위해서는 다음과 같은 단계를 따르면 됩니다.

django_example/big_cache.py 파일을 참고하여 django 프로젝트에 Connector 역할을 하는 BigCache 클래스를 추가합니다.

cache를 사용하려는 views 함수에 다음과 같이 적용합니다.

``` python
bigcache = BigCache(location="http://localhost:36379/cache/")

def my_view(request, id):
    # 캐시를 조회합니다.
    # 캐시가 있으면 캐시된 내용을 반환합니다.
    key = request.get_full_path()
    content = bigcache.get(key)
    if content:
        return HttpResponse(content)

    # 캐시가 없으면 Page를 생성합니다.
    page = 생략...

    # 캐시를 저장합니다.
    response = page.serve(request)
    bigcache.set(key, response.rendered_content, timeout="28d")
    return response

```
