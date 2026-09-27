#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin:/opt/homebrew/bin
export PATH

DIR=$(cd "$(dirname "$0")"; pwd)
curPath=$DIR
rootPath=$(dirname "$(dirname "$DIR")")
serverPath=$(dirname "$rootPath")
export rootPath
export serverPath

sysName=`uname`
action=$1
type=$2

VERSION=$2

if id www &> /dev/null ;then
    echo "www uid is `id -u www`"
    echo "www shell is `grep "^www:" /etc/passwd |cut -d':' -f7 `"
else
    groupadd www
	useradd -g www -s /bin/bash www
fi

if [ "${2}" == "" ];then
	echo 'Versi skrip instalasi tidak ditemukan...'
	exit 0
fi

if [ "${action}" == "uninstall" ];then
	if [ -f /usr/lib/systemd/system/apache.service ] || [ -f /lib/systemd/system/apache.service ];then
		systemctl stop apache
		systemctl disable apache
		rm -rf /usr/lib/systemd/system/apache.service
		rm -rf /lib/systemd/system/apache.service
		systemctl daemon-reload
	fi

	if [ -f $serverPath/apache/init.d/apache ];then
		$serverPath/apache/init.d/apache stop
	fi

	rm -rf $serverPath/apache
	echo "Apache uninstalled (site configs are kept in $serverPath/web_conf/apache)"
	exit 0
fi

# Like aaPanel only one web server may run: both want port 80/443
if [ "${action}" == "install" ] && [ -d $serverPath/openresty ];then
	echo 'OpenResty is installed. Uninstall OpenResty first, then install Apache.'
	exit 1
fi

bash -x $DIR/versions/$2/install.sh $1

if [ "${action}" == "install" ] && [ -f $serverPath/apache/bin/httpd ];then
	echo "${VERSION}" > $serverPath/apache/version.pl

	#Inisialisasi
	cd ${rootPath} && python3 ${rootPath}/plugins/apache/index.py start
	cd ${rootPath} && python3 ${rootPath}/plugins/apache/index.py initd_install
fi
