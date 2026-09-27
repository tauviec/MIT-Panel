# coding: utf-8

import os
import sys
import time
import string
import json
import hashlib
import shlex
import datetime
import subprocess
import re
import hashlib
from random import Random

import mit
import db

from flask import redirect


def init():
    initDB()
    initDBSshPort()
    initUserInfo()
    initInitD()
    initInitTask()


def local():
    result = checkClose()
    if result:
        return result


def checkClose():
    if os.path.exists('data/close.pl'):
        return redirect('/close')


def initDB():
    try:
        sql = db.Sql().dbfile('default')
        csql = mit.readFile('data/sql/default.sql')
        csql_list = csql.split(';')
        for index in range(len(csql_list)):
            sql.execute(csql_list[index], ())

    except Exception as ex:
        print(str(ex))

def initDBSshPort():
    import firewall_api
    cmd_data = mit.execShell(
        r"cat /etc/ssh/sshd_config | grep '^Port \d*' | tail -1")
    ssh_port = cmd_data[0].replace("Port ", '').strip()
    if ssh_port == '':
        ssh_port = '22'
    firewall_api.firewall_api().addAcceptPortArgs(ssh_port, 'SSH remote management service', 'port')


def doContentReplace(src, dst):
    content = mit.readFile(src)
    content = content.replace("{$SERVER_PATH}", mit.getRunDir())
    mit.writeFile(dst, content)


def initInitD():

    # systemctl
    # sysCfgDir = mit.systemdCfgDir()
    # if os.path.exists(sysCfgDir) and mit.getOsName() == 'centos' and mit.getOsID() == '9':
    #     systemd_mit = sysCfgDir + '/mit.service'
    #     systemd_mit_task = sysCfgDir + '/mit-task.service'

    #     systemd_mit_tpl = mit.getRunDir() + '/scripts/init.d/mit.service.tpl'
    #     systemd_mit_task_tpl = mit.getRunDir() + '/scripts/init.d/mit-task.service.tpl'

    #     if os.path.exists(systemd_mit):
    #         os.remove(systemd_mit)
    #     if os.path.exists(systemd_mit_task):
    #         os.remove(systemd_mit_task)

    #     doContentReplace(systemd_mit_tpl, systemd_mit)
    #     doContentReplace(systemd_mit_task_tpl, systemd_mit_task)

    #     mit.execShell('systemctl enable mit')
    #     mit.execShell('systemctl enable mit-task')
    #     mit.execShell('systemctl daemon-reload')

    script = mit.getRunDir() + '/scripts/init.d/mit.tpl'
    script_bin = mit.getRunDir() + '/scripts/init.d/mit'
    doContentReplace(script, script_bin)
    mit.execShell('chmod +x ' + script_bin)

    if not mit.isAppleSystem() and not os.path.exists("/etc/rc.d/init.d"):
        mit.execShell('mkdir -p /etc/rc.d/init.d')

    if not mit.isAppleSystem() and not os.path.exists("/etc/init.d"):
        mit.execShell('mkdir -p /etc/init.d')

    # initd
    if os.path.exists('/etc/rc.d/init.d'):
        initd_bin = '/etc/rc.d/init.d/mit'
        if not os.path.exists(initd_bin):
            import shutil
            shutil.copyfile(script_bin, initd_bin)
            mit.execShell('chmod +x ' + initd_bin)
        mit.execShell('which chkconfig && chkconfig --add mit')

    if os.path.exists('/etc/init.d'):
        initd_bin = '/etc/init.d/mit'
        if not os.path.exists(initd_bin):
            import shutil
            shutil.copyfile(script_bin, initd_bin)
            mit.execShell('chmod +x ' + initd_bin)
        mit.execShell('which update-rc.d && update-rc.d -f mit defaults')

    mit.setHostAddr(mit.getLocalIp())


def initInitTask():
    import cert_api
    api = cert_api.cert_api()
    api.createCertCron()


def initUserInfo():

    data = mit.M('users').where('id=?', (1,)).getField('password')
    if data == '21232f297a57a5a743894a0e4a801fc3':
        pwd = mit.getRandomString(8).lower()
        file_pw = mit.getRunDir() + '/data/default.pl'
        mit.writeFile(file_pw, pwd)
        mit.M('users').where('id=?', (1,)).setField(
            'password', mit.md5(pwd))
