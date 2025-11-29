#!/bin/bash

cd /home/gisman/projects/ODP/bigcache
source venv/bin/activate

lsof -ti:36379 | xargs kill -9

echo 'starting'

# echo | nohup python src/main.py --reload >> log/bigcache.log &
# echo | nohup python src/main.py --port=36379 --db_path=/disk/ssd2t/bigcache  >> log/bigcache.log &
export DB_PATH='/disk/ssd2t/bigcache'
echo | nohup uvicorn src.main:app --host=0.0.0.0 --port=36379 --workers=1 > /dev/null 2>&1 &

sleep 1

echo 'started'


