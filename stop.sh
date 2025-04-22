echo 'stopping'
lsof -ti:36379 | xargs kill -9

sleep 1

echo 'stopped'


