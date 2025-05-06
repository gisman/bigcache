source venv/bin/activate

lsof -ti:36399 | xargs kill -9

echo 'starting'

# echo | nohup python src/main.py --reload >> log/bigcache.log &
# echo | nohup python src/main.py --port=36379 --db_path=/disk/ssd2t/bigcache  >> log/bigcache.log &
export DB_PATH='/disk/ssd2t/bigcache_debug'
echo | nohup uvicorn src.main:app --host=0.0.0.0 --port=36399 --workers=1 >> log/bigcache_debug.log &

sleep 1

echo 'started'


