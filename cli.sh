#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:/opt/homebrew/bin:~/bin

curPath=`pwd`
rootPath=$(dirname "$curPath")
DIR=$(cd "$(dirname "$0")"; pwd)

PATH=$PATH:$DIR/bin
if [ -f bin/activate ];then
	source bin/activate
fi

export LC_ALL="en_US.UTF-8"


mit_start_task()
{
    isStart=$(ps aux |grep 'task.py'|grep -v grep|awk '{print $2}')
    if [ "$isStart" == '' ];then
        echo -e "Starting mit-tasks... \c"
        cd $DIR && nohup python3 task.py >> ${DIR}/logs/task.log 2>&1 &
        sleep 0.3
        isStart=$(ps aux |grep 'task.py'|grep -v grep|awk '{print $2}')
        if [ "$isStart" == '' ];then
            echo -e "\033[31mfailed\033[0m"
            echo '------------------------------------------------------'
            tail -n 20 $DIR/logs/task.log
            echo '------------------------------------------------------'
            echo -e "\033[31mError: mit-tasks service startup failed.\033[0m"
            return;
        fi
        echo -e "\033[32mdone\033[0m"
    else
        echo "Starting mit-tasks... mit-tasks (pid $(echo $isStart)) already running"
    fi
}

mit_start(){
	gunicorn -c setting.py app:app
	mit_start_task
}


mit_start_debug(){
	python3 task.py >> $DIR/logs/task.log 2>&1 &
	port=7200
    if [ -f ${DIR}/data/port.pl ];then
        port=$(cat ${DIR}/data/port.pl)
    fi
    # gunicorn -b :${port} -k gevent -w 1 app:app
	gunicorn -b :${port} -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app
}

mit_start_debug2(){
	python3 task.py >> $DIR/logs/task.log 2>&1 &
	gunicorn -b :7200 -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1  app:app
}


mit_stop()
{
	PLIST=`ps -ef|grep app:app |grep -v grep|awk '{print $2}'`
	for i in $PLIST
	do
	    kill -9 $i > /dev/null 2>&1
	done

	pids=`ps -ef|grep task.py | grep -v grep |awk '{print $2}'`
	arr=($pids)
    for p in ${arr[@]}
    do
    	kill -9 $p > /dev/null 2>&1
    done
}

case "$1" in
    'start') mit_start;;
    'stop') mit_stop;;
    'restart')
		mit_stop
		mit_start
		;;
	'debug')
		mit_stop
		mit_start_debug
		;;
	'debug2')
		mit_stop
		mit_start_debug2
		;;
esac
