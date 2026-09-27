#! /bin/sh
# chkconfig: 2345 55 25
# Description: Startup script for the Apache web server managed by the panel

### BEGIN INIT INFO
# Provides:          apache
# Required-Start:    $all
# Required-Stop:     $all
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: starts the apache web server
### END INIT INFO

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
NAME=httpd
APACHECTL={$SERVER_PATH}/apache/bin/apachectl
PIDFILE={$SERVER_PATH}/apache/logs/httpd.pid

is_running()
{
    if [ -f $PIDFILE ];then
        mPID=`cat $PIDFILE`
        isStart=`ps ax | awk '{ print $1 }' | grep -e "^${mPID}$"`
        if [ "$isStart" != '' ];then
            return 0
        fi
    fi
    return 1
}

case "$1" in
    start)
        echo -n "Starting $NAME... "
        if is_running; then
            echo "$NAME already running."
            exit 0
        fi
        $APACHECTL -k start
        if [ "$?" != 0 ] ; then
            echo " failed"
            exit 1
        fi
        echo " done"
        ;;

    stop)
        echo -n "Stoping $NAME... "
        if ! is_running; then
            echo "$NAME is not running."
            exit 0
        fi
        $APACHECTL -k stop
        echo " done"
        ;;

    restart)
        $APACHECTL -t || exit 1
        $0 stop
        sleep 1
        $0 start
        ;;

    reload)
        echo -n "Reload $NAME... "
        $APACHECTL -k graceful
        echo " done"
        ;;

    configtest)
        $APACHECTL -t
        ;;

    status)
        if is_running; then
            echo "$NAME (pid `cat $PIDFILE`) already running."
        else
            echo "$NAME is stopped"
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|restart|reload|status|configtest}"
        exit 1
        ;;
esac
