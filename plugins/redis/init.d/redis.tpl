#!/bin/bash
# chkconfig: 2345 55 25
# description: Redis (MIT Panel)

### BEGIN INIT INFO
# Provides:          redis
# Required-Start:    $all
# Required-Stop:     $all
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: starts redis
# Description:       starts the redis server
### END INIT INFO

PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin

redis_dir={$SERVER_PATH}
redis_bin=$redis_dir/bin/redis-server
redis_conf=$redis_dir/redis.conf
redis_pid=$redis_dir/redis.pid

is_running()
{
    [ -f $redis_pid ] && kill -0 `cat $redis_pid` 2>/dev/null
}

app_start()
{
    if is_running; then
        echo "Starting redis already running"
        return
    fi
    echo -e "Starting redis... \c"
    $redis_bin $redis_conf --daemonize yes
    echo -e "\033[32mdone\033[0m"
}

app_stop()
{
    if ! is_running; then
        echo "redis not running"
        return
    fi
    echo -e "Stopping redis... \c"
    kill `cat $redis_pid`
    for i in 1 2 3 4 5 6 7 8 9 10; do
        is_running || break
        sleep 1
    done
    echo -e "\033[32mdone\033[0m"
}

app_status()
{
    if is_running; then
        echo -e "\033[32mredis already running\033[0m"
    else
        echo -e "\033[31mredis not running\033[0m"
    fi
}

case "$1" in
    'start') app_start;;
    'stop') app_stop;;
    'restart'|'reload')
        app_stop
        app_start;;
    'status') app_status;;
esac
