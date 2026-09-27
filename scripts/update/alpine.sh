#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin:/opt/homebrew/bin
export PATH
LANG=en_US.UTF-8


# systemctl stop SuSEfirewall2

cd ${rootPath}/scripts && bash lib.sh
chmod 755 ${rootPath}/data

if [ -f /etc/rc.d/init.d/mit ];then
    bash /etc/rc.d/init.d/mit stop && rm -rf ${rootPath}/scripts/init.d/mit && rm -rf /etc/rc.d/init.d/mit
fi

echo -e "start mit"
cd ${rootPath} && bash cli.sh start
isStart=`ps -ef|grep 'gunicorn -c setting.py app:app' |grep -v grep|awk '{print $2}'`
n=0
while [[ ! -f /etc/rc.d/init.d/mit ]];
do
    echo -e ".\c"
    sleep 1
    let n+=1
    if [ $n -gt 20 ];then
        echo -e "start mit fail"
        exit 1
    fi
done
echo -e "start mit success"

cd ${rootPath} && bash /etc/rc.d/init.d/mit stop
cd ${rootPath} && bash /etc/rc.d/init.d/mit start
