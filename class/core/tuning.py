# coding: utf-8

# Memory-based tuning profiles for MySQL / MariaDB, Apache and Nginx (OpenResty),
# from 1GB up to 128GB+ of RAM. The panel usually runs web + PHP + database on the
# same machine, so the database never takes the whole memory.

import os
import re
import math
import time

import mit


# ------------------------------ system info ------------------------------

def memTotalMB():
    try:
        for line in open('/proc/meminfo'):
            if line.startswith('MemTotal:'):
                return int(line.split()[1]) // 1024
    except Exception:
        pass
    if mit.isAppleSystem():
        out = mit.execShell('sysctl -n hw.memsize')[0].strip()
        if out.isdigit():
            return int(out) // 1024 // 1024
    return 1024


def cpuCount():
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


# ------------------------------ MySQL / MariaDB ------------------------------
# Units follow the panel form: *_size in MB for the global buffers,
# KB for the per-connection buffers, plain numbers for counts.

DB_TIERS = [
    # (tier, label, lower bound GB, profile)
    ('1', '1-2GB', 1, dict(key_buffer_size=32, query_cache_size=32, tmp_table_size=64, innodb_buffer_pool_size=384,
                           innodb_log_buffer_size=16, max_connections=200, table_open_cache=512, thread_cache_size=32,
                           sort_buffer_size=512, read_buffer_size=256, read_rnd_buffer_size=512, join_buffer_size=512,
                           thread_stack=256, binlog_cache_size=32)),
    ('2', '2-4GB', 2, dict(key_buffer_size=64, query_cache_size=64, tmp_table_size=128, innodb_buffer_pool_size=1024,
                           innodb_log_buffer_size=32, max_connections=300, table_open_cache=1024, thread_cache_size=64,
                           sort_buffer_size=512, read_buffer_size=256, read_rnd_buffer_size=512, join_buffer_size=512,
                           thread_stack=256, binlog_cache_size=32)),
    ('3', '4-8GB', 4, dict(key_buffer_size=128, query_cache_size=128, tmp_table_size=256, innodb_buffer_pool_size=2048,
                           innodb_log_buffer_size=32, max_connections=500, table_open_cache=2048, thread_cache_size=128,
                           sort_buffer_size=512, read_buffer_size=256, read_rnd_buffer_size=512, join_buffer_size=512,
                           thread_stack=256, binlog_cache_size=32)),
    ('4', '8-16GB', 8, dict(key_buffer_size=256, query_cache_size=128, tmp_table_size=512, innodb_buffer_pool_size=4096,
                            innodb_log_buffer_size=64, max_connections=800, table_open_cache=4096, thread_cache_size=256,
                            sort_buffer_size=1024, read_buffer_size=512, read_rnd_buffer_size=1024, join_buffer_size=1024,
                            thread_stack=256, binlog_cache_size=64)),
    ('5', '16-32GB', 16, dict(key_buffer_size=256, query_cache_size=128, tmp_table_size=1024, innodb_buffer_pool_size=9216,
                              innodb_log_buffer_size=64, max_connections=1000, table_open_cache=8192, thread_cache_size=384,
                              sort_buffer_size=1024, read_buffer_size=512, read_rnd_buffer_size=1024, join_buffer_size=1024,
                              thread_stack=256, binlog_cache_size=64)),
    ('6', '32-64GB', 32, dict(key_buffer_size=512, query_cache_size=128, tmp_table_size=1024, innodb_buffer_pool_size=18432,
                              innodb_log_buffer_size=128, max_connections=1500, table_open_cache=16384, thread_cache_size=512,
                              sort_buffer_size=2048, read_buffer_size=1024, read_rnd_buffer_size=1024, join_buffer_size=2048,
                              thread_stack=512, binlog_cache_size=128)),
    ('7', '64-128GB', 64, dict(key_buffer_size=512, query_cache_size=128, tmp_table_size=2048, innodb_buffer_pool_size=36864,
                               innodb_log_buffer_size=128, max_connections=2000, table_open_cache=32768, thread_cache_size=768,
                               sort_buffer_size=2048, read_buffer_size=1024, read_rnd_buffer_size=1024, join_buffer_size=2048,
                               thread_stack=512, binlog_cache_size=128)),
    ('8', '128GB+', 128, dict(key_buffer_size=512, query_cache_size=128, tmp_table_size=2048, innodb_buffer_pool_size=73728,
                              innodb_log_buffer_size=256, max_connections=3000, table_open_cache=40000, thread_cache_size=1024,
                              sort_buffer_size=2048, read_buffer_size=1024, read_rnd_buffer_size=1024, join_buffer_size=2048,
                              thread_stack=512, binlog_cache_size=128)),
]

PER_CONN_KB = ['sort_buffer_size', 'read_buffer_size', 'read_rnd_buffer_size',
               'join_buffer_size', 'thread_stack', 'binlog_cache_size']
GLOBAL_MB = ['key_buffer_size', 'query_cache_size', 'tmp_table_size',
             'innodb_buffer_pool_size', 'innodb_log_buffer_size']


def dbEstimateMB(p, has_query_cache=True):
    '''worst case, same formula as the panel form'''
    a = sum([p[k] for k in GLOBAL_MB if has_query_cache or k != 'query_cache_size'])
    b = sum([p[k] for k in PER_CONN_KB]) / 1024.0
    return a + p['max_connections'] * b


def capConnections(p, ram_mb, has_query_cache=True, share=0.85):
    '''lower max_connections until the worst case fits in share * RAM'''
    budget = ram_mb * share
    per_conn = sum([p[k] for k in PER_CONN_KB]) / 1024.0
    glob = dbEstimateMB(dict(p, max_connections=0), has_query_cache)
    room = int((budget - glob) / per_conn) if per_conn > 0 else p['max_connections']
    p['max_connections'] = max(50, min(p['max_connections'], room))
    return p


def dbTierFor(ram_mb):
    gb = ram_mb / 1024.0
    chosen = DB_TIERS[0]
    for t in DB_TIERS:
        # tiers are chosen on the usable RAM (the kernel reports a bit less than the label)
        if gb >= t[2] * 0.9:
            chosen = t
    return chosen


def dbProfile(tier='auto', has_query_cache=True, ram_mb=None):
    '''tier: '1'..'8' or 'auto' (sized from the RAM of this server)'''
    if ram_mb is None:
        ram_mb = memTotalMB()

    if tier == 'auto':
        t = dbTierFor(ram_mb)
        p = dict(t[3])
        gb = ram_mb / 1024.0
        if gb < 2:
            ratio = 0.25
        elif gb < 8:
            ratio = 0.40
        elif gb < 32:
            ratio = 0.55
        else:
            ratio = 0.60
        p['innodb_buffer_pool_size'] = max(128, int(ram_mb * ratio) // 128 * 128)
        label = 'Auto (%s RAM)' % mit.toSize(ram_mb * 1024 * 1024)
        capConnections(p, ram_mb, has_query_cache)
    else:
        found = [t for t in DB_TIERS if t[0] == str(tier)]
        if not found:
            return None
        t = found[0]
        p = dict(t[3])
        label = t[1]
        # sized for the smallest machine of the tier
        capConnections(p, t[2] * 1024, has_query_cache)

    p['max_heap_table_size'] = p['tmp_table_size']
    if not has_query_cache:
        p['query_cache_size'] = 0
    return {'label': label, 'mem_total': ram_mb, 'estimate': int(dbEstimateMB(p, has_query_cache)), 'profile': p}


def dbTierList():
    return [{'tier': t[0], 'label': t[1]} for t in DB_TIERS]


def writeDbConf(content, args, gets):
    '''write the panel-form values into my.cnf content (same units as setDbStatus)'''
    emptys = ['max_connections', 'thread_cache_size', 'table_open_cache']
    n = 0
    for g in gets:
        s = 'M'
        if n > 5:
            s = 'K'
        if g in emptys:
            s = ''
        rep = r'\s*' + g + r'\s*=\s*\d+(M|K|k|m|G)?\n'
        c = g + ' = ' + str(args[g]) + s + '\n'
        if re.search(r'(?m)^\s*' + g + r'\s*=', content):
            content = re.sub(rep, '\n' + c, content, 1)
        else:
            content = content.replace('[mysqld]\n', '[mysqld]\n' + c)
        n += 1
    return content


def pidAlive(pid_file):
    pid = mit.readFile(pid_file)
    if not pid:
        return False
    try:
        os.kill(int(pid.strip()), 0)
        return True
    except Exception:
        return False


def applyWithRollback(conf_file, new_content, restart_fn, pid_file_fn, wait=60):
    '''write conf, restart, verify the process is up; restore + restart on failure'''
    old = mit.readFile(conf_file)
    backup = conf_file + '.tune_' + time.strftime('%Y%m%d%H%M%S') + '.bak'
    mit.writeFile(backup, old)
    mit.writeFile(conf_file, new_content)
    restart_fn()

    for i in range(wait):
        time.sleep(1)
        if pidAlive(pid_file_fn()):
            # stay up a few seconds: InnoDB fails late when the pool cannot be allocated
            time.sleep(5)
            if pidAlive(pid_file_fn()):
                return (True, backup)
            break

    mit.writeFile(conf_file, old)
    restart_fn()
    return (False, backup)


# ------------------------------ Apache (event MPM) ------------------------------

def apacheProfile(ram_mb=None, cpus=None):
    if ram_mb is None:
        ram_mb = memTotalMB()
    if cpus is None:
        cpus = cpuCount()
    gb = ram_mb / 1024.0

    # PHP runs in PHP-FPM, so Apache threads are light; the limit mostly
    # protects PHP-FPM and the database from floods
    steps = [(1, 150), (2, 250), (4, 400), (8, 800), (16, 1500), (32, 3000), (64, 5000), (1 << 30, 8000)]
    mrw = steps[-1][1]
    for limit, val in steps:
        if gb <= limit * 1.05:
            mrw = val
            break

    tpc = 25 if mrw <= 400 else 64
    server_limit = int(math.ceil(mrw / float(tpc)))
    mrw = server_limit * tpc
    start = max(2, min(server_limit, cpus // 2 if cpus > 3 else 2))
    min_spare = max(tpc, (mrw // 10) // tpc * tpc)
    max_spare = min_spare + 2 * tpc

    return {
        'label': 'Auto (%s RAM, %d CPU)' % (mit.toSize(ram_mb * 1024 * 1024), cpus),
        'mem_total': ram_mb,
        'profile': {
            'StartServers': start,
            'ServerLimit': server_limit,
            'ThreadLimit': max(64, tpc),
            'ThreadsPerChild': tpc,
            'MinSpareThreads': min_spare,
            'MaxSpareThreads': max_spare,
            'MaxRequestWorkers': mrw,
            'MaxConnectionsPerChild': 10000 if gb >= 4 else 0,
            'KeepAlive': 'On',
            'KeepAliveTimeout': 5,
            'MaxKeepAliveRequests': 1000 if gb >= 8 else 200,
            'Timeout': 120,
        }
    }


EVENT_KEYS = ['StartServers', 'ServerLimit', 'ThreadLimit', 'ThreadsPerChild', 'MinSpareThreads',
              'MaxSpareThreads', 'MaxRequestWorkers', 'MaxConnectionsPerChild']


def applyApacheProfile(content, p):
    m = re.search(r'<IfModule mpm_event_module>(?:.|\n)*?</IfModule>', content)
    if m:
        # ThreadLimit / ServerLimit must come before the values they bound
        block = '<IfModule mpm_event_module>\n'
        for k in ['ServerLimit', 'ThreadLimit'] + [x for x in EVENT_KEYS if x not in ('ServerLimit', 'ThreadLimit')]:
            block += '    %s %s\n' % (k, p[k])
        block += '</IfModule>'
        content = content.replace(m.group(), block, 1)
    for k in ['KeepAlive', 'KeepAliveTimeout', 'MaxKeepAliveRequests', 'Timeout']:
        content = re.sub(r'(?m)^(\s*)%s\s+\S+' % k, r'\g<1>%s %s' % (k, p[k]), content, 1)
    return content


# ------------------------------ Nginx (OpenResty) ------------------------------

def nginxProfile(ram_mb=None, cpus=None):
    if ram_mb is None:
        ram_mb = memTotalMB()
    if cpus is None:
        cpus = cpuCount()
    gb = ram_mb / 1024.0

    steps = [(1, 2048), (2, 4096), (4, 10240), (8, 20480), (16, 32768), (1 << 30, 65535)]
    wc = steps[-1][1]
    for limit, val in steps:
        if gb <= limit * 1.05:
            wc = val
            break

    if gb <= 4:
        cache_max = '1g'
    elif gb <= 16:
        cache_max = '2g'
    elif gb <= 64:
        cache_max = '8g'
    else:
        cache_max = '16g'

    return {
        'label': 'Auto (%s RAM, %d CPU)' % (mit.toSize(ram_mb * 1024 * 1024), cpus),
        'mem_total': ram_mb,
        'profile': {
            'worker_processes': 'auto',
            'worker_connections': wc,
            'worker_rlimit_nofile': min(wc * 2, 200000),
            'keepalive_timeout': 60,
            'proxy_cache_max_size': cache_max,
        }
    }


def applyNginxProfile(content, p):
    for k in ['worker_processes', 'worker_connections', 'worker_rlimit_nofile', 'keepalive_timeout']:
        content = re.sub(r'(?m)^(\s*)%s\s+[^;\n]+;' % k, r'\g<1>%s %s;' % (k, p[k]), content, 1)
    content = re.sub(r'(proxy_cache_path[^;]*max_size=)\w+', r'\g<1>' + p['proxy_cache_max_size'], content, 1)
    return content
