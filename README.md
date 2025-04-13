# bigcache

leveldb를 사용하여 매우 많은 데이터를 빠르게 캐시하는 FastAPI 서버.

leveldb는 Google에서 만든 오픈소스 데이터베이스로, key-value 쌍을 저장하는 데 최적화되어 있습니다. 이 프로젝트는 FastAPI와 leveldb를 사용하여 캐시 서버를 구현한 것입니다.

대표적인 캐시 서버인 redis와 memcached와는 다르게, leveldb는 디스크 기반의 데이터베이스이기 때문에 대량의 데이터를 저장할 수 있습니다. 또한, FastAPI를 사용하여 RESTful API를 제공하므로, HTTP 요청을 통해 데이터를 저장하고 조회할 수 있습니다.

leveldb는 단일 프로세스에서만 사용할 수 있으므로, uwsgi, gunicorn과 같은 멀티 프로세스 환경에서는 사용할 수 없지만 bigcache는 멀티 프로세스 환경에서도 사용할 수 있습니다.

자주 사용되지 않지만 대량의 데이터를 서비스해야 하는 경우에 유용합니다. 예를 들어, 오래 걸리는 쿼리를 캐시하여 빠르게 응답할 수 있습니다. 

이미지, css, js 파일과 같은 정적 파일을 서비스하는 것은 권장하지 않습니다. 정적 파일은 nginx와 같은 웹 서버에서 서비스하는 것이 좋습니다.


## 터미널에서 다음 명령어를 실행하여 서버를 시작합니다.

``` bash
uvicorn main:app --reload
```

## 캐시 저장 Test

``` bash
curl -X POST -H "Content-Type: application/json" -d '{"value": {"title": "example data", "notes": "example notes"}, "duration": "1m"}' http://localhost:36379/cache/mykey

curl -X POST -H "Content-Type: application/json" -d '{"value": {"title": "example data", "notes": "example notes"}}' http://localhost:36379/cache/mykey_noexpire
```

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


curl -X DELETE http://localhost:36379/cache/www-data-go-kr-data-filedata-15127817
curl http://localhost:36379/cache/www-data-go-kr-data-filedata-15127817