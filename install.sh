#!/bin/bash
# MIT Panel - one-step installer (Linux, including Linux Mint / desktop distros)
#
#   From a copied folder :  sudo bash install.sh
#   From the internet    :  curl -fsSL https://raw.githubusercontent.com/tauviec/MIT-Panel/main/install.sh | sudo bash
#
# Windows: run install-windows.ps1 (installs through WSL2 + Ubuntu)

if [ "$(uname)" != "Darwin" ] && [ "$EUID" -ne 0 ];then
	echo "Jalankan sebagai root: sudo bash install.sh"
	exit 1
fi

DIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd)
if [ -f "$DIR/scripts/install.sh" ];then
	exec bash "$DIR/scripts/install.sh" "$@"
fi

MIT_REPO_RAW=${MIT_REPO_RAW:-https://raw.githubusercontent.com/tauviec/MIT-Panel/${MIT_BRANCH:-main}}
curl -fsSL ${MIT_REPO_RAW}/scripts/install.sh -o /tmp/mit-install.sh || {
	echo "Gagal mengunduh installer dari ${MIT_REPO_RAW}"
	exit 1
}
exec bash /tmp/mit-install.sh "$@"
