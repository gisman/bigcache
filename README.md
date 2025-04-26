This project implements a FastAPI-based caching service with LevelDB as the backend.
It provides endpoints for storing, retrieving, deleting, and managing cached data.

bigcache provides long-term caching.
This cache server can significantly improve response times for web page requests that are infrequent but take a long time to generate.

Unlike typical in-memory cache servers like Redis or Memcached, LevelDB operates on a disk-based system, allowing it to cache large volumes of data. By leveraging FastAPI, it provides a RESTful API, enabling easy caching and retrieval of data through HTTP requests.

While Django's built-in Cache Backend, FileBasedCache, supports large data storage, it suffers from severe performance degradation when the number of files becomes excessively large. This is because it checks the total number of cache entries whenever a new cache is added, leading to significant delays. Bigcache, on the other hand, does not perform such checks.

The cache remains fast even as the number of cached items grows, using minimal memory and CPU time.

### Functions:
- **connect_db(db_path: str)**: Asynchronously connects to the LevelDB database.
- **lifespan(app: FastAPI)**: Manages the application lifecycle, including database initialization and cleanup.
- **set_cache(key: str, item: CacheItem)**: Stores a key-value pair in the cache with optional expiration.
- **set_pickle(key: str, request: Request)**: Stores raw binary data in the cache.
- **get_pickle(key: str)**: Retrieves raw binary data from the cache.
- **get_cache(key: str)**: Retrieves a key-value pair from the cache, checking for expiration.
- **get_close()**: Closes the database connection.
- **get_clear()**: Clears all cached data and resets the database.
- **get_stats()**: Retrieves hit and miss statistics for the cache.
- **get_count()**: Counts the number of items in the cache.
- **delete_cache(key: str)**: Deletes a specific key-value pair from the cache.
- **delete_prefix(prefix: str)**: Deletes all key-value pairs with a specific prefix.

### Endpoints:
- **GET /cache/{key:path}**: Retrieves a JSON Data from the cache. Suitable for HTML.
- **POST /cache/{key:path}**: Stores JSON data in the cache with an expiration time. Suitable for HTML.
- **GET /pickle/{key:path}**: Retrieves raw binary data from the cache. Suitable for Pickle.
- **POST /pickle/{key:path}**: Stores raw binary data in the cache without an expiration time. Suitable for Pickle.
- **GET /close**: Closes the database connection.
- **GET /clear**: Clears all cached data.
- **GET /stat**: Retrieves cache hit and miss statistics.
- **GET /stat/count**: Counts the number of cached items.
- **DELETE /cache/{key:path}**: Deletes a specific key-value pair from the cache.
- **DELETE /prefix/{prefix:path}**: Deletes all key-value pairs with a specific prefix.


### Usage:

#### Command-line Arguments:

- **--port**: Specifies the port to run the FastAPI application on (default: 36379).
- **--db_path**: Specifies the path to the LevelDB database (default: "./data" or the value of the DB_PATH environment variable).

Run the script with optional command-line arguments to start the FastAPI application.

python: 
```bash
python src/main.py --port 8080 --db_path ./my_database`
```

uvicorn: 
```bash
    DB_PATH='./my_database'
    uvicorn src.main:app --host=0.0.0.0 --port=8080 --workers=1
```

You can find detailed usage of the endpoints at http://localhost:8080/docs.

### Notes

- Since there is no limit on the number of cache entries, ensure that the disk does not run out of space.
- Unnecessary cache entries should be deleted. Use the Delete API to remove them.
- When running with uvicorn, set it to a single worker. (Concurrency is handled by threads, so no need to worry.)
- Statistics are reset upon restarting the application.

### Example

Here is an example of using BigCache in a Django View function. It imports and utilizes `example/big_cache.py`.

* Initialization
```python
from big_cache import BigCache

bigcache = BigCache("http://localhost:36379/cache/")
```

* Example of cache a HTML page in Django
```python
def dataset(request, name_or_id):
    key = request.get_full_path()
    cached_html = cache.get(cache_key)
    if cached_html:
        return HttpResponse(cached_html)

# Example of stores a HTML page
    response = page.serve(request)
    bigcache.set(key, response.rendered_content, timeout="28d")
    return response
```

* Example of cache a Django page with pickle
```python
def dataset(request, name_or_id):
    key = request.get_full_path()
    page = bigcache.unpickle(key)

# Example of stores a HTML page
    response = page.serve(request)
    if bigcache and not has_cache:
        key = f"dataset_page/{name_or_id}"
        bigcache.pickle(key, page)
    return response
```
