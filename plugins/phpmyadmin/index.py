# coding:utf-8

import sys
import io
import os
import time
import re
import json

sys.path.append(os.getcwd() + "/class/core")
import mit
import site_api

app_debug = False
if mit.isAppleSystem():
    app_debug = True


def getPluginName():
    return 'phpmyadmin'


def getPluginDir():
    return mit.getPluginDir() + '/' + getPluginName()


def getServerDir():
    return mit.getServerDir() + '/' + getPluginName()


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
            return (False, mit.returnJson(False, 'Parameter: (' + ck[i] + ') none!'))
    return (True, mit.returnJson(True, 'ok'))


def getConf():
    return mit.getWebConfDir() + '/vhost/phpmyadmin.conf'


def getConfTpl():
    if mit.isApache():
        return getPluginDir() + '/conf/phpmyadmin_apache.conf'
    return getPluginDir() + '/conf/phpmyadmin.conf'


def getPortRep():
    if mit.isApache():
        return (r'<VirtualHost\s+\*:(\d+)>', '<VirtualHost *:{}>')
    return (r'listen\s*(.*);', 'listen {};')


def getConfInc():
    return getServerDir() + "/" + getCfg()['path'] + '/config.inc.php'


def getPort():
    file = getConf()
    content = mit.readFile(file)
    rep = getPortRep()[0]
    tmp = re.search(rep, content)
    return tmp.groups()[0].strip()


def getHomePage():
    try:
        port = getPort()
        ip = '127.0.0.1'
        if not mit.isAppleSystem():
            ip = mit.getLocalIp()
        url = 'http://' + ip + ':' + port + \
            '/' + getCfg()['path'] + '/index.php'
        return mit.returnJson(True, 'OK', url)
    except Exception as e:
        return mit.returnJson(False, 'Plugin not started!')


def getPhpVer(expect=55):
    v = site_api.site_api().getPhpVersion()
    is_find = False
    for i in range(len(v)):
        t = str(v[i]['version'])
        if (t == expect):
            is_find = True
            return str(t)
    if not is_find:
        if len(v) > 1:
            return v[1]['version']
        return v[0]['version']
    return str(expect)


def getCachePhpVer():
    cacheFile = getServerDir() + '/php.pl'
    v = ''
    if os.path.exists(cacheFile):
        v = mit.readFile(cacheFile)
    else:
        v = getPhpVer()
        mit.writeFile(cacheFile, v)
    return v


def contentReplace(content):
    service_path = mit.getServerDir()
    php_ver = getCachePhpVer()
    tmp = mit.execShell(
        'cat /dev/urandom | head -n 32 | md5sum | head -c 16')
    blowfish_secret = tmp[0].strip()
    # print php_ver
    php_conf_dir = mit.getServerDir() + '/web_conf/php/conf'
    if mit.isApache():
        php_conf_dir = mit.getServerDir() + '/web_conf/php/apache'
    content = content.replace('{$ROOT_PATH}', mit.getRootDir())
    content = content.replace('{$SERVER_PATH}', service_path)
    content = content.replace('{$PHP_CONF_PATH}', php_conf_dir)
    content = content.replace('{$PHP_VER}', php_ver)
    content = content.replace('{$BLOWFISH_SECRET}', blowfish_secret)

    cfg = getCfg()

    # phpMyAdmin is often installed before the database: when the chosen one
    # is missing but the other is installed, point at the installed one
    choose_dir = {'mysql': 'mysql', 'mysql-apt': 'mysql-apt',
                  'mysql-yum': 'mysql-yum'}.get(cfg['choose'], 'mariadb')
    if not os.path.exists(service_path + '/' + choose_dir):
        for db in ['mariadb', 'mysql', 'mysql-apt', 'mysql-yum']:
            if os.path.exists(service_path + '/' + db):
                cfg['choose'] = db
                setCfg('choose', db)
                break

    if cfg['choose'] == "mysql":
        content = content.replace('{$CHOOSE_DB}', 'mysql')
        content = content.replace('{$CHOOSE_DB_DIR}', 'mysql')
    elif cfg['choose'] == "mysql-apt":
        content = content.replace('{$CHOOSE_DB}', 'mysql')
        content = content.replace('{$CHOOSE_DB_DIR}', 'mysql-apt')
    elif cfg['choose'] == "mysql-yum":
        content = content.replace('{$CHOOSE_DB}', 'mysql')
        content = content.replace('{$CHOOSE_DB_DIR}', 'mysql-yum')
    else:
        content = content.replace('{$CHOOSE_DB}', 'MariaDB')
        content = content.replace('{$CHOOSE_DB_DIR}', 'mariadb')

    content = content.replace('{$PMA_PATH}', cfg['path'])

    port = cfg["port"]
    rep, fmt = getPortRep()
    content = re.sub(rep, fmt.format(port), content, 1)
    return content


def initCfg():
    cfg = getServerDir() + "/cfg.json"
    if not os.path.exists(cfg):
        data = {}
        data['port'] = '888'
        data['choose'] = 'mysql'
        data['path'] = ''
        data['username'] = 'admin'
        data['password'] = 'admin'
        mit.writeFile(cfg, json.dumps(data))


def setCfg(key, val):
    cfg = getServerDir() + "/cfg.json"
    data = mit.readFile(cfg)
    data = json.loads(data)
    data[key] = val
    mit.writeFile(cfg, json.dumps(data))


def getCfg():
    cfg = getServerDir() + "/cfg.json"
    data = mit.readFile(cfg)
    data = json.loads(data)
    return data


def returnCfg():
    cfg = getServerDir() + "/cfg.json"
    data = mit.readFile(cfg)
    return data


def refreshDbConf(conf_inc):
    # config.inc.php written before MariaDB/MySQL was installed points at a
    # socket that does not exist: rewrite it for the database now installed
    if not os.path.exists(conf_inc):
        return
    m = re.search(r"^\$cfg\['Servers'\]\[\$i\]\['socket'\]\s*=\s*'([^']+)'",
                  mit.readFile(conf_inc), re.M)
    if m and not os.path.exists(os.path.dirname(m.group(1))):
        content = contentReplace(mit.readFile(getPluginDir() + '/conf/config.inc.php'))
        if m.group(1) not in content:
            mit.writeFile(conf_inc, content)


def status():
    conf = getConf()
    conf_inc = getServerDir() + "/" + getCfg()["path"] + '/config.inc.php'
    refreshDbConf(conf_inc)
    if os.path.exists(conf) and os.path.exists(conf_inc):
        return 'start'
    return 'stop'


def start():
    initCfg()

    pma_dir = getServerDir() + "/phpmyadmin"
    if os.path.exists(pma_dir):
        rand_str = mit.getRandomString(6)
        rand_str = rand_str.lower()
        pma_dir_dst = pma_dir + "_" + rand_str
        mit.execShell("mv " + pma_dir + " " + pma_dir_dst)
        setCfg('path', 'phpmyadmin_' + rand_str)

    file_tpl = getConfTpl()
    file_run = getConf()
    if not os.path.exists(file_run):
        centent = mit.readFile(file_tpl)
        centent = contentReplace(centent)
        mit.writeFile(file_run, centent)

    pma_path = getServerDir() + '/pma.pass'
    if not os.path.exists(pma_path):
        username = mit.getRandomString(10)
        pass_cmd = username + ':' + mit.hasPwd(username)
        setCfg('username', username)
        setCfg('password', username)
        mit.writeFile(pma_path, pass_cmd)

    tmp = getServerDir() + "/" + getCfg()["path"] + '/tmp'
    if not os.path.exists(tmp):
        os.mkdir(tmp)
        mit.execShell("chown -R www:www " + tmp)

    conf_run = getServerDir() + "/" + getCfg()["path"] + '/config.inc.php'
    if not os.path.exists(conf_run):
        conf_tpl = getPluginDir() + '/conf/config.inc.php'
        centent = mit.readFile(conf_tpl)
        centent = contentReplace(centent)
        mit.writeFile(conf_run, centent)

    log_a = accessLog()
    log_e = errorLog()

    for i in [log_a, log_e]:
        if os.path.exists(i):
            cmd = "echo '' > " + i
            mit.execShell(cmd)

    mit.restartWeb()
    return 'ok'


def stop():
    conf = getConf()
    if os.path.exists(conf):
        os.remove(conf)
    mit.restartWeb()
    return 'ok'


def restart():
    return start()


def reload():
    file_tpl = getConfTpl()
    file_run = getConf()
    if os.path.exists(file_run):
        centent = mit.readFile(file_tpl)
        centent = contentReplace(centent)
        mit.writeFile(file_run, centent)
    return start()


def setPhpVer():
    args = getArgs()

    if not 'phpver' in args:
        return 'phpver missing'

    cacheFile = getServerDir() + '/php.pl'
    mit.writeFile(cacheFile, args['phpver'])

    file_tpl = getConfTpl()
    file_run = getConf()

    content = mit.readFile(file_tpl)
    content = contentReplace(content)
    mit.writeFile(file_run, content)

    mit.restartWeb()
    return 'ok'


def getSetPhpVer():
    cacheFile = getServerDir() + '/php.pl'
    if os.path.exists(cacheFile):
        return mit.readFile(cacheFile).strip()
    return ''


def getPmaOption():
    data = getCfg()
    return mit.returnJson(True, 'ok', data)


def getPmaPort():
    try:
        port = getPort()
        return mit.returnJson(True, 'OK', port)
    except Exception as e:
        # print(e)
        return mit.returnJson(False, 'Plugin not started!')


def setPmaPort():
    args = getArgs()
    data = checkArgs(args, ['port'])
    if not data[0]:
        return data[1]

    port = args['port']
    if port == '80':
        return mit.returnJson(False, '80 can not be used!')

    file = getConf()
    if not os.path.exists(file):
        return mit.returnJson(False, 'Plugin not started!')
    content = mit.readFile(file)
    rep, fmt = getPortRep()
    content = re.sub(rep, fmt.format(port), content, 1)
    mit.writeFile(file, content)

    setCfg("port", port)
    mit.restartWeb()
    return mit.returnJson(True, 'Successfully modified!')


def setPmaChoose():
    args = getArgs()
    data = checkArgs(args, ['choose'])
    if not data[0]:
        return data[1]

    choose = args['choose']
    setCfg('choose', choose)

    pma_path = getCfg()['path']
    conf_run = getServerDir() + "/" + pma_path + '/config.inc.php'

    conf_tpl = getPluginDir() + '/conf/config.inc.php'
    content = mit.readFile(conf_tpl)
    content = contentReplace(content)
    mit.writeFile(conf_run, content)

    mit.restartWeb()
    return mit.returnJson(True, 'Successfully modified!')


def setPmaUsername():
    args = getArgs()
    data = checkArgs(args, ['username'])
    if not data[0]:
        return data[1]

    username = args['username']
    setCfg('username', username)

    cfg = getCfg()
    pma_path = getServerDir() + '/pma.pass'
    username = mit.getRandomString(10)
    pass_cmd = cfg['username'] + ':' + mit.hasPwd(cfg['password'])
    mit.writeFile(pma_path, pass_cmd)

    mit.restartWeb()
    return mit.returnJson(True, 'Successfully modified!')


def setPmaPassword():
    args = getArgs()
    data = checkArgs(args, ['password'])
    if not data[0]:
        return data[1]

    password = args['password']
    setCfg('password', password)

    cfg = getCfg()
    pma_path = getServerDir() + '/pma.pass'
    username = mit.getRandomString(10)
    pass_cmd = cfg['username'] + ':' + mit.hasPwd(cfg['password'])
    mit.writeFile(pma_path, pass_cmd)

    mit.restartWeb()
    return mit.returnJson(True, 'Successfully modified!')


def setPmaPath():
    args = getArgs()
    data = checkArgs(args, ['path'])
    if not data[0]:
        return data[1]

    path = args['path']

    if len(path) < 5:
        return mit.returnJson(False, 'Cannot be less than 5 digits!')

    old_path = getServerDir() + "/" + getCfg()['path']
    new_path = getServerDir() + "/" + path

    mit.execShell("mv " + old_path + " " + new_path)
    setCfg('path', path)
    return mit.returnJson(True, 'Successfully modified!')


def accessLog():
    return getServerDir() + '/access.log'


def errorLog():
    return getServerDir() + '/error.log'


def Version():
    return mit.readFile(getServerDir() + '/version.pl')


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
    elif func == 'conf':
        print(getConf())
    elif func == 'version':
        print(Version())
    elif func == 'get_cfg':
        print(returnCfg())
    elif func == 'config_inc':
        print(getConfInc())
    elif func == 'get_home_page':
        print(getHomePage())
    elif func == 'set_php_ver':
        print(setPhpVer())
    elif func == 'get_set_php_ver':
        print(getSetPhpVer())
    elif func == 'get_pma_port':
        print(getPmaPort())
    elif func == 'set_pma_port':
        print(setPmaPort())
    elif func == 'get_pma_option':
        print(getPmaOption())
    elif func == 'set_pma_choose':
        print(setPmaChoose())
    elif func == 'set_pma_username':
        print(setPmaUsername())
    elif func == 'set_pma_password':
        print(setPmaPassword())
    elif func == 'set_pma_path':
        print(setPmaPath())
    elif func == 'access_log':
        print(accessLog())
    elif func == 'error_log':
        print(errorLog())
    else:
        print('error')
