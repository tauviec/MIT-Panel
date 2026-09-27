#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin:/opt/homebrew/bin
export PATH

#Dapatkan info dan versi
_os=`uname`
# Ubuntu/Debian derivatives (Linux Mint, LMDE, Pop!_OS, Zorin, elementary, KDE neon, ...)
# are installed with the packages of the distro they are built on
DERIVED=''
if [ -f /etc/os-release ];then
	OS_ID=$(. /etc/os-release; echo "$ID")
	OS_LIKE=$(. /etc/os-release; echo " $ID_LIKE ")
	if [ "$OS_ID" != "ubuntu" ] && [ "$OS_ID" != "debian" ];then
		if echo "$OS_LIKE" | grep -qi " ubuntu ";then
			DERIVED='ubuntu'
		elif echo "$OS_LIKE" | grep -qi " debian ";then
			DERIVED='debian'
		fi
	fi
fi

if [ ${_os} == "Darwin" ]; then
    OSNAME='macos'
elif [ "$DERIVED" != "" ]; then
    OSNAME=$DERIVED
elif grep -Eq "openSUSE" /etc/*-release; then
    OSNAME='opensuse'
elif grep -Eq "FreeBSD" /etc/*-release; then
    OSNAME='freebsd'
elif grep -Eqi "EulerOS" /etc/*-release || grep -Eqi "openEuler" /etc/*-release; then
    OSNAME='euler'
elif grep -Eqi "Arch" /etc/issue || grep -Eq "Arch" /etc/*-release; then
    OSNAME='arch'
elif grep -Eqi "CentOS" /etc/issue || grep -Eq "CentOS" /etc/*-release; then
    OSNAME='centos'
elif grep -Eqi "AlmaLinux" /etc/issue || grep -Eq "AlmaLinux" /etc/*-release; then
    OSNAME='alma'
elif grep -Eqi "Rocky" /etc/issue || grep -Eq "Rocky" /etc/*-release; then
    OSNAME='rocky'
elif grep -Eqi "Red Hat Enterprise Linux Server" /etc/issue || grep -Eq "Red Hat Enterprise Linux Server" /etc/*-release; then
    OSNAME='rhel'
elif grep -Eqi "Aliyun" /etc/issue || grep -Eq "Aliyun" /etc/*-release; then
    OSNAME='aliyun'
elif grep -Eqi "Fedora" /etc/issue || grep -Eq "Fedora" /etc/*-release; then
    OSNAME='fedora'
elif grep -Eqi "Amazon Linux AMI" /etc/issue || grep -Eq "Amazon Linux AMI" /etc/*-release; then
    OSNAME='amazon'
elif grep -Eqi "Debian" /etc/issue || grep -Eq "Debian" /etc/*-release; then
    OSNAME='debian'
elif grep -Eqi "Ubuntu" /etc/issue || grep -Eq "Ubuntu" /etc/*-release; then
    OSNAME='ubuntu'
elif grep -Eqi "Raspbian" /etc/issue || grep -Eq "Raspbian" /etc/*-release; then
    OSNAME='raspbian'
elif grep -Eqi "Deepin" /etc/issue || grep -Eq "Deepin" /etc/*-release; then
    OSNAME='deepin'
else
    OSNAME='unknow'
fi

if [ -d ${rootPath} ];then
    echo "$OSNAME" > ${rootPath}/data/osname.pl
fi

if [ "$OSNAME" == "macos" ];then
    echo "$OSNAME"
fi