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
    return 'apache'


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


def getConf():
    return getServerDir() + "/conf/httpd.conf"


def getConfTpl():
    return getPluginDir() + '/conf/httpd.conf'


def getWebConfDir():
    return mit.getServerDir() + '/web_conf/apache'


def getOs():
    data = {}
    data['os'] = mit.getOs()
    # httpd is started as root by systemd/apachectl and drops to www itself
    data['auth'] = True
    return mit.getJson(data)


# module file -> module identifier, loaded in this order when the .so exists
MODULES = [
    ('mod_mpm_event.so', 'mpm_event_module'),
    ('mod_authn_file.so', 'authn_file_module'),
    ('mod_authn_core.so', 'authn_core_module'),
    ('mod_authz_host.so', 'authz_host_module'),
    ('mod_authz_groupfile.so', 'authz_groupfile_module'),
    ('mod_authz_user.so', 'authz_user_module'),
    ('mod_authz_core.so', 'authz_core_module'),
    ('mod_access_compat.so', 'access_compat_module'),
    ('mod_auth_basic.so', 'auth_basic_module'),
    ('mod_socache_shmcb.so', 'socache_shmcb_module'),
    ('mod_reqtimeout.so', 'reqtimeout_module'),
    ('mod_filter.so', 'filter_module'),
    ('mod_deflate.so', 'deflate_module'),
    ('mod_brotli.so', 'brotli_module'),
    ('mod_mime.so', 'mime_module'),
    ('mod_log_config.so', 'log_config_module'),
    ('mod_env.so', 'env_module'),
    ('mod_expires.so', 'expires_module'),
    ('mod_headers.so', 'headers_module'),
    ('mod_setenvif.so', 'setenvif_module'),
    ('mod_version.so', 'version_module'),
    ('mod_remoteip.so', 'remoteip_module'),
    ('mod_proxy.so', 'proxy_module'),
    ('mod_proxy_http.so', 'proxy_http_module'),
    ('mod_proxy_fcgi.so', 'proxy_fcgi_module'),
    ('mod_proxy_wstunnel.so', 'proxy_wstunnel_module'),
    ('mod_ssl.so', 'ssl_module'),
    ('mod_http2.so', 'http2_module'),
    ('mod_unixd.so', 'unixd_module'),
    ('mod_status.so', 'status_module'),
    ('mod_autoindex.so', 'autoindex_module'),
    ('mod_dir.so', 'dir_module'),
    ('mod_alias.so', 'alias_module'),
    ('mod_rewrite.so', 'rewrite_module'),
    ('mod_ratelimit.so', 'ratelimit_module'),
]


def loadModules():
    mod_dir = getServerDir() + '/modules'
    lines = []
    has_mpm = os.path.exists(mod_dir + '/mod_mpm_event.so')
    for so, name in MODULES:
        if os.path.exists(mod_dir + '/' + so):
            lines.append('LoadModule %s modules/%s' % (name, so))
    if not has_mpm and os.path.exists(mod_dir + '/mod_mpm_prefork.so'):
        lines.insert(0, 'LoadModule mpm_prefork_module modules/mod_mpm_prefork.so')
    return "\n".join(lines)


def makeWebConfDirs():
    for d in ['vhost', 'rewrite', 'pass', 'redirect', 'proxy']:
        path = getWebConfDir() + '/' + d
        if not os.path.exists(path):
            mit.execShell('mkdir -p ' + path + ' && chmod -R 755 ' + path)


def makeHtdocs():
    html = getServerDir() + '/htdocs'
    if not os.path.exists(html):
        os.makedirs(html)
    index = html + '/index.html'
    content = mit.readFile(index)
    if not content or content.find('It works!') != -1:
        mit.writeFile(index, '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Apache</title></head>
<body style="font-family:sans-serif;text-align:center;padding-top:80px">
<h1>Apache is running</h1>
<p>No website is bound to this domain / IP yet.</p>
</body></html>
''')
    notfound = html + '/404.html'
    if not os.path.exists(notfound):
        mit.writeFile(notfound, '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>404 Not Found</title></head>
<body style="font-family:sans-serif;text-align:center;padding-top:80px">
<h1>404 Not Found</h1>
</body></html>
''')


def makePanelDomainConf():
    # panel domain that was bound while running OpenResty
    bind_domain = mit.getRunDir() + '/data/bind_domain.pl'
    dst = getWebConfDir() + '/vhost/panel.conf'
    if not os.path.exists(bind_domain) or os.path.exists(dst):
        return
    domain = mit.readFile(bind_domain).strip()
    if domain == '':
        return
    content = mit.readFile(mit.getRunDir() + '/data/tpl/apache_panel.conf')
    content = content.replace("{$PORT}", "80")
    content = content.replace("{$SERVER_NAME}", domain)
    content = content.replace("{$PANAL_PORT}", mit.readFile(mit.getRunDir() + '/data/port.pl').strip())
    content = content.replace("{$LOGPATH}", mit.getRunDir() + '/logs')
    mit.writeFile(dst, content)


def makePhpMyAdminConf():
    pma_dir = mit.getServerDir() + '/phpmyadmin'
    if not os.path.exists(pma_dir) or os.path.exists(getWebConfDir() + '/vhost/phpmyadmin.conf'):
        return
    mit.execShell('cd ' + mit.getRunDir() + ' && python3 plugins/phpmyadmin/index.py start')


def rebuildVhost():
    import site_apache
    import site_api
    site_apache.makeEnablePhpConf()
    made = site_apache.site_apache(site_api.site_api()).rebuildFromDb()
    return made


def confReplace():
    service_path = mit.getServerDir()
    content = mit.readFile(getConfTpl())
    content = content.replace('{$SERVER_PATH}', service_path)
    content = content.replace('{$LOAD_MODULES}', loadModules())

    user = 'www'
    user_group = 'www'
    if mit.getOs() == 'darwin':
        user = mit.execShell("who | sed -n '2, 1p' |awk '{print $1}'")[0].strip()
        user_group = 'staff'
    content = content.replace('{$OS_USER}', user)
    content = content.replace('{$OS_USER_GROUP}', user_group)
    mit.writeFile(getConf(), content)

    makeWebConfDirs()
    makeHtdocs()

    import site_apache
    site_apache.makeEnablePhpConf()
    if not os.path.exists(getWebConfDir() + '/vhost/0.default.conf'):
        site_apache.makeDefaultVhost(getServerDir() + '/htdocs')

    # sites created while OpenResty was the web server
    try:
        rebuildVhost()
    except Exception as e:
        print('rebuild vhost: ' + str(e))

    makePanelDomainConf()
    makePhpMyAdminConf()
    mit.apacheSyncListen()


def initDreplace():
    file_tpl = getPluginDir() + "/init.d/apache.tpl"
    service_path = mit.getServerDir()

    initD_path = getServerDir() + '/init.d'

    # Apache is not installed
    if not os.path.exists(getServerDir()):
        print("ok")
        exit(0)

    file_bin = initD_path + '/' + getPluginName()
    if not os.path.exists(initD_path):
        os.mkdir(initD_path)

    if not os.path.exists(file_bin):
        content = mit.readFile(file_tpl)
        content = content.replace('{$SERVER_PATH}', service_path)
        mit.writeFile(file_bin, content)
        mit.execShell('chmod +x ' + file_bin)

    # first start generates httpd.conf and migrates existing sites
    conf_mark = getServerDir() + '/conf/panel_conf.pl'
    if not os.path.exists(conf_mark):
        confReplace()
        mit.writeFile(conf_mark, 'ok')
    else:
        mit.apacheSyncListen()

    # systemd
    systemDir = mit.systemdCfgDir()
    systemService = systemDir + '/apache.service'
    systemServiceTpl = getPluginDir() + '/init.d/apache.service.tpl'
    if os.path.exists(systemDir) and not os.path.exists(systemService):
        se_content = mit.readFile(systemServiceTpl)
        se_content = se_content.replace('{$SERVER_PATH}', service_path)
        mit.writeFile(systemService, se_content)
        mit.execShell('systemctl daemon-reload')

    return file_bin


def status():
    pid_file = getServerDir() + '/logs/httpd.pid'
    if not os.path.exists(pid_file):
        return 'stop'
    pid = mit.readFile(pid_file).strip()
    data = mit.execShell("ps -p " + pid + " -o comm= 2>/dev/null")
    if data[0].strip() == '':
        return 'stop'
    return 'start'


def configTest():
    mit.apacheSyncListen()
    data = mit.execShell(getServerDir() + '/bin/apachectl -t')
    if (data[0] + data[1]).find('Syntax OK') == -1:
        return data[1]
    return True


def apOp(method):
    file = initDreplace()

    if method != 'stop':
        check = configTest()
        if check != True:
            return 'ERROR: configuration error<br><a style="color:red;">' + check.replace("\n", '<br>') + '</a>'

    if not mit.isAppleSystem() and os.path.exists(mit.systemdCfgDir() + '/apache.service'):
        if method == 'restart':
            # restart via a timer so the panel request can finish first
            threading.Timer(2, mit.execShell, args=('systemctl restart apache',)).start()
            return 'ok'
        data = mit.execShell('systemctl ' + method + ' apache')
        if data[1] == '':
            return 'ok'
        return data[1]

    data = mit.execShell(file + ' ' + method)
    if data[1] == '':
        return 'ok'
    return data[1]


def start():
    return apOp('start')


def stop():
    return apOp('stop')


def restart():
    return apOp('restart')


def reload():
    return apOp('reload')


def initdStatus():
    if mit.isAppleSystem():
        return "ok"

    shell_cmd = 'systemctl status apache | grep loaded | grep "enabled;"'
    data = mit.execShell(shell_cmd)
    if data[0] == '':
        return 'fail'
    return 'ok'


def initdInstall():
    if mit.isAppleSystem():
        return "ok"

    mit.execShell('systemctl enable apache')
    return 'ok'


def initdUinstall():
    if mit.isAppleSystem():
        return "ok"

    mit.execShell('systemctl disable apache')
    return 'ok'


def runInfo():
    try:
        result = mit.httpGet('http://127.0.0.1/server-status?auto', timeout=2)
        data = {}
        keys = ['Total Accesses', 'Total kBytes', 'Uptime', 'ReqPerSec',
                'BytesPerSec', 'BusyWorkers', 'IdleWorkers', 'ConnsTotal',
                'ConnsAsyncWriting', 'ConnsAsyncKeepAlive', 'ConnsAsyncClosing']
        for line in result.split("\n"):
            if line.find(':') == -1:
                continue
            k, v = line.split(':', 1)
            if k.strip() in keys:
                data[k.strip()] = v.strip()
        if len(data) == 0:
            return 'Apache not started or mod_status unavailable'
        return mit.getJson(data)
    except Exception as e:
        return 'Apache not started or mod_status unavailable'


def errorLogPath():
    return getServerDir() + '/logs/error_log'


CFG_ARGS = [
    {"name": "Timeout", "ps": "Request timeout (seconds)", 'type': 2},
    {"name": "KeepAlive", "ps": "Persistent connections", 'type': 1},
    {"name": "KeepAliveTimeout", "ps": "Keep-alive timeout (seconds)", 'type': 2},
    {"name": "MaxKeepAliveRequests", "ps": "Max requests per keep-alive connection", 'type': 2},
    {"name": "ServerLimit", "ps": "Max child processes (MaxRequestWorkers / ThreadsPerChild), needs restart", 'type': 2},
    {"name": "StartServers", "ps": "Child processes created at startup", 'type': 2},
    {"name": "ThreadsPerChild", "ps": "Threads per child process (event MPM)", 'type': 2},
    {"name": "MaxRequestWorkers", "ps": "Maximum concurrent requests", 'type': 2},
    {"name": "LimitRequestBody", "ps": "Maximum upload size in bytes (0 = unlimited)", 'type': 2},
]


def getCfg():
    content = mit.readFile(getConf())
    if not content:
        return mit.returnJson(False, 'httpd.conf not found')

    rdata = []
    for i in CFG_ARGS:
        k = re.search(r'^\s*(%s)\s+(\S+)' % i['name'], content, re.M)
        if not k:
            continue
        rdata.append({"name": i['name'], "value": k.group(2), "unit": "",
                      "ps": i["ps"], "type": i["type"]})

    return mit.returnJson(True, "ok", rdata)


def setCfg():
    args = getArgs()
    names = [i['name'] for i in CFG_ARGS]

    cfg = getConf()
    mit.backFile(cfg)
    content = mit.readFile(cfg)

    for k, v in args.items():
        if not k in names:
            continue
        if k == 'KeepAlive':
            if not v in ('On', 'Off'):
                return mit.returnJson(False, 'KeepAlive must be On or Off')
        elif not re.match(r'^\d+$', v):
            return mit.returnJson(False, 'The parameter value is wrong, please enter a numeric integer')
        # the first occurrence; StartServers exists for both MPMs, event comes first
        content = re.sub(r'^(\s*)%s\s+\S+' % k, r'\g<1>%s %s' % (k, v), content, 1, re.M)

    mit.writeFile(cfg, content)
    isError = configTest()
    if isError != True:
        mit.restoreFile(cfg)
        return mit.returnJson(False, 'ERROR: configuration error<br><a style="color:red;">' + isError.replace("\n", '<br>') + '</a>')

    mit.restartWeb()
    return mit.returnJson(True, 'Successfully set')


def rebuildVhostApi():
    try:
        made = rebuildVhost()
        mit.restartWeb()
        if len(made) == 0:
            return mit.returnJson(True, 'Semua situs sudah punya vhost Apache.')
        return mit.returnJson(True, 'Vhost Apache dibuat untuk: ' + ', '.join(made))
    except Exception as e:
        return mit.returnJson(False, 'Rebuild gagal: ' + str(e))


def getTuneProfile():
    import tuning
    return mit.returnJson(True, 'ok', tuning.apacheProfile())


def autoTune():
    import tuning
    data = tuning.apacheProfile()
    cfg = getConf()
    old = mit.readFile(cfg)
    mit.writeFile(cfg, tuning.applyApacheProfile(old, data['profile']))

    check = configTest()
    if check != True:
        mit.writeFile(cfg, old)
        return mit.returnJson(False, 'Konfigurasi hasil tuning tidak valid, dibatalkan: ' + check)

    # ServerLimit / ThreadLimit only change on a full restart
    backup = cfg + '.tune_' + time.strftime('%Y%m%d%H%M%S') + '.bak'
    mit.writeFile(backup, old)
    initDreplace()
    if os.path.exists(mit.systemdCfgDir() + '/apache.service'):
        mit.execShell('systemctl restart apache')
    else:
        mit.execShell(getServerDir() + '/init.d/apache restart')

    for i in range(20):
        time.sleep(1)
        if status() == 'start':
            p = data['profile']
            msg = '%s: MaxRequestWorkers %d, ThreadsPerChild %d, ServerLimit %d. Backup: %s' % (
                data['label'], p['MaxRequestWorkers'], p['ThreadsPerChild'], p['ServerLimit'], backup)
            mit.writeLog('Tuning', 'Apache ' + msg)
            return mit.returnJson(True, msg)

    mit.writeFile(cfg, old)
    mit.execShell('systemctl restart apache')
    return mit.returnJson(False, 'Apache gagal start dengan profil baru, konfigurasi lama dikembalikan.')


def installPreInspection():
    if os.path.exists(mit.getServerDir() + '/openresty'):
        return 'OpenResty sudah terpasang. Seperti aaPanel, hanya satu web server yang bisa aktif: hapus OpenResty dulu, lalu pasang Apache. Situs yang sudah ada akan otomatis dibuatkan vhost Apache.'
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
    elif func == 'rebuild_vhost':
        print(rebuildVhostApi())
    elif func == 'conf_replace':
        confReplace()
        print('ok')
    else:
        print('error')
