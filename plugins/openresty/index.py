#!/usr/bin/python3
# coding:utf-8

import sys
import io
import os
import time
import threading
import subprocess
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/class/core")
import mit


app_debug = False

if mit.isAppleSystem():
    app_debug = True


def getPluginName():
    return 'openresty'


def getPluginDir():
    return mit.getPluginDir() + '/' + getPluginName()


def getServerDir():
    return mit.getServerDir() + '/' + getPluginName()


def getInitDFile():
    if app_debug:
        return '/tmp/' + getPluginName()
    return '/etc/init.d/' + getPluginName()


def getArgs():
    args = sys.argv[2:]
    tmp = {}
    args_len = len(args)

    if args_len == 1:
        t = args[0].strip('{').strip('}')
        t = t.split(':')
        tmp[t[0]] = t[1]
    elif args_len > 1:
        for i in range(len(args)):
            t = args[i].split(':')
            tmp[t[0]] = t[1]

    return tmp


def checkArgs(data, ck=[]):
    for i in range(len(ck)):
        if not ck[i] in data:
            return (False, mit.returnJson(False, 'Parameters: (' + ck[i] + ') none!'))
    return (True, mit.returnJson(True, 'ok'))


def clearTemp():
    path_bin = getServerDir() + "/nginx"
    mit.execShell('rm -rf ' + path_bin + '/client_body_temp')
    mit.execShell('rm -rf ' + path_bin + '/fastcgi_temp')
    mit.execShell('rm -rf ' + path_bin + '/proxy_temp')
    mit.execShell('rm -rf ' + path_bin + '/scgi_temp')
    mit.execShell('rm -rf ' + path_bin + '/uwsgi_temp')


def getConf():
    path = getServerDir() + "/nginx/conf/nginx.conf"
    return path


def getConfTpl():
    path = getPluginDir() + '/conf/nginx.conf'
    return path


def getOs():
    data = {}
    data['os'] = mit.getOs()
    ng_exe_bin = getServerDir() + "/nginx/sbin/nginx"
    if checkAuthEq(ng_exe_bin, 'root'):
        data['auth'] = True
    else:
        data['auth'] = False
    return mit.getJson(data)


def getInitDTpl():
    path = getPluginDir() + "/init.d/nginx.tpl"
    return path


def getFileOwner(filename):
    import pwd
    stat = os.lstat(filename)
    uid = stat.st_uid
    pw = pwd.getpwuid(uid)
    return pw.pw_name


def checkAuthEq(file, owner='root'):
    fowner = getFileOwner(file)
    if (fowner == owner):
        return True
    return False


def confReplace():
    service_path = mit.getServerDir()
    content = mit.readFile(getConfTpl())
    content = content.replace('{$SERVER_PATH}', service_path)

    user = 'www'
    user_group = 'www'

    if mit.getOs() == 'darwin':
        # macosx do
        user = mit.execShell(
            "who | sed -n '2, 1p' |awk '{print $1}'")[0].strip()
        # user = 'root'
        user_group = 'staff'
        content = content.replace('{$EVENT_MODEL}', 'kqueue')
    else:
        content = content.replace('{$EVENT_MODEL}', 'epoll')

    if mit.getOs() == 'darwin':
        content = content.replace('user  {$OS_USER} {$OS_USER_GROUP};', '#user  {$OS_USER} {$OS_USER_GROUP};')

    content = content.replace('{$OS_USER}', user)
    content = content.replace('{$OS_USER_GROUP}', user_group)

    # ng_conf_md5 = ''
    # ng_conf_md5_file = getServerDir() + '/nginx_conf.md5'
    # if not os.path.exists(ng_conf_md5_file):
    #     ng_conf_md5 = mit.md5(content)
    #     mit.writeFile(ng_conf_md5_file, ng_conf_md5)
    # else:
    #     ng_conf_md5 = mit.writeFile(ng_conf_md5_file).strip()

    nconf = getServerDir() + '/nginx/conf/nginx.conf'
    mit.writeFile(nconf, content)

    # Create cache directories
    proxy_cache_temp = getServerDir() + '/nginx/proxy_cache_temp'
    if not os.path.exists(proxy_cache_temp):
        mit.execShell('mkdir -p ' + proxy_cache_temp)
    mit.execShell('chown -R ' + user + ':' + user_group + ' ' + proxy_cache_temp)

    fastcgi_cache_temp = getServerDir() + '/nginx/fastcgi_cache_temp'
    if not os.path.exists(fastcgi_cache_temp):
        mit.execShell('mkdir -p ' + fastcgi_cache_temp)
    mit.execShell('chown -R ' + user + ':' + user_group + ' ' + fastcgi_cache_temp)

    lua_conf_dir = mit.getServerDir() + '/web_conf/nginx/lua'
    if not os.path.exists(lua_conf_dir):
        mit.execShell('mkdir -p ' + lua_conf_dir)

    lua_conf = lua_conf_dir + '/lua.conf'
    lua_conf_tpl = getPluginDir() + '/conf/lua.conf'
    lua_content = mit.readFile(lua_conf_tpl)
    lua_content = lua_content.replace('{$SERVER_PATH}', service_path)
    mit.writeFile(lua_conf, lua_content)

    empty_lua = lua_conf_dir + '/empty.lua'
    if not os.path.exists(empty_lua):
        mit.writeFile(empty_lua, '')

    mit.opLuaMakeAll()

    php_conf = mit.getServerDir() + '/web_conf/php/conf'
    if not os.path.exists(php_conf):
        mit.execShell('mkdir -p ' + php_conf)
    static_conf = mit.getServerDir() + '/web_conf/php/conf/enable-php-00.conf'
    if not os.path.exists(static_conf):
        mit.writeFile(static_conf, 'set $PHP_ENV 0;')

    # give nginx root permission
    ng_exe_bin = getServerDir() + "/nginx/sbin/nginx"
    if not checkAuthEq(ng_exe_bin, 'root'):
        args = getArgs()
        sudoPwd = args.get('pwd', '')
        if sudoPwd:
            cmd_own = 'chown -R ' + 'root:' + user_group + ' ' + ng_exe_bin
            os.system('echo %s|sudo -S %s' % (sudoPwd, cmd_own))
            cmd_mod = 'chmod 755 ' + ng_exe_bin
            os.system('echo %s|sudo -S %s' % (sudoPwd, cmd_mod))
            cmd_s = 'chmod u+s ' + ng_exe_bin
            os.system('echo %s|sudo -S %s' % (sudoPwd, cmd_s))
        else:
            print("Warning: Missing sudo password, skipping nginx chown/chmod. It will run as the current user.")


    # vhost
    vhost_dir = mit.getServerDir() + '/web_conf/nginx/vhost'
    vhost_tpl_dir = getPluginDir() + '/conf/vhost'
    # print(vhost_dir, vhost_tpl_dir)
    vhost_list = ['0.websocket.conf', '0.nginx_status.conf']
    for f in vhost_list:
        a_conf = vhost_dir + '/' + f
        a_conf_tpl = vhost_tpl_dir + '/' + f
        mit.writeFile(a_conf, mit.readFile(a_conf_tpl))

def initDreplace():

    file_tpl = getInitDTpl()
    service_path = mit.getServerDir()

    initD_path = getServerDir() + '/init.d'

    # OpenResty is not installed
    if not os.path.exists(getServerDir()):
        print("ok")
        exit(0)

    # init.d
    file_bin = initD_path + '/' + getPluginName()
    if not os.path.exists(initD_path):
        os.mkdir(initD_path)

        # initd replace
        content = mit.readFile(file_tpl)
        content = content.replace('{$SERVER_PATH}', service_path)
        mit.writeFile(file_bin, content)
        mit.execShell('chmod +x ' + file_bin)

        # config replace
        confReplace()

    # systemd
    # /usr/lib/systemd/system
    systemDir = mit.systemdCfgDir()
    systemService = systemDir + '/openresty.service'
    systemServiceTpl = getPluginDir() + '/init.d/openresty.service.tpl'
    if os.path.exists(systemDir) and not os.path.exists(systemService):
        se_content = mit.readFile(systemServiceTpl)
        se_content = se_content.replace('{$SERVER_PATH}', service_path)
        mit.writeFile(systemService, se_content)
        mit.execShell('systemctl daemon-reload')

    return file_bin


def status():
    data = mit.execShell(
        "ps -ef|grep openresty |grep -v grep | grep -v python | awk '{print $2}'")
    if data[0] == '':
        return 'stop'
    return 'start'


def restyOp(method):
    file = initDreplace()

    check = getServerDir() + "/bin/openresty -t"
    check_data = mit.execShell(check)
    if not check_data[1].find('test is successful') > -1:
        return check_data[1]

    if not mit.isAppleSystem():
        data = mit.execShell('systemctl ' + method + ' openresty')
        if data[1] == '':
            return 'ok'
        return data[1]

    data = mit.execShell(file + ' ' + method)
    if data[1] == '':
        return 'ok'
    return data[1]


def op_submit_systemctl_restart():
    mit.execShell('systemctl restart openresty')


def op_submit_init_restart(file):
    mit.execShell(file + ' restart')


def restyOp_restart():
    file = initDreplace()

    check = getServerDir() + "/bin/openresty -t"
    check_data = mit.execShell(check)
    if not check_data[1].find('test is successful') > -1:
        return 'ERROR: configuration error<br><a style="color:red;">' + check_data[1].replace("\n", '<br>') + '</a>'

    if not mit.isAppleSystem():
        threading.Timer(2, op_submit_systemctl_restart, args=()).start()
        # submit_restart1()
        return 'ok'

    threading.Timer(2, op_submit_init_restart, args=(file,)).start()
    # submit_restart2(file)
    return 'ok'


def start():
    return restyOp('start')


def stop():
    return restyOp('stop')


def restart():
    return restyOp_restart()


def reload():
    return restyOp('reload')


def initdStatus():

    if mit.isAppleSystem():
        return "ok"

    shell_cmd = 'systemctl status openresty | grep loaded | grep "enabled;"'
    data = mit.execShell(shell_cmd)
    if data[0] == '':
        return 'fail'
    return 'ok'


def initdInstall():
    if mit.isAppleSystem():
        return "ok"

    mit.execShell('systemctl enable openresty')
    return 'ok'


def initdUinstall():
    if mit.isAppleSystem():
        return "ok"

    mit.execShell('systemctl disable openresty')
    return 'ok'


def runInfo():
    try:
        url = 'http://127.0.0.1/nginx_status'
        result = mit.httpGet(url, timeout=1)
        tmp = result.split()
        data = {}
        data['active'] = tmp[2]
        data['accepts'] = tmp[9]
        data['handled'] = tmp[7]
        data['requests'] = tmp[8]
        data['Reading'] = tmp[11]
        data['Writing'] = tmp[13]
        data['Waiting'] = tmp[15]
        return mit.getJson(data)
    except Exception as e:

        url = 'http://' + mit.getHostAddr() + '/nginx_status'
        result = mit.httpGet(url)
        tmp = result.split()
        data = {}
        data['active'] = tmp[2]
        data['accepts'] = tmp[9]
        data['handled'] = tmp[7]
        data['requests'] = tmp[8]
        data['Reading'] = tmp[11]
        data['Writing'] = tmp[13]
        data['Waiting'] = tmp[15]
        return mit.getJson(data)
    except Exception as e:
        return 'oprenresty not started'


def errorLogPath():
    return getServerDir() + '/nginx/logs/error.log'


def getCfg():
    cfg = getConf()
    content = mit.readFile(cfg)

    unitrep = "[kmgKMG]"
    cfg_args = [
        {"name": "worker_processes", "ps": "Processing process, auto means automatic, number means the number of processes", 'type': 2},
        {"name": "worker_connections", "ps": "Maximum number of concurrent connections", 'type': 2},
        {"name": "keepalive_timeout", "ps": "Connection timeout", 'type': 2},
        {"name": "gzip", "ps": "Whether to enable compressed transmission", 'type': 1},
        {"name": "gzip_min_length", "ps": "Minimal zip file", 'type': 2},
        {"name": "gzip_comp_level", "ps": "Compression ratio", 'type': 2},
        {"name": "client_max_body_size", "ps": "Maximum uploaded files", 'type': 2},
        {"name": "server_names_hash_bucket_size", "ps": "The hash table size of the server name", 'type': 2},
        {"name": "client_header_buffer_size", "ps": "Client request header buffer size", 'type': 2},
    ]

    rdata = []
    for i in cfg_args:
        rep = r"(%s)\s+(\w+)" % i["name"]
        k = re.search(rep, content)
        if not k:
            return mit.returnJson(False, "Failed to get key {}".format(k))
        k = k.group(1)
        v = re.search(rep, content)
        if not v:
            return mit.returnJson(False, "Failed to get value {}".format(v))
        v = v.group(2)

        if re.search(unitrep, v):
            u = str.upper(v[-1])
            v = v[:-1]
            if len(u) == 1:
                psstr = u + "B，" + i["ps"]
            else:
                psstr = u + "，" + i["ps"]
        else:
            u = ""

        kv = {"name": k, "value": v, "unit": u,
              "ps": i["ps"], "type": i["type"]}
        rdata.append(kv)

    return mit.returnJson(True, "ok", rdata)


def setCfg():

    args = getArgs()
    data = checkArgs(args, [
        'worker_processes', 'worker_connections', 'keepalive_timeout',
        'gzip', 'gzip_min_length', 'gzip_comp_level', 'client_max_body_size',
        'server_names_hash_bucket_size', 'client_header_buffer_size'
    ])
    if not data[0]:
        return data[1]

    cfg = getConf()
    mit.backFile(cfg)
    content = mit.readFile(cfg)

    unitrep = "[kmgKMG]"
    cfg_args = [
        {"name": "worker_processes", "ps": "Processing process, auto means automatic, number means the number of processes", 'type': 2},
        {"name": "worker_connections", "ps": "Maximum number of concurrent connections", 'type': 2},
        {"name": "keepalive_timeout", "ps": "Connection timeout", 'type': 2},
        {"name": "gzip", "ps": "Whether to enable compressed transmission", 'type': 1},
        {"name": "gzip_min_length", "ps": "Minimal zip file", 'type': 2},
        {"name": "gzip_comp_level", "ps": "Compression ratio", 'type': 2},
        {"name": "client_max_body_size", "ps": "Maximum uploaded files", 'type': 2},
        {"name": "server_names_hash_bucket_size", "ps": "The hash table size of the server name", 'type': 2},
        {"name": "client_header_buffer_size", "ps": "Client request header buffer size", 'type': 2},
    ]

    # print(args)
    for k, v in args.items():
        # print(k, v)
        rep = r"%s\s+[^kKmMgG\;\n]+" % k
        if k == "worker_processes" or k == "gzip":
            if not re.search(r"auto|on|off|\d+", v):
                return mit.returnJson(False, 'Wrong parameter value')
        else:
            if not re.search(r"\d+", v):
                return mit.returnJson(False, 'The parameter value is wrong, please enter a numeric integer')

        if re.search(rep, content):
            newconf = "%s %s" % (k, v)
            content = re.sub(rep, newconf, content)
        elif re.search(rep, content):
            newconf = "%s %s" % (k, v)
            content = re.sub(rep, newconf, content)

    mit.writeFile(cfg, content)
    isError = mit.checkWebConfig()
    if (isError != True):
        mit.restoreFile(cfg)
        return mit.returnJson(False, 'ERROR: configuration error<br><a style="color:red;">' + isError.replace("\n", '<br>') + '</a>')

    mit.restartWeb()
    return mit.returnJson(True, 'Successfully set')


def getTuneProfile():
    import tuning
    return mit.returnJson(True, 'ok', tuning.nginxProfile())


def autoTune():
    import tuning
    data = tuning.nginxProfile()
    cfg = getConf()
    old = mit.readFile(cfg)
    backup = cfg + '.tune_' + time.strftime('%Y%m%d%H%M%S') + '.bak'
    mit.writeFile(backup, old)
    mit.writeFile(cfg, tuning.applyNginxProfile(old, data['profile']))

    isError = mit.checkWebConfig()
    if isError != True:
        mit.writeFile(cfg, old)
        return mit.returnJson(False, 'Konfigurasi hasil tuning tidak valid, dibatalkan: ' + isError)

    mit.restartWeb()
    p = data['profile']
    msg = '%s: worker_connections %d, worker_rlimit_nofile %d, proxy cache %s. Backup: %s' % (
        data['label'], p['worker_connections'], p['worker_rlimit_nofile'], p['proxy_cache_max_size'], backup)
    mit.writeLog('Tuning', 'Nginx ' + msg)
    return mit.returnJson(True, msg)


def installPreInspection():
    if os.path.exists(mit.getServerDir() + '/apache'):
        return 'Apache sudah terpasang. Hanya satu web server yang bisa aktif: hapus Apache dulu, lalu pasang Nginx.'
    return 'ok'


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
    elif func == 'install_pre_inspection':
        print(installPreInspection())
    elif func == 'conf':
        print(getConf())
    elif func == 'get_os':
        print(getOs())
    elif func == 'run_info':
        print(runInfo())
    elif func == 'error_log':
        print(errorLogPath())
    elif func == 'get_cfg':
        print(getCfg())
    elif func == 'set_cfg':
        print(setCfg())
    elif func == 'get_tune_profile':
        print(getTuneProfile())
    elif func == 'auto_tune':
        print(autoTune())
    else:
        print('error')
