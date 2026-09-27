# coding: utf-8

# Service watchdog, run every minute by task.py:
#   - restarts the web server (Nginx/Apache), MySQL, MariaDB and PHP-FPM when
#     systemd reports them "failed" (at most MAX_RESTARTS per service per hour,
#     so a service that keeps crashing is not restarted forever),
#   - warns when a disk is almost full or memory is almost exhausted,
#   - logs everything to logs/watchdog.log, the panel log and the notify channel.
#
# Disable it by creating data/watchdog_off.pl

import os
import re
import time
import json

import mit

MAX_RESTARTS = 3
WINDOW = 3600
DISK_WARN = 90
DISK_CRIT = 95
MEM_WARN = 95


def stateFile():
    return mit.getRunDir() + '/data/watchdog_state.json'


def logFile():
    return mit.getRunDir() + '/logs/watchdog.log'


def isEnabled():
    return not os.path.exists(mit.getRunDir() + '/data/watchdog_off.pl')


def log(msg, notify=False, key='watchdog'):
    line = time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + msg + '\n'
    try:
        mit.writeFile(logFile(), line, 'a+')
    except Exception:
        pass
    mit.writeLog('Watchdog', msg)
    if notify:
        # notifyMessage limits repeats of the same type itself (trigger_time)
        mit.notifyMessage('[MIT Panel Watchdog] ' + msg, 'watchdog_' + key, 3600, False)


def loadState():
    try:
        return json.loads(mit.readFile(stateFile()))
    except Exception:
        return {}


def saveState(state):
    mit.writeFile(stateFile(), json.dumps(state))


def confValue(conf, key):
    content = mit.readFile(conf)
    if not content:
        return ''
    m = re.search(r'(?m)^\s*' + key + r'\s*=\s*(.+)$', content)
    return m.groups()[0].strip() if m else ''


# ------------------------------ services ------------------------------
# systemd state decides: "failed" = crashed / OOM-killed / systemd gave up
# restarting it -> the watchdog steps in. "inactive" = stopped on purpose by
# the admin -> left alone.

def serviceState(name):
    return mit.execShell('systemctl is-active ' + name)[0].strip()


def hasUnit(name):
    return os.path.exists(mit.systemdCfgDir() + '/' + name + '.service')


def services():
    '''(systemd unit, title, log hint) of installed services'''
    sdir = mit.getServerDir()
    items = []

    if mit.isInstalledWeb():
        name = 'apache' if mit.isApache() else 'openresty'
        err_log = sdir + ('/apache/logs/error_log' if mit.isApache() else '/openresty/nginx/logs/error.log')
        items.append((name, mit.getWebServerTitle(), err_log))

    for name, title in [('mysql', 'MySQL'), ('mariadb', 'MariaDB')]:
        conf = sdir + '/' + name + '/etc/my.cnf'
        if os.path.exists(conf):
            items.append((name, title, confValue(conf, 'log-error') or (sdir + '/' + name + '/data')))

    php_dir = sdir + '/php'
    if os.path.exists(php_dir):
        for v in sorted(os.listdir(php_dir)):
            if v.isdigit() and os.path.exists(php_dir + '/' + v + '/sbin/php-fpm'):
                items.append(('php' + v, 'PHP-' + v, php_dir + '/' + v + '/var/log/php-fpm.log'))

    return [i for i in items if hasUnit(i[0])]


def checkServices(state):
    now = int(time.time())
    for name, title, err_log in services():
        if serviceState(name) != 'failed':
            continue

        hist = [t for t in state.get(name, []) if now - t < WINDOW]
        if len(hist) >= MAX_RESTARTS:
            if state.get(name + '_gaveup', 0) < now - WINDOW:
                log('%s crash dan sudah %d kali di-restart dalam 1 jam; restart otomatis dihentikan. '
                    'Periksa log: %s' % (title, MAX_RESTARTS, err_log), True, name)
                state[name + '_gaveup'] = now
            state[name] = hist
            continue

        mit.execShell('systemctl reset-failed ' + name)
        mit.execShell('systemctl start ' + name)
        time.sleep(5)
        hist.append(now)
        state[name] = hist
        if serviceState(name) == 'active':
            log('%s crash, berhasil di-restart otomatis (%d/%d dalam 1 jam).' % (title, len(hist), MAX_RESTARTS), True, name)
        else:
            log('%s crash dan GAGAL di-restart (%d/%d). Periksa log: %s' % (title, len(hist), MAX_RESTARTS, err_log), True, name)


# ------------------------------ resources ------------------------------

def checkDisks(state):
    now = int(time.time())
    paths = ['/', mit.getRootDir(), mit.getServerDir()]
    seen = []
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            st = os.statvfs(p)
        except Exception:
            continue
        dev = (st.f_blocks, st.f_bsize)
        if dev in seen or st.f_blocks == 0:
            continue
        seen.append(dev)
        used = 100.0 * (st.f_blocks - st.f_bavail) / st.f_blocks
        free_gb = st.f_bavail * st.f_frsize / 1024.0 ** 3
        key = 'disk_' + p
        if used >= DISK_WARN and now - state.get(key, 0) > 6 * 3600:
            level = 'KRITIS' if used >= DISK_CRIT else 'Peringatan'
            log('%s: disk %s terpakai %.0f%% (sisa %.1fGB). Disk penuh bisa merusak database MySQL/MariaDB.'
                % (level, p, used, free_gb), True, 'disk')
            state[key] = now


def checkMemory(state):
    now = int(time.time())
    try:
        info = {}
        for line in open('/proc/meminfo'):
            k, v = line.split(':', 1)
            info[k] = int(v.split()[0])
        total = info['MemTotal']
        avail = info.get('MemAvailable', info.get('MemFree', 0))
        swap_total = info.get('SwapTotal', 0)
        swap_free = info.get('SwapFree', 0)
    except Exception:
        return
    used = 100.0 * (total - avail) / total
    if used >= MEM_WARN and now - state.get('mem', 0) > 6 * 3600:
        swap = ''
        if swap_total > 0:
            swap = ', swap terpakai %.0f%%' % (100.0 * (swap_total - swap_free) / swap_total)
        log('Peringatan: RAM terpakai %.0f%%%s. Risiko OOM (layanan dimatikan kernel). '
            'Turunkan tuning MySQL/MariaDB atau tambah RAM/swap.' % (used, swap), True, 'mem')
        state['mem'] = now


def run():
    if not isEnabled():
        return
    state = loadState()
    try:
        checkServices(state)
        checkDisks(state)
        checkMemory(state)
    finally:
        saveState(state)
