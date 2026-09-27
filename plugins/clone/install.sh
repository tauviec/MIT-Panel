#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

DIR=$(cd "$(dirname "$0")"; pwd)
rootPath=$(dirname "$(dirname "$DIR")")
serverPath=$(dirname "$rootPath")

Install_clone()
{
	echo 'Memasang rsync dan sshpass...'
	if [ -f /usr/bin/apt-get ];then
		apt-get install -y rsync sshpass openssh-client
	elif [ -f /usr/bin/dnf ];then
		dnf install -y rsync sshpass openssh-clients
	elif [ -f /usr/bin/yum ];then
		yum install -y epel-release
		yum install -y rsync sshpass openssh-clients
	elif [ -f /usr/bin/pacman ];then
		pacman -Sy --noconfirm rsync sshpass openssh
	elif [ -f /usr/bin/zypper ];then
		zypper install -y rsync sshpass openssh
	fi
	mkdir -p $serverPath/clone
	echo "${1}" > $serverPath/clone/version.pl
	echo 'Clone Server terpasang'
}

Uninstall_clone()
{
	rm -rf $serverPath/clone
	echo 'Clone Server dihapus'
}

action=$1
if [ "${1}" == 'install' ];then
	Install_clone $2
else
	Uninstall_clone
fi
