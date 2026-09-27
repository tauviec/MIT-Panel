#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin:/opt/homebrew/bin
export PATH

if [ -z "$rootPath" ]; then
    DIR=$(cd "$(dirname "$0")"; pwd)
    rootPath=$(dirname "$(dirname "$(dirname "$(dirname "$DIR")")")")
    serverPath=$(dirname "$rootPath")
fi

sysName=`uname`
action=$1
type=$2

# First version that downloads is used; archive.apache.org keeps every release
HTTPD_VERSIONS="2.4.65 2.4.64 2.4.63 2.4.62"
APR_VERSIONS="1.7.6 1.7.5 1.7.4"
APR_UTIL_VERSIONS="1.6.3"

apacheDir=${serverPath}/source/apache

download()
{
	# download <name> <versions> <url-prefix>; prints the version that worked
	local name=$1
	local versions=$2
	local prefix=$3
	for v in $versions; do
		local file=${apacheDir}/${name}-${v}.tar.gz
		if [ ! -s $file ];then
			wget --no-check-certificate -O $file ${prefix}/${name}-${v}.tar.gz -T 30 >/dev/null 2>&1
		fi
		if [ -s $file ] && tar -tzf $file >/dev/null 2>&1;then
			echo $v
			return 0
		fi
		rm -f $file
	done
	return 1
}

Install_deps()
{
	if [ "$sysName" == "Darwin" ]; then
		brew install pcre2 openssl@3 expat nghttp2
		return
	fi

	if [ -f /usr/bin/apt-get ]; then
		export DEBIAN_FRONTEND=noninteractive
		apt-get update -y
		apt-get install -y build-essential wget libpcre2-dev libssl-dev libexpat1-dev zlib1g-dev libnghttp2-dev libbrotli-dev pkg-config
	elif [ -f /usr/bin/dnf ]; then
		dnf install -y gcc gcc-c++ make wget pcre2-devel openssl-devel expat-devel zlib-devel libnghttp2-devel brotli-devel pkgconfig perl
	elif [ -f /usr/bin/yum ]; then
		yum install -y gcc gcc-c++ make wget pcre2-devel openssl-devel expat-devel zlib-devel libnghttp2-devel brotli-devel pkgconfig perl
	elif [ -f /usr/bin/pacman ]; then
		pacman -Sy --noconfirm base-devel wget pcre2 openssl expat zlib libnghttp2 brotli pkgconf
	elif [ -f /usr/bin/zypper ]; then
		zypper install -y gcc gcc-c++ make wget pcre2-devel libopenssl-devel libexpat-devel zlib-devel libnghttp2-devel pkg-config
	fi
}

Install_apache()
{
	if [ "${action}" == "install" ];then
		if [ -f $serverPath/apache/bin/httpd ];then
			exit 0
		fi
	fi

	# ----- cpu start ------
	cpuCore="1"
	if [ -f /proc/cpuinfo ];then
		cpuCore=`cat /proc/cpuinfo | grep "processor" | wc -l`
	elif [ "$sysName" == "Darwin" ];then
		cpuCore=`sysctl -n hw.ncpu`
	fi
	# ----- cpu end ------

	Install_deps

	mkdir -p ${apacheDir}
	echo 'Sedang mengunduh source Apache...'

	HTTPD_VERSION=`download httpd "$HTTPD_VERSIONS" https://archive.apache.org/dist/httpd`
	if [ "$HTTPD_VERSION" == "" ];then
		echo 'Failed to download Apache httpd source tarball!'
		exit 1
	fi
	APR_VERSION=`download apr "$APR_VERSIONS" https://archive.apache.org/dist/apr`
	APR_UTIL_VERSION=`download apr-util "$APR_UTIL_VERSIONS" https://archive.apache.org/dist/apr`
	if [ "$APR_VERSION" == "" ] || [ "$APR_UTIL_VERSION" == "" ];then
		echo 'Failed to download APR / APR-util source tarball!'
		exit 1
	fi
	echo "httpd ${HTTPD_VERSION}, apr ${APR_VERSION}, apr-util ${APR_UTIL_VERSION}"

	cd ${apacheDir} && rm -rf httpd-${HTTPD_VERSION} && tar -zxf httpd-${HTTPD_VERSION}.tar.gz
	cd ${apacheDir} && tar -zxf apr-${APR_VERSION}.tar.gz && tar -zxf apr-util-${APR_UTIL_VERSION}.tar.gz
	rm -rf ${apacheDir}/httpd-${HTTPD_VERSION}/srclib/apr ${apacheDir}/httpd-${HTTPD_VERSION}/srclib/apr-util
	mv ${apacheDir}/apr-${APR_VERSION} ${apacheDir}/httpd-${HTTPD_VERSION}/srclib/apr
	mv ${apacheDir}/apr-util-${APR_UTIL_VERSION} ${apacheDir}/httpd-${HTTPD_VERSION}/srclib/apr-util

	OPTIONS=''
	PCRE_CONFIG=`which pcre2-config 2>/dev/null`
	if [ "$sysName" == "Darwin" ];then
		BREW_DIR=`brew --prefix`
		PCRE_CONFIG=${BREW_DIR}/opt/pcre2/bin/pcre2-config
		OPTIONS="${OPTIONS} --with-ssl=${BREW_DIR}/opt/openssl@3"
		OPTIONS="${OPTIONS} --with-expat=${BREW_DIR}/opt/expat"
		OPTIONS="${OPTIONS} --with-nghttp2=${BREW_DIR}/opt/nghttp2 --enable-http2=shared"
	else
		OPTIONS="${OPTIONS} --with-ssl"
		# mod_http2 only when libnghttp2 headers are present, otherwise configure fails
		if pkg-config --exists libnghttp2 2>/dev/null || [ -f /usr/include/nghttp2/nghttp2.h ];then
			OPTIONS="${OPTIONS} --enable-http2=shared"
		fi
		if pkg-config --exists libbrotlienc 2>/dev/null;then
			OPTIONS="${OPTIONS} --enable-brotli=shared"
		fi
	fi
	if [ "$PCRE_CONFIG" != "" ];then
		OPTIONS="${OPTIONS} --with-pcre=${PCRE_CONFIG}"
	fi

	cd ${apacheDir}/httpd-${HTTPD_VERSION} && ./configure \
		--prefix=$serverPath/apache \
		--with-included-apr \
		--enable-so \
		--enable-mods-shared=most \
		--enable-mpms-shared=all \
		--with-mpm=event \
		--enable-ssl=shared \
		--enable-rewrite=shared \
		--enable-headers=shared \
		--enable-expires=shared \
		--enable-deflate=shared \
		--enable-proxy=shared \
		--enable-proxy-http=shared \
		--enable-proxy-fcgi=shared \
		--enable-proxy-wstunnel=shared \
		--enable-remoteip=shared \
		--enable-ratelimit=shared \
		--enable-socache-shmcb=shared \
		--enable-status=shared \
		$OPTIONS

	make -j${cpuCore} && make install

	if [ ! -f $serverPath/apache/bin/httpd ];then
		echo 'Apache compile failed!'
		exit 1
	fi

	echo "${HTTPD_VERSION}" > $serverPath/apache/httpd_version.pl

	mkdir -p $serverPath/web_conf/apache/vhost
	mkdir -p $serverPath/web_conf/php/apache

	# keep the source tree small, the tarballs stay for a rebuild
	rm -rf ${apacheDir}/httpd-${HTTPD_VERSION}
	echo 'Apache terpasang!'
}

Uninstall_apache()
{
	rm -rf $serverPath/apache
	echo 'Apache dihapus!'
}

action=$1
if [ "${1}" == 'install' ];then
	Install_apache
elif [ "${1}" == 'upgrade' ];then
	rm -f $serverPath/apache/bin/httpd.old
	[ -f $serverPath/apache/bin/httpd ] && mv $serverPath/apache/bin/httpd $serverPath/apache/bin/httpd.old
	action=install
	Install_apache
else
	Uninstall_apache
fi
