# coding:utf-8

import sys
import os
import re
import time
import json
import base64
import shlex

sys.path.append(os.getcwd() + "/class/core")
import mit

app_debug = False
if mit.isAppleSystem():
    app_debug = True

# options editable from the "Pengaturan" page, with their defaults
CONF_KEYS = {
    'bind': '127.0.0.1 -::1',
    'port': '6379',
    'requirepass': '',
    'timeout': '0',
    'databases': '16',
    'maxclients': '10000',
    'maxmemory': '0',
    'maxmemory-policy': 'noeviction',
    'appendonly': 'no',
}

MEMORY_POLICIES = ['noeviction', 'allkeys-lru', 'allkeys-lfu', 'allkeys-random',
                   'volatile-lru', 'volatile-lfu', 'volatile-random', 'volatile-ttl']


def getPluginName():
    return 'redis'


def getPluginDir():
    return mit.getPluginDir() + '/' + getPluginName()


def getServerDir():
    return mit.getServerDir() + '/' + getPluginName()


def getInitDTpl():
    return getPluginDir() + "/init.d/" + getPluginName() + ".tpl"


def getConf():
    return getServerDir() + '/redis.conf'


def getLog():
    return getServerDir() + '/redis.log'


def getArgs():
    # the page sends base64(JSON) so values survive the unquoted shell call
    for arg in reversed(sys.argv[2:]):
        try:
            data = json.loads(base64.b64decode(arg).decode('utf-8'))
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def readConf():
    content = mit.readFile(getConf())
    if not content:
        return {}
    conf = {}
    for line in content.split('\n'):
        line = line.strip()
        if line == '' or line.startswith('#'):
            continue
        parts = line.split(None, 1)
        key = parts[0].lower()
        if key in CONF_KEYS:
            conf[key] = parts[1].strip() if len(parts) > 1 else ''
    return conf


def getConfValue(key):
    return readConf().get(key, CONF_KEYS[key])


def writeConf(values):
    content = mit.readFile(getConf())
    lines = content.split('\n')
    for key, value in values.items():
        new_line = key + ' ' + value if value != '' else '# ' + key
        pattern = re.compile(r'^\s*#?\s*' + re.escape(key) + r'(\s|$)', re.I)
        found = False
        for i in range(len(lines)):
            if pattern.match(lines[i]):
                if found:
                    lines[i] = ''
                else:
                    lines[i] = new_line
                    found = True
        if not found:
            lines.append(new_line)
    mit.writeFile(getConf(), '\n'.join(lines))


def redisCli(cmd):
    password = getConfValue('requirepass')
    shell = 'REDISCLI_AUTH=' + shlex.quote(password) + ' ' if password else ''
    shell += getServerDir() + '/bin/redis-cli -h 127.0.0.1 -p ' + \
        shlex.quote(getConfValue('port')) + ' ' + cmd
    return mit.execShell(shell)


def status():
    data = mit.execShell(
        "ps -ef | grep '" + getServerDir() + "/bin/redis-server' | grep -v grep | awk '{print $2}'")
    if data[0].strip() == '':
        return 'stop'
    return 'start'


def initDreplace():
    initD_path = getServerDir() + '/init.d'
    if not os.path.exists(initD_path):
        os.mkdir(initD_path)
    file_bin = initD_path + '/' + getPluginName()

    if not os.path.exists(file_bin):
        content = mit.readFile(getInitDTpl())
        content = content.replace('{$SERVER_PATH}', getServerDir())
        mit.writeFile(file_bin, content)
        mit.execShell('chmod +x ' + file_bin)

    systemDir = mit.systemdCfgDir()
    systemService = systemDir + '/redis.service'
    systemServiceTpl = getPluginDir() + '/init.d/redis.service.tpl'
    if os.path.exists(systemDir) and not os.path.exists(systemService):
        content = mit.readFile(systemServiceTpl)
        content = content.replace('{$SERVER_PATH}', mit.getServerDir())
        mit.writeFile(systemService, content)
        mit.execShell('systemctl daemon-reload')

    return file_bin


def redisOp(method):
    file = initDreplace()

    if app_debug:
        mit.execShell(file + ' ' + method)
    else:
        mit.execShell('systemctl ' + method + ' redis')

    want = 'stop' if method == 'stop' else 'start'
    for i in range(10):
        if status() == want:
            return 'ok'
        time.sleep(0.5)

    log = mit.execShell('tail -n 5 ' + getLog())[0].strip()
    return 'Redis gagal di-' + method + '.\n' + log


def start():
    return redisOp('start')


def stop():
    return redisOp('stop')


def restart():
    return redisOp('restart')


def reload():
    return redisOp('restart')


def initdStatus():
    if app_debug:
        return 'ok'
    data = mit.execShell('systemctl is-enabled redis')
    if data[0].strip() == 'enabled':
        return 'ok'
    return 'fail'


def initdInstall():
    if app_debug:
        return 'ok'
    initDreplace()
    mit.execShell('systemctl enable redis')
    return 'ok'


def initdUinstall():
    if app_debug:
        return 'ok'
    mit.execShell('systemctl disable redis')
    return 'ok'


def runInfo():
    if status() != 'start':
        return mit.returnJson(False, 'Redis belum berjalan!')

    data = redisCli('info')
    if data[0].strip() == '' or 'NOAUTH' in data[0] or 'WRONGPASS' in data[0]:
        return mit.returnJson(False, 'Gagal membaca info Redis: ' + (data[0] + data[1]).strip())

    info = {}
    for line in data[0].split('\n'):
        line = line.strip()
        if line == '' or line.startswith('#') or ':' not in line:
            continue
        k, v = line.split(':', 1)
        info[k] = v

    keys = 0
    for k in info:
        if re.match(r'^db\d+$', k):
            m = re.search(r'keys=(\d+)', info[k])
            if m:
                keys += int(m.group(1))
    info['total_keys'] = keys

    hits = int(info.get('keyspace_hits', 0))
    misses = int(info.get('keyspace_misses', 0))
    info['hit_rate'] = '%.2f%%' % (hits * 100.0 / (hits + misses)) if hits + misses else '-'
    return mit.returnJson(True, 'ok', info)


def getRedisConf():
    conf = readConf()
    data = {}
    for key in CONF_KEYS:
        data[key] = conf.get(key, CONF_KEYS[key])
    data['maxmemory'] = str(toMb(data['maxmemory']))
    data['memory_policies'] = MEMORY_POLICIES
    return mit.returnJson(True, 'ok', data)


def toMb(value):
    value = str(value).strip().lower()
    m = re.match(r'^(\d+)\s*(gb|g|mb|m|kb|k|b)?$', value)
    if not m:
        return 0
    num = int(m.group(1))
    unit = m.group(2) or 'b'
    if unit in ('gb', 'g'):
        return num * 1024
    if unit in ('mb', 'm'):
        return num
    if unit in ('kb', 'k'):
        return num // 1024
    return num // 1024 // 1024


def enableAofLive():
    data = redisCli('config set appendonly yes')
    if data[0].strip() != 'OK':
        return 'Gagal mengaktifkan AOF: ' + (data[0] + data[1]).strip()
    for i in range(120):
        info = redisCli('info persistence')[0]
        if 'aof_rewrite_in_progress:0' in info and 'aof_rewrite_scheduled:0' in info:
            return 'ok'
        time.sleep(0.5)
    return 'AOF masih ditulis Redis, coba simpan lagi sebentar lagi'


def submitRedisConf():
    args = getArgs()
    values = {}

    bind = str(args.get('bind', '')).strip()
    if not re.match(r'^[0-9A-Za-z.:\-* ]+$', bind):
        return mit.returnJson(False, 'Alamat bind tidak valid')
    values['bind'] = bind

    for key, low, high in (('port', 1, 65535), ('timeout', 0, 31536000),
                           ('databases', 1, 1024), ('maxclients', 1, 1000000),
                           ('maxmemory', 0, 1048576)):
        try:
            num = int(str(args.get(key, '')).strip())
        except ValueError:
            return mit.returnJson(False, key + ' harus berupa angka')
        if num < low or num > high:
            return mit.returnJson(False, key + ' harus antara %d dan %d' % (low, high))
        values[key] = str(num)
    values['maxmemory'] = values['maxmemory'] + 'mb' if values['maxmemory'] != '0' else '0'

    password = str(args.get('requirepass', '')).strip()
    if password and not re.match(r'^[A-Za-z0-9!@#%^*()_+\-=.,~]{6,128}$', password):
        return mit.returnJson(False, 'Password minimal 6 karakter; hanya huruf, angka, dan !@#%^*()_+-=.,~')
    if not password and bind not in ('127.0.0.1', '127.0.0.1 -::1', '127.0.0.1 ::1'):
        return mit.returnJson(False, 'Redis yang bisa diakses dari luar wajib memakai password')
    values['requirepass'] = password

    policy = str(args.get('maxmemory-policy', ''))
    if policy not in MEMORY_POLICIES:
        return mit.returnJson(False, 'maxmemory-policy tidak valid')
    values['maxmemory-policy'] = policy

    appendonly = str(args.get('appendonly', 'no'))
    values['appendonly'] = 'yes' if appendonly == 'yes' else 'no'

    # Turning AOF on by config + restart would load an empty AOF and drop the
    # existing data, so enable it live first and let Redis write the AOF.
    if values['appendonly'] == 'yes' and getConfValue('appendonly') != 'yes' and status() == 'start':
        ret = enableAofLive()
        if ret != 'ok':
            return mit.returnJson(False, ret)

    writeConf(values)
    if status() == 'start':
        ret = restart()
        if ret != 'ok':
            return mit.returnJson(False, 'Tersimpan, tetapi ' + ret)
    return mit.returnJson(True, 'Pengaturan tersimpan dan Redis di-restart')


def connInfo():
    version = mit.readFile(getServerDir() + '/version_full.pl')
    data = {
        'host': '127.0.0.1',
        'port': getConfValue('port'),
        'password': getConfValue('requirepass'),
        'bind': getConfValue('bind'),
        'version': version.strip() if version else '',
        'cli': getServerDir() + '/bin/redis-cli',
    }
    return mit.returnJson(True, 'ok', data)


def flushAll():
    if status() != 'start':
        return mit.returnJson(False, 'Redis belum berjalan!')
    data = redisCli('flushall')
    if data[0].strip() == 'OK':
        return mit.returnJson(True, 'Semua data Redis sudah dikosongkan')
    return mit.returnJson(False, (data[0] + data[1]).strip())


if __name__ == "__main__":
    func = sys.argv[1]
    if func == 'status':
        print(status())
    elif func == 'start':
        print(start())
    elif func == 'stop':
        print(stop())
    elif func == 'restart':
        print(restart())
    elif func == 'reload':
        print(reload())
    elif func == 'initd_status':
        print(initdStatus())
    elif func == 'initd_install':
        print(initdInstall())
    elif func == 'initd_uninstall':
        print(initdUinstall())
    elif func == 'conf':
        print(getConf())
    elif func == 'run_log':
        print(getLog())
    elif func == 'run_info':
        print(runInfo())
    elif func == 'get_redis_conf':
        print(getRedisConf())
    elif func == 'submit_redis_conf':
        print(submitRedisConf())
    elif func == 'conn_info':
        print(connInfo())
    elif func == 'flush_all':
        print(flushAll())
    else:
        print('error')
