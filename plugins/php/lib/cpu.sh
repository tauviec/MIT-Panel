#!/bin/bash
# Sets cpuCore: parallel make jobs for building PHP and its libraries.
# Same rule as versions/*/install.sh: min(cpu count, RAM in GB), then 80%.
# Usage: source "$(cd "$(dirname "$0")"; pwd)/cpu.sh"   (or the lib/ path)

if [ -z "${cpuCore}" ]; then
	cpuCore="1"
	if [ -f /proc/cpuinfo ];then
		cpuCore=`grep -c "processor" /proc/cpuinfo`
	elif [ "$(uname)" == "Darwin" ];then
		cpuCore=`sysctl -n hw.ncpu 2>/dev/null || echo 1`
	fi

	MEM_INFO=$(which free > /dev/null 2>&1 && free -m|grep Mem|awk '{printf("%.f",($2)/1024)}')
	if [ "${cpuCore}" != "1" ] && [ "${MEM_INFO}" != "" ] && [ "${MEM_INFO}" != "0" ];then
		if [ "${cpuCore}" -gt "${MEM_INFO}" ];then
			cpuCore="${MEM_INFO}"
		fi
	elif [ "${MEM_INFO}" == "0" ];then
		cpuCore="1"
	fi

	if [ "$cpuCore" -gt "2" ];then
		cpuCore=`echo "$cpuCore" | awk '{printf("%.f",($1)*0.8)}'`
	fi
fi
export cpuCore
