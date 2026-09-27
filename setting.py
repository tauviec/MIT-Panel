from gevent import monkey
monkey.patch_all()

# coding:utf-8

import time
import sys
import random
import os

pwd = os.getcwd()
sys.path.append(pwd + '/class/core')

import mit

import system_api
cpu_info = system_api.system_api().getCpuInfo()
workers = cpu_info[1]


log_dir = os.getcwd() + '/logs'
if not os.path.exists(log_dir):
    os.mkdir(log_dir)

# default port
mit_port = "7200"
if os.path.exists("data/port.pl"):
    mit_port = mit.readFile('data/port.pl')
    mit_port.strip()
else:
    import firewall_api
    import common
    common.initDB()
    mit_port = str(random.randint(10000, 65530))
    firewall_api.firewall_api().addAcceptPortArgs(mit_port, 'WEB panel', 'port')
    mit.writeFile('data/port.pl', mit_port)

bind = []
if os.path.exists('data/ipv6.pl'):
    bind.append('[0:0:0:0:0:0:0:0]:%s' % mit_port)
else:
    bind.append('0.0.0.0:%s' % mit_port)

if not os.path.exists('data/admin_path.pl'):
    admin_path = mit.getRandomString(8)
    mit.writeFile('data/admin_path.pl', '/' + admin_path.lower())

if workers > 2:
    workers = 1

threads = workers * 1
backlog = 512
reload = False
daemon = True
worker_class = 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker'
timeout = 7200
keepalive = 60
preload_app = True
capture_output = True
access_log_format = '%(t)s %(p)s %(h)s "%(r)s" %(s)s %(L)s %(b)s %(f)s" "%(a)s"'
loglevel = 'info'
errorlog = log_dir + '/error.log'
accesslog = log_dir + '/access.log'
pidfile = log_dir + '/mit.pid'
