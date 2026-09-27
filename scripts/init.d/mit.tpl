#!/bin/bash
# chkconfig: 2345 55 25
# description: MIT Panel Cloud Service

### BEGIN INIT INFO
# Provides:          mit
# Required-Start:    $all
# Required-Stop:     $all
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: starts mit
# Description:       starts the mit
### END INIT INFO


PATH=/usr/local/bin:/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export LANG=en_US.UTF-8

mit_path={$SERVER_PATH}
PATH=$PATH:$mit_path/bin


if [ -f $mit_path/bin/activate ];then
    source $mit_path/bin/activate
fi

mit_start_panel()
{
    isStart=`ps -ef|grep 'gunicorn -c setting.py app:app' |grep -v grep|awk '{print $2}'`
    if [ "$isStart" == '' ];then
        echo -e "starting mit-panel... \c"
        cd $mit_path &&  gunicorn -c setting.py app:app
        port=$(cat ${mit_path}/data/port.pl)
        isStart=""
        while [[ "$isStart" == "" ]];
        do
            echo -e ".\c"
            sleep 0.5
            isStart=$(lsof -n -P -i:$port|grep LISTEN|grep -v grep|awk '{print $2}'|xargs)
            let n+=1
            if [ $n -gt 20 ];then
                break;
            fi
        done
        if [ "$isStart" == '' ];then
            echo -e "\033[31mfailed\033[0m"
            echo '------------------------------------------------------'
            tail -n 20 ${mit_path}/logs/error.log
            echo '------------------------------------------------------'
            echo -e "\033[31mError: mit-panel service startup failed.\033[0m"
            return;
        fi
        echo -e "\033[32mdone\033[0m"
    else
        echo "starting mit-panel... mit(pid $(echo $isStart)) already running"
    fi
}


mit_start_task()
{
    isStart=$(ps aux |grep 'task.py'|grep -v grep|awk '{print $2}')
    if [ "$isStart" == '' ];then
        echo -e "starting mit-tasks... \c"
        cd $mit_path && python3 task.py >> ${mit_path}/logs/task.log 2>&1 &
        sleep 0.3
        isStart=$(ps aux |grep 'task.py'|grep -v grep|awk '{print $2}')
        if [ "$isStart" == '' ];then
            echo -e "\033[31mfailed\033[0m"
            echo '------------------------------------------------------'
            tail -n 20 $mit_path/logs/task.log
            echo '------------------------------------------------------'
            echo -e "\033[31mError: mit-tasks service startup failed.\033[0m"
            return;
        fi
        echo -e "\033[32mdone\033[0m"
    else
        echo "starting mit-tasks... mit-tasks (pid $(echo $isStart)) already running"
    fi
}

mit_start()
{
    mit_start_task
	mit_start_panel
}

# $mit_path/tmp/panelTask.pl && service mit restart_task
mit_stop_task()
{
    if [ -f $mit_path/tmp/panelTask.pl ];then
        echo -e "\033[32mthe task is running and cannot be stopped\033[0m"
        exit 0
    fi

    echo -e "stopping mit-tasks... \c";
    pids=$(ps aux | grep 'task.py'|grep -v grep|awk '{print $2}')
    arr=($pids)
    for p in ${arr[@]}
    do
        kill -9 $p  > /dev/null 2>&1
    done
    echo -e "\033[32mdone\033[0m"
}

mit_stop_panel()
{
    echo -e "stopping mit-panel... \c";
    arr=`ps aux|grep 'gunicorn -c setting.py app:app'|grep -v grep|awk '{print $2}'`
    for p in ${arr[@]}
    do
        kill -9 $p > /dev/null 2>&1
    done

    pidfile=${mit_path}/logs/mit.pid
    if [ -f $pidfile ];then
        rm -f $pidfile
    fi
    echo -e "\033[32mdone\033[0m"
}

mit_stop()
{
    mit_stop_task
    mit_stop_panel
}

mit_status()
{
    isStart=$(ps aux|grep 'gunicorn -c setting.py app:app'|grep -v grep|awk '{print $2}')
    if [ "$isStart" != '' ];then
        echo -e "\033[32mmit (pid $(echo $isStart)) already running\033[0m"
    else
        echo -e "\033[31mmit not running\033[0m"
    fi

    isStart=$(ps aux |grep 'task.py'|grep -v grep|awk '{print $2}')
    if [ "$isStart" != '' ];then
        echo -e "\033[32mmit-task (pid $isStart) already running\033[0m"
    else
        echo -e "\033[31mmit-task not running\033[0m"
    fi
}


mit_reload()
{
	isStart=$(ps aux|grep 'gunicorn -c setting.py app:app'|grep -v grep|awk '{print $2}')

    if [ "$isStart" != '' ];then
    	echo -e "reload mit... \c";
	    arr=`ps aux|grep 'gunicorn -c setting.py app:app'|grep -v grep|awk '{print $2}'`
		for p in ${arr[@]}
        do
                kill -9 $p
        done
        cd $mit_path && gunicorn -c setting.py app:app
        isStart=`ps aux|grep 'gunicorn -c setting.py app:app'|grep -v grep|awk '{print $2}'`
        if [ "$isStart" == '' ];then
            echo -e "\033[31mfailed\033[0m"
            echo '------------------------------------------------------'
            tail -n 20 $mit_path/logs/error.log
            echo '------------------------------------------------------'
            echo -e "\033[31mError: mit service startup failed.\033[0m"
            return;
        fi
        echo -e "\033[32mdone\033[0m"
    else
        echo -e "\033[31mmit not running\033[0m"
        mit_start
    fi
}

mit_close(){
    echo 'True' > $mit_path/data/close.pl
}

mit_open()
{
    if [ -f $mit_path/data/close.pl ];then
        rm -rf $mit_path/data/close.pl
    fi
}

mit_unbind_domain()
{
    if [ -f $mit_path/data/bind_domain.pl ];then
        rm -rf $mit_path/data/bind_domain.pl
    fi
}

error_logs()
{
	tail -n 100 $mit_path/logs/error.log
}

mit_update()
{
    curl --insecure -fsSL https://raw.githubusercontent.com/tauviec/MIT-Panel/main/scripts/update.sh | bash
}

mit_install_app()
{
    bash $mit_path/scripts/quick/app.sh
}

mit_close_admin_path(){
    if [ -f $mit_path/data/admin_path.pl ]; then
        rm -rf $mit_path/data/admin_path.pl
    fi
}

mit_force_kill()
{
    PLIST=`ps -ef|grep app:app |grep -v grep|awk '{print $2}'`
    for i in $PLIST
    do
        kill -9 $i
    done

    pids=`ps -ef|grep task.py | grep -v grep |awk '{print $2}'`
    arr=($pids)
    for p in ${arr[@]}
    do
        kill -9 $p
    done
}

mit_debug(){
    mit_stop
    mit_force_kill

    port=7200
    if [ -f $mit_path/data/port.pl ];then
        port=$(cat $mit_path/data/port.pl)
    fi

    if [ -d $mit_path ];then
        cd $mit_path
    fi
    gunicorn -b :$port -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1  app:app
}

case "$1" in
    'start') mit_start;;
    'stop') mit_stop;;
    'reload') mit_reload;;
    'restart')
        mit_stop
        mit_start;;
    'restart_panel')
        mit_stop_panel
        mit_start_panel;;
    'restart_task')
        mit_stop_task
        mit_start_task;;
    'status') mit_status;;
    'logs') error_logs;;
    'close') mit_close;;
    'open') mit_open;;
    'update') mit_update;;
    'install_app') mit_install_app;;
    'close_admin_path') mit_close_admin_path;;
    'unbind_domain') mit_unbind_domain;;
    'debug') mit_debug;;
    'default')
        cd $mit_path
        port=7200

        if [ -f $mit_path/data/port.pl ];then
            port=$(cat $mit_path/data/port.pl)
        fi

        if [ ! -f $mit_path/data/default.pl ];then
            echo -e "\033[33mInstall Failed\033[0m"
            exit 1
        fi

        password=$(cat $mit_path/data/default.pl)
        if [ -f $mit_path/data/domain.conf ];then
            address=$(cat $mit_path/data/domain.conf)
        fi
        if [ -f $mit_path/data/admin_path.pl ];then
            auth_path=$(cat $mit_path/data/admin_path.pl)
        fi

        if [ "$address" == "" ];then
            v4=$(python3 $mit_path/tools.py getServerIp 4)
            v6=$(python3 $mit_path/tools.py getServerIp 6)
            local_ip=$(python3 $mit_path/tools.py getLocalIp)

            if [ "$v4" != "" ] && [ "$v6" != "" ]; then

                if [ ! -f $mit_path/data/ipv6.pl ];then
                    echo 'True' > $mit_path/data/ipv6.pl
                    mit_stop
                    mit_start
                fi

                address="MIT-Panel-Url-Ipv4: http://$v4:$port$auth_path \nMIT-Panel-Url-Ipv6: http://[$v6]:$port$auth_path"
            elif [ "$v4" != "" ]; then
                address="MIT-Panel-Url-Ipv4: http://$v4:$port$auth_path"
            elif [ "$v6" != "" ]; then

                if [ ! -f $mit_path/data/ipv6.pl ];then
                    #  Need to restart ipv6 to take effect
                    echo 'True' > $mit_path/data/ipv6.pl
                    mit_stop
                    mit_start
                fi
                address="MIT-Panel-Url-Ipv6: http://[$v6]:$port$auth_path"
            else
                address="MIT-Panel-Url: http://you-server-ip:$port$auth_path"
            fi
            
            if [ "$local_ip" != "" ] && [ "$local_ip" != "127.0.0.1" ]; then
                address="$address \nMIT-Panel-Url-Local: http://$local_ip:$port$auth_path"
            fi
            # same machine (Linux desktop, or Windows browser through WSL2)
            address="$address \nMIT-Panel-Url-Localhost: http://localhost:$port$auth_path"
        else
            address="MIT-Panel-Url: http://$address:$port$auth_path"
        fi

        show_panel_ip="$port|"
        echo -e "=================================================================="
        echo -e "\033[32mMIT-Panel default info!\033[0m"
        echo -e "=================================================================="
        echo -e "$address"
        echo -e `python3 $mit_path/tools.py username`
        echo -e `python3 $mit_path/tools.py password`
        # echo -e "password: $password"
        echo -e "\033[33mWarning:\033[0m"
        echo -e "\033[33mIf you cannot access the panel. \033[0m"
        echo -e "\033[33mrelease the following port (${show_panel_ip}888|80|443|22) in the security group.\033[0m"
        echo -e "=================================================================="
        ;;
    *)
        cd $mit_path && python3 $mit_path/tools.py cli $1
        ;;
esac
