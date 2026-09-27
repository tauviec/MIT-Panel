#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin:/opt/homebrew/bin
export PATH

DIR=$(cd "$(dirname "$0")"; pwd)
curPath=$DIR
rootPath=$(dirname "$(dirname "$DIR")")
serverPath=$(dirname "$rootPath")
export rootPath
export serverPath

# cd ${rootPath}/plugins/redis && bash install.sh install 7.4
# cd ${rootPath}/plugins/redis && bash install.sh uninstall 7.4

action=$1
VERSION=$2
sysName=`uname`

redisDir=${serverPath}/redis
sourceDir=${serverPath}/source/redis

# fallback when the release index cannot be read
Pinned()
{
	case "$1" in
		'7.2') echo '7.2.12';;
		'7.4') echo '7.4.7';;
		'8.0') echo '8.0.5';;
		'8.2') echo '8.2.3';;
		'8.4') echo '8.4.1';;
	esac
}

if [ -f ${rootPath}/bin/activate ];then
	source ${rootPath}/bin/activate
fi

Install_Deps()
{
	if command -v apt-get >/dev/null 2>&1; then
		export DEBIAN_FRONTEND=noninteractive
		apt-get install -y gcc make pkg-config libssl-dev curl tar
	elif command -v dnf >/dev/null 2>&1; then
		dnf install -y gcc make pkgconfig openssl-devel curl tar
	elif command -v yum >/dev/null 2>&1; then
		yum install -y gcc make pkgconfig openssl-devel curl tar
	elif command -v zypper >/dev/null 2>&1; then
		zypper --non-interactive install gcc make pkg-config libopenssl-devel curl tar
	elif command -v pacman >/dev/null 2>&1; then
		pacman -S --noconfirm --needed gcc make pkgconf openssl curl tar
	fi
}

Latest_Patch()
{
	local minor=$1
	local latest
	latest=$(curl -fsSL --max-time 30 https://download.redis.io/releases/ 2>/dev/null \
		| grep -oE "redis-${minor//./\\.}\.[0-9]+\.tar\.gz" \
		| sed -e 's/^redis-//' -e 's/\.tar\.gz$//' \
		| sort -uV | tail -1)
	if [ "$latest" == "" ];then
		latest=$(Pinned $minor)
	fi
	echo $latest
}

Cpu_Core()
{
	cpuCore=1
	if [ -f /proc/cpuinfo ];then
		cpuCore=`grep -c "processor" /proc/cpuinfo`
	fi
	if [ "$cpuCore" -gt "2" ];then
		cpuCore=`echo "$cpuCore" | awk '{printf("%.f",($1)*0.8)}'`
	else
		cpuCore=1
	fi
}

Install_App()
{
	if [ -f ${redisDir}/bin/redis-server ];then
		echo "Redis sudah terpasang di ${redisDir}"
		exit 0
	fi

	echo '[1/5] Memasang dependensi build...'
	Install_Deps

	REDIS_VER=$(Latest_Patch $VERSION)
	if [ "$REDIS_VER" == "" ];then
		echo "Versi Redis ${VERSION} tidak dikenal"
		echo 'install fail' >&2
		exit 1
	fi

	echo "[2/5] Mengunduh redis-${REDIS_VER}..."
	mkdir -p ${sourceDir}
	if [ ! -f ${sourceDir}/redis-${REDIS_VER}.tar.gz ];then
		curl -fSL --retry 3 --connect-timeout 30 -o ${sourceDir}/redis-${REDIS_VER}.tar.gz \
			https://download.redis.io/releases/redis-${REDIS_VER}.tar.gz
	fi
	if ! tar -tzf ${sourceDir}/redis-${REDIS_VER}.tar.gz >/dev/null 2>&1; then
		rm -f ${sourceDir}/redis-${REDIS_VER}.tar.gz
		echo 'Unduhan Redis gagal'
		echo 'install fail' >&2
		exit 1
	fi
	rm -rf ${sourceDir}/redis-${REDIS_VER}
	cd ${sourceDir} && tar -zxf redis-${REDIS_VER}.tar.gz

	echo "[3/5] Mengompilasi redis-${REDIS_VER}..."
	Cpu_Core
	cd ${sourceDir}/redis-${REDIS_VER}
	if ! make -j${cpuCore} BUILD_TLS=yes; then
		echo 'Kompilasi Redis gagal'
		echo 'install fail' >&2
		exit 1
	fi
	make PREFIX=${redisDir} install

	if [ ! -f ${redisDir}/bin/redis-server ];then
		echo 'Instalasi gagal'
		echo 'install fail' >&2
		exit 1
	fi

	echo '[4/5] Konfigurasi...'
	if [ "$sysName" != "Darwin" ] && ! id redis >/dev/null 2>&1; then
		groupadd -r redis 2>/dev/null
		useradd -r -g redis -s /usr/sbin/nologin -d ${redisDir} redis 2>/dev/null \
			|| useradd -r -g redis -s /sbin/nologin -d ${redisDir} redis
	fi

	mkdir -p ${redisDir}/data
	if [ ! -f ${redisDir}/redis.conf ];then
		REDIS_PASS=`cat /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 16`
		sed -e "s#{\$SERVER_PATH}#${redisDir}#g" -e "s#{\$REDIS_PASS}#${REDIS_PASS}#g" \
			${curPath}/conf/redis.conf > ${redisDir}/redis.conf
	fi
	touch ${redisDir}/redis.log
	echo "${VERSION}" > ${redisDir}/version.pl
	echo "${REDIS_VER}" > ${redisDir}/version_full.pl

	if [ "$sysName" != "Darwin" ];then
		chown -R redis:redis ${redisDir}/data ${redisDir}/redis.log ${redisDir}/redis.conf
		chmod 640 ${redisDir}/redis.conf
		chmod 750 ${redisDir}/data
		# recommended by Redis so background saves do not fail under memory pressure
		echo 'vm.overcommit_memory = 1' > /etc/sysctl.d/99-mit-redis.conf
		sysctl -w vm.overcommit_memory=1 >/dev/null 2>&1
	fi

	rm -rf ${sourceDir}/redis-${REDIS_VER}

	echo '[5/5] Menjalankan layanan...'
	cd ${rootPath} && python3 ${rootPath}/plugins/redis/index.py start
	cd ${rootPath} && python3 ${rootPath}/plugins/redis/index.py initd_install
	echo "Redis ${REDIS_VER} berhasil dipasang"
}

Uninstall_App()
{
	if [ -f /usr/lib/systemd/system/redis.service ] || [ -f /lib/systemd/system/redis.service ];then
		systemctl stop redis
		systemctl disable redis
		rm -f /usr/lib/systemd/system/redis.service
		rm -f /lib/systemd/system/redis.service
		systemctl daemon-reload
	fi

	if [ -f ${redisDir}/init.d/redis ];then
		${redisDir}/init.d/redis stop
	fi

	rm -f /etc/sysctl.d/99-mit-redis.conf
	rm -rf ${redisDir}
	echo 'Redis berhasil dihapus'
}

if [ "${action}" == "install" ];then
	if [ "$(Pinned ${VERSION})" == "" ];then
		echo "Versi Redis tidak didukung: ${VERSION}"
		exit 1
	fi
	Install_App
else
	Uninstall_App
fi
