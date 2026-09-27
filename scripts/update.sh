#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin:/opt/homebrew/bin
export PATH
# LANG=en_US.UTF-8
is64bit=`getconf LONG_BIT`

startTime=`date +%s`

# Path detection
OSNAME=$(uname -s)
if [ "$OSNAME" == "Darwin" ]; then
    DIR=$(cd "$(dirname "$0")"; pwd)
    export rootPath=$(dirname "$DIR")
    export serverPath=$(dirname "$rootPath")
else
    export rootPath="/opt/mit/server/panel"
    export serverPath="/opt/mit/server"
fi

_os=`uname`
echo "menggunakan sistem: ${_os}"

if [ "$EUID" -ne 0 ]
  then echo "Harap jalankan sebagai root!"
  exit
fi

if [ ${_os} != "Darwin" ] && [ ! -d ${rootPath}/logs ]; then
    mkdir -p ${rootPath}/logs
fi

LOG_FILE=/var/log/mit-update.log
{

HTTP_PREFIX="https://"

if [ ${_os} == "Darwin" ]; then
    OSNAME='macos'
elif grep -Eqi "openSUSE" /etc/*-release; then
    OSNAME='opensuse'
    zypper refresh
elif grep -Eqi "EulerOS" /etc/*-release || grep -Eqi "openEuler" /etc/*-release; then
    OSNAME='euler'
elif grep -Eqi "FreeBSD" /etc/*-release; then
    OSNAME='freebsd'
elif grep -Eqi "CentOS" /etc/issue || grep -Eqi "CentOS" /etc/*-release; then
    OSNAME='rhel'
    yum install -y wget zip unzip
elif grep -Eqi "Fedora" /etc/issue || grep -Eqi "Fedora" /etc/*-release; then
    OSNAME='rhel'
    yum install -y wget zip unzip
elif grep -Eqi "Rocky" /etc/issue || grep -Eqi "Rocky" /etc/*-release; then
    OSNAME='rhel'
    yum install -y wget zip unzip
elif grep -Eqi "AlmaLinux" /etc/issue || grep -Eqi "AlmaLinux" /etc/*-release; then
    OSNAME='rhel'
    yum install -y wget zip unzip
elif grep -Eqi "Anolis" /etc/issue || grep -Eqi "Anolis" /etc/*-release; then
    OSNAME='rhel'
    yum install -y wget curl zip unzip tar crontabs
elif grep -Eqi "Amazon Linux" /etc/issue || grep -Eqi "Amazon Linux" /etc/*-release; then
    OSNAME='amazon'
    yum install -y wget zip unzip
elif grep -Eqi "Ubuntu" /etc/issue || grep -Eqi "Ubuntu" /etc/*-release; then
    OSNAME='ubuntu'
    apt install -y wget zip unzip
elif grep -Eqi "Debian" /etc/issue || grep -Eqi "Debian" /etc/*-release; then
    OSNAME='debian'
    apt install -y wget zip unzip
elif grep -Eqi "Raspbian" /etc/issue || grep -Eqi "Raspbian" /etc/*-release; then
    OSNAME='raspbian'
elif grep -Eqi "Alpine" /etc/issue || grep -Eqi "Alpine" /etc/*-release; then
    OSNAME='alpine'
    apk update
    apk add devscripts -force-broken-world
    apk add wget zip unzip tar -force-broken-world
else
    OSNAME='unknow'
fi

CP_CMD=/usr/bin/cp
if [ -f /bin/cp ];then
        CP_CMD=/bin/cp
fi

echo "mulai pembaruan kode panel"

MIT_REPO=${MIT_REPO:-https://github.com/tauviec/MIT-Panel}
MIT_BRANCH=${MIT_BRANCH:-main}
rm -rf /tmp/mit-src && mkdir -p /tmp/mit-src
curl --insecure -fsSLo /tmp/mit-src.tar.gz ${MIT_REPO}/archive/refs/heads/${MIT_BRANCH}.tar.gz
tar -zxf /tmp/mit-src.tar.gz -C /tmp/mit-src --strip-components=1
$CP_CMD -rf /tmp/mit-src/* ${rootPath}
find ${rootPath} -type f \( -name "*.sh" -o -name "*.tpl" \) -exec sed -i 's/\r$//' {} +
rm -rf /tmp/mit-src.tar.gz /tmp/mit-src

echo "pembaruan kode panel selesai"


#pip uninstall public
echo "menggunakan versi sistem: ${OSNAME}"
cd ${rootPath} && bash scripts/update/${OSNAME}.sh

bash /etc/rc.d/init.d/mit restart
bash /etc/rc.d/init.d/mit default

if [ -f /usr/bin/mit ];then
    rm -rf /usr/bin/mit
fi

if [ ! -e /usr/bin/mit ]; then
    if [ ! -f /usr/bin/mit ];then
        ln -s /etc/rc.d/init.d/mit /usr/bin/mit
    fi
fi

endTime=`date +%s`
((outTime=($endTime-$startTime)/60))
echo -e "Waktu yang dihabiskan:\033[32m $outTime \033[0mMenit!"

} 1> >(tee $LOG_FILE) 2>&1