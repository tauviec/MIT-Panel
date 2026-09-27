# coding: utf-8

import psutil
import time
import os
import sys
import mit
import re
import json
import pwd

from flask import session
from flask import request


class config_api:

    __version = '4.17'
    __api_addr = 'data/api.json'

    def __init__(self):
        pass

    def getVersion(self):
        return self.__version

    ##### ----- start ----- ###

    def getPanelListApi(self):
        data = mit.M('panel').field(
            'id,title,url,username,password,click,addtime').order('click desc').select()
        return mit.getJson(data)

    def addPanelInfoApi(self):
        title = request.form.get('title', '')
        url = request.form.get('url', '')
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        isAdd = mit.M('panel').where(
            'title=? OR url=?', (title, url)).count()
        if isAdd:
            return mit.returnJson(False, 'Alamat paanel sudah terdaftar!')
        isRe = mit.M('panel').add('title,url,username,password,click,addtime',
                                 (title, url, username, password, 0, int(time.time())))
        if isRe:
            return mit.returnJson(True, 'Alamat panel berhasil ditambah!')
        return mit.returnJson(False, 'Penambahan alamat panel gagal!')

    def delPanelInfoApi(self):
        mid = request.form.get('id', '')
        isExists = mit.M('panel').where('id=?', (mid,)).count()
        if not isExists:
            return mit.returnJson(False, 'Data alamat panel yang diinginkan tidak ada!')
        mit.M('panel').where('id=?', (mid,)).delete()
        return mit.returnJson(True, 'Data alamat panel berhasil dihapus!')

    def setPanelInfoApi(self):
        title = request.form.get('title', '')
        url = request.form.get('url', '')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        mid = request.form.get('id', '')
        isSave = mit.M('panel').where(
            '(title=? OR url=?) AND id!=?', (title, url, mid)).count()
        if isSave:
            return mit.returnJson(False, 'Alamat paanel sudah terdaftar!')

        isRe = mit.M('panel').where('id=?', (mid,)).save(
            'title,url,username,password', (title, url, username, password))
        if isRe:
            return mit.returnJson(True, 'Alamat panel berhasil diubah!')
        return mit.returnJson(False, 'Gagal mengganti alamat panel!')

    def syncDateApi(self):
        if mit.isAppleSystem():
            return mit.returnJson(True, 'Sinkronisasi waktu tidak disupport!')

        data = mit.execShell('ntpdate -s time.nist.gov')
        if data[0] == '':
            return mit.returnJson(True, 'Sinkronisasi waktu berhasil dilakukan!')
        return mit.returnJson(False, 'Sinkronisasi waktu gagal:' + data[0])

    def setPasswordApi(self):
        password1 = request.form.get('password1', '')
        password2 = request.form.get('password2', '')
        if password1 != password2:
            return mit.returnJson(False, 'Kata sandi yang dimasukkan dua kali tidak cocok, harap masukkan kembali!')
        if len(password1) < 5:
            return mit.returnJson(False, 'Kata sandi pengguna tidak boleh kurang dari 5 digit!')
        mit.M('users').where("username=?", (session['username'],)).setField(
            'password', mit.md5(password1.strip()))
        return mit.returnJson(True, 'Penyetelan ulang kata sandi selesai!')

    def setNameApi(self):
        name1 = request.form.get('name1', '')
        name2 = request.form.get('name2', '')
        if name1 != name2:
            return mit.returnJson(False, 'Nama pengguna yang dimasukkan dua kali tidak cocok, harap masukkan kembali!')
        if len(name1) < 3:
            return mit.returnJson(False, 'Nama pengguna minimal 3 karakter')

        mit.M('users').where("username=?", (session['username'],)).setField(
            'username', name1.strip())

        session['username'] = name1
        return mit.returnJson(True, 'Akun pengguna berhasil dimodifikasi!')

    def setWebnameApi(self):
        webname = request.form.get('webname', '')
        if webname != mit.getConfig('title'):
            mit.setConfig('title', webname)
        return mit.returnJson(True, 'Alias panel berhasil disimpan!')

    def setPortApi(self):
        port = request.form.get('port', '')
        if port != mit.getHostPort():
            import system_api
            import firewall_api

            sysCfgDir = mit.systemdCfgDir()
            if os.path.exists(sysCfgDir + "/firewalld.service"):
                if not firewall_api.firewall_api().getFwStatus():
                    return mit.returnJson(False, 'firewalld must be started first!')

            mit.setHostPort(port)

            msg = mit.getInfo('Successfully released port [{1}]', (port,))
            mit.writeLog("Firewall management", msg)
            addtime = time.strftime('%Y-%m-%d %X', time.localtime())
            mit.M('firewall').add('port,ps,addtime', (port, "Configuration modification", addtime))

            firewall_api.firewall_api().addAcceptPort(port)
            firewall_api.firewall_api().firewallReload()

            system_api.system_api().restartMit()

        return mit.returnJson(True, 'Port berhasil disimpan!')

    def setIpApi(self):
        host_ip = request.form.get('host_ip', '')
        if host_ip != mit.getHostAddr():
            mit.setHostAddr(host_ip)
        return mit.returnJson(True, 'IP berhasil disimpan!')

    def setWwwDirApi(self):
        sites_path = request.form.get('sites_path', '')
        if sites_path != mit.getWwwDir():
            mit.setWwwDir(sites_path)
        return mit.returnJson(True, 'Berhasil ubah folder website bawaan!')

    def setBackupDirApi(self):
        backup_path = request.form.get('backup_path', '')
        if backup_path != mit.getBackupDir():
            mit.setBackupDir(backup_path)
        return mit.returnJson(True, 'Berhasil ubah folder backup bawaan!')

    def setBasicAuthApi(self):
        basic_user = request.form.get('basic_user', '').strip()
        basic_pwd = request.form.get('basic_pwd', '').strip()
        basic_open = request.form.get('is_open', '').strip()

        salt = '_md_salt'
        path = 'data/basic_auth.json'
        is_open = True

        if basic_open == 'false':
            if os.path.exists(path):
                os.remove(path)
            return mit.returnJson(True, 'Berhasil hapus BasicAuth!')

        if basic_user == '' or basic_pwd == '':
            return mit.returnJson(True, 'User and password cannot be empty!')

        ba_conf = None
        if os.path.exists(path):
            try:
                ba_conf = json.loads(mit.readFile(path))
            except:
                os.remove(path)

        if not ba_conf:
            ba_conf = {
                "basic_user": mit.md5(basic_user + salt),
                "basic_pwd": mit.md5(basic_pwd + salt),
                "open": is_open
            }
        else:
            ba_conf['basic_user'] = mit.md5(basic_user + salt)
            ba_conf['basic_pwd'] = mit.md5(basic_pwd + salt)
            ba_conf['open'] = is_open

        mit.writeFile(path, json.dumps(ba_conf))
        os.chmod(path, 384)
        mit.writeLog('Panel settings', 'Set the BasicAuth state to: %s' % is_open)

        mit.restartMit()
        return mit.returnJson(True, 'Berhasil diatur!')

    def setApi(self):
        webname = request.form.get('webname', '')
        port = request.form.get('port', '')
        host_ip = request.form.get('host_ip', '')
        domain = request.form.get('domain', '')
        sites_path = request.form.get('sites_path', '')
        backup_path = request.form.get('backup_path', '')

        if domain != '':
            reg = r"^([\w\-\*]{1,100}\.){1,4}(\w{1,10}|\w{1,10}\.\w{1,10})$"
            if not re.match(reg, domain):
                return mit.returnJson(False, 'Format nama domain utama salah')

        if int(port) >= 65535 or int(port) < 100:
            return mit.returnJson(False, 'Rentang port salah!')

        if webname != mit.getConfig('title'):
            mit.setConfig('title', webname)

        if sites_path != mit.getWwwDir():
            mit.setWwwDir(sites_path)

        if backup_path != mit.getWwwDir():
            mit.setBackupDir(backup_path)

        if port != mit.getHostPort():
            import system_api
            import firewall_api

            sysCfgDir = mit.systemdCfgDir()
            if os.path.exists(sysCfgDir + "/firewalld.service"):
                if not firewall_api.firewall_api().getFwStatus():
                    return mit.returnJson(False, 'Firewalld harus dijalankan terlebih dahulu!')

            mit.setHostPort(port)

            msg = mit.getInfo('Port [{1}] berhasil dibuka', (port,))
            mit.writeLog("Manajemen Firewall", msg)
            addtime = time.strftime('%Y-%m-%d %X', time.localtime())
            mit.M('firewall').add('port,ps,addtime', (port, "Modifikasi konfigurasi", addtime))

            firewall_api.firewall_api().addAcceptPort(port)
            firewall_api.firewall_api().firewallReload()

            system_api.system_api().restartMit()

        if host_ip != mit.getHostAddr():
            mit.setHostAddr(host_ip)

        mhost = mit.getHostAddr()
        info = {
            'uri': '/config',
            'host': mhost + ':' + port
        }
        return mit.returnJson(True, 'Berhasil disimpan!', info)

    def setAdminPathApi(self):
        admin_path = request.form.get('admin_path', '').strip()
        admin_path_checks = ['/', '/close', '/login',
                             '/do_login', '/site', '/sites',
                             '/download_file', '/control', '/crontab',
                             '/firewall', '/files', 'config',
                             '/soft', '/system', '/code',
                             '/ssl', '/plugins', '/hook']
        if admin_path == '':
            admin_path = '/'
        if admin_path != '/':
            if len(admin_path) < 6:
                return mit.returnJson(False, 'Panjang alamat login tidak boleh kurang dari 6 karakter!')
            if admin_path in admin_path_checks:
                return mit.returnJson(False, 'Path login sudah digunakan oleh panel, silakan gunakan alamat login yang lain!')
            if not re.match(r"^/[\w\./-_]+$", admin_path):
                return mit.returnJson(False, 'Format alamat login salah, contoh: /random_string')

        admin_path_file = 'data/admin_path.pl'
        admin_path_old = '/'
        if os.path.exists(admin_path_file):
            admin_path_old = mit.readFile(admin_path_file).strip()

        if admin_path_old != admin_path:
            mit.writeFile(admin_path_file, admin_path)
            mit.restartMit()
        return mit.returnJson(True, 'Berhasil dimodifikasi!')

    def closePanelApi(self):
        filename = 'data/close.pl'
        if os.path.exists(filename):
            os.remove(filename)
            return mit.returnJson(True, 'Panel sudah dibuka')
        mit.writeFile(filename, 'True')
        mit.execShell("chmod 600 " + filename)
        mit.execShell("chown root.root " + filename)
        return mit.returnJson(True, 'Panel ditutup!')

    def openDebugApi(self):
        filename = 'data/debug.pl'
        if os.path.exists(filename):
            os.remove(filename)
            return mit.returnJson(True, 'Development mode off!')
        mit.writeFile(filename, 'True')
        return mit.returnJson(True, 'Development mode on!')

    def setIpv6StatusApi(self):
        ipv6_file = 'data/ipv6.pl'
        if os.path.exists('data/ipv6.pl'):
            os.remove(ipv6_file)
            mit.writeLog('Pengaturan panel', 'Tutup panel dengan IPv6!')
        else:
            mit.writeFile(ipv6_file, 'True')
            mit.writeLog('Pengaturan panel', 'Aktifkan panel dengan IPv6!')
        mit.restartMit()
        return mit.returnJson(True, 'Pengaturan berhasil!')

    def getPanelSslApi(self):
        cert = self.getPanelSslData()
        return mit.getJson(cert)

    def getPanelSslData(self):
        cert = {}
        keyPath = 'ssl/private.pem'
        certPath = 'ssl/cert.pem'
        if not os.path.exists(certPath):
            # mit.createSSL()
            cert['privateKey'] = ''
            cert['is_https'] = ''
            cert['certPem'] = ''
            cert['rep'] = os.path.exists('ssl/input.pl')
            cert['info'] = {'endtime': 0, 'subject': 'no',
                            'notAfter': 'no', 'notBefore': 'no', 'issuer': 'no'}
            return cert

        panel_ssl = mit.getWebConfDir() + "/vhost/panel.conf"
        if not os.path.exists(panel_ssl):
            cert['is_https'] = ''
        else:
            ssl_data = mit.readFile(panel_ssl)
            if ssl_data.find('$server_port !~ 443') != -1 or ssl_data.find('RewriteCond %{SERVER_PORT} !^443$') != -1:
                cert['is_https'] = 'checked'

        cert['privateKey'] = mit.readFile(keyPath)
        cert['certPem'] = mit.readFile(certPath)
        cert['rep'] = os.path.exists('ssl/input.pl')
        cert['info'] = mit.getCertName(certPath)
        return cert

    def savePanelSslApi(self):
        keyPath = 'ssl/private.pem'
        certPath = 'ssl/cert.pem'
        checkCert = '/tmp/cert.pl'

        certPem = request.form.get('certPem', '').strip()
        privateKey = request.form.get('privateKey', '').strip()

        if(privateKey.find('KEY') == -1):
            return mit.returnJson(False, 'The key is wrong, please check!')
        if(certPem.find('CERTIFICATE') == -1):
            return mit.returnJson(False, 'Certificate error, please check!')

        mit.writeFile(checkCert, certPem)
        if privateKey:
            mit.writeFile(keyPath, privateKey)
        if certPem:
            mit.writeFile(certPath, certPem)
        if not mit.checkCert(checkCert):
            return mit.returnJson(False, 'Certificate error, please check!')
        mit.writeFile('ssl/input.pl', 'True')
        return mit.returnJson(True, 'Certificate saved!')

    def setPanelHttpToHttpsApi(self):

        bind_domain = 'data/bind_domain.pl'
        if not os.path.exists(bind_domain):
            return mit.returnJson(False, 'Bind the domain name first!')

        keyPath = 'ssl/private.pem'
        if not os.path.exists(keyPath):
            return mit.returnJson(False, 'No SSL certificate applied!')

        is_https = request.form.get('https', '').strip()

        panel_ssl = mit.getWebConfDir() + "/vhost/panel.conf"
        if not os.path.exists(panel_ssl):
            return mit.returnJson(False, 'Panel SSL is not turned on!')

        if mit.isApache():
            import site_apache
            conf = mit.readFile(panel_ssl)
            if is_https == 'false' and not site_apache.hasSsl(conf):
                return mit.returnJson(False, 'SSL is not currently enabled')
            mit.writeFile(panel_ssl, site_apache.setHttpsRedirect(conf, is_https == 'false'))
        elif is_https == 'false':
            conf = mit.readFile(panel_ssl)
            if conf:
                if conf.find('ssl_certificate') == -1:
                    return mit.returnJson(False, 'SSL is not currently enabled')
                to = "#error_page 404/404.html;\n\
    #HTTP_TO_HTTPS_START\n\
    if ($server_port !~ 443){\n\
        rewrite ^(/.*)$ https://$host$1 permanent;\n\
    }\n\
    #HTTP_TO_HTTPS_END"
                conf = conf.replace('#error_page 404/404.html;', to)
                mit.writeFile(panel_ssl, conf)
        else:
            conf = mit.readFile(panel_ssl)
            if conf:
                rep = r"\n\s*#HTTP_TO_HTTPS_START(.|\n){1,300}#HTTP_TO_HTTPS_END"
                conf = re.sub(rep, '', conf)
                rep = r"\s+if.+server_port.+\n.+\n\s+\s*}"
                conf = re.sub(rep, '', conf)
                mit.writeFile(panel_ssl, conf)

        mit.restartWeb()

        action = 'Turn on'
        if is_https == 'true':
            action = 'Turn off'
        return mit.returnJson(True, action + 'HTTPS jump successfully!')

    def delPanelSslApi(self):
        bind_domain = 'data/bind_domain.pl'
        if not os.path.exists(bind_domain):
            return mit.returnJson(False, 'Unbound domain name!')

        siteName = mit.readFile(bind_domain).strip()

        src_letpath = mit.getServerDir() + '/web_conf/letsencrypt/' + siteName

        dst_letpath = mit.getRunDir() + '/ssl'
        dst_csrpath = dst_letpath + '/cert.pem'
        dst_keypath = dst_letpath + '/private.pem'

        if os.path.exists(src_letpath) or os.path.exists(dst_csrpath):
            if os.path.exists(src_letpath):
                mit.execShell('rm -rf ' + src_letpath)
            if os.path.exists(dst_csrpath):
                mit.execShell('rm -rf ' + dst_csrpath)
            if os.path.exists(dst_keypath):
                mit.execShell('rm -rf ' + dst_keypath)
            # mit.restartWeb()
            return mit.returnJson(True, 'SSL removed!')

        # mit.restartWeb()
        return mit.returnJson(False, 'SSL no longer exists!')

    def applyPanelLetSslApi(self):

        # check domain is bind?
        bind_domain = 'data/bind_domain.pl'
        if not os.path.exists(bind_domain):
            return mit.returnJson(False, 'Bind the domain name first!')

        siteName = mit.readFile(bind_domain).strip()
        auth_to = mit.getRunDir() + "/tmp"
        to_args = {
            'domains': [siteName],
            'auth_type': 'http',
            'auth_to': auth_to,
        }

        src_letpath = mit.getServerDir() + '/web_conf/letsencrypt/' + siteName
        src_csrpath = src_letpath + "/fullchain.pem"
        src_keypath = src_letpath + "/privkey.pem"

        dst_letpath = mit.getRunDir() + '/ssl'
        dst_csrpath = dst_letpath + '/cert.pem'
        dst_keypath = dst_letpath + '/private.pem'

        is_already_apply = False

        if not os.path.exists(src_letpath):
            import cert_api
            data = cert_api.cert_api().applyCertApi(to_args)
            if not data['status']:
                msg = data['msg']
                if type(data['msg']) != str:
                    msg = data['msg'][0]
                    emsg = data['msg'][1]['challenges'][0]['error']
                    msg = msg + '<p><span>Response status:</span>' + str(emsg['status']) + '</p><p><span>Error type:</span>' + emsg[
                        'type'] + '</p><p><span>Error code:</span>' + emsg['detail'] + '</p>'
                return mit.returnJson(data['status'], msg, data['msg'])

        else:
            is_already_apply = True

        mit.buildSoftLink(src_csrpath, dst_csrpath, True)
        mit.buildSoftLink(src_keypath, dst_keypath, True)
        mit.execShell('echo "lets" > "' + dst_letpath + '/README"')

        data = self.getPanelSslData()

        tmp_well_know = auth_to + '/.well-known'
        if os.path.exists(tmp_well_know):
            mit.execShell('rm -rf ' + tmp_well_know)

        if is_already_apply:
            return mit.returnJson(True, 'Repeat application!', data)

        return mit.returnJson(True, 'Successful application!', data)

    def getPanelTpl(self):
        if mit.isApache():
            return mit.getRunDir() + "/data/tpl/apache_panel.conf"
        return mit.getRunDir() + "/data/tpl/nginx_panel.conf"

    def setPanelDomainApi(self):
        domain = request.form.get('domain', '')

        panel_tpl = self.getPanelTpl()
        dst_panel_path = mit.getWebConfDir() + "/vhost/panel.conf"

        cfg_domain = 'data/bind_domain.pl'
        if domain == '':
            os.remove(cfg_domain)
            os.remove(dst_panel_path)
            mit.restartWeb()
            return mit.returnJson(True, 'Nama domain berhasil dibersihin!')

        reg = r"^([\w\-\*]{1,100}\.){1,4}(\w{1,10}|\w{1,10}\.\w{1,10})$"
        if not re.match(reg, domain):
            return mit.returnJson(False, 'Primary domain name format is incorrect')

        if not mit.isInstalledWeb():
            return mit.returnJson(False, 'Rely on Nginx or Apache, first install and start it!')

        content = mit.readFile(panel_tpl)
        content = content.replace("{$PORT}", "80")
        content = content.replace("{$SERVER_NAME}", domain)
        content = content.replace("{$PANAL_PORT}", mit.readFile('data/port.pl'))
        content = content.replace("{$LOGPATH}", mit.getRunDir() + '/logs')
        content = content.replace("{$PANAL_ADDR}", mit.getRunDir())
        mit.writeFile(dst_panel_path, content)
        mit.restartWeb()

        mit.writeFile(cfg_domain, domain)
        return mit.returnJson(True, 'Berhasil atur nama domain!')

    def setPanelSslApi(self):
        sslConf = mit.getRunDir() + '/data/ssl.pl'

        panel_tpl = self.getPanelTpl()
        dst_panel_path = mit.getWebConfDir() + "/vhost/panel.conf"
        if os.path.exists(sslConf):
            os.system('rm -f ' + sslConf)

            conf = mit.readFile(dst_panel_path)
            if conf and mit.isApache():
                import site_apache
                mit.writeFile(dst_panel_path, site_apache.removeSsl(conf))
            elif conf:
                rep = r"\s+ssl_certificate\s+.+;\s+ssl_certificate_key\s+.+;"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl_protocols\s+.+;\n"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl_ciphers\s+.+;\n"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl_prefer_server_ciphers\s+.+;\n"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl_session_cache\s+.+;\n"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl_session_timeout\s+.+;\n"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl_ecdh_curve\s+.+;\n"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl_session_tickets\s+.+;\n"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl_stapling\s+.+;\n"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl_stapling_verify\s+.+;\n"
                conf = re.sub(rep, '', conf)
                rep = r"\s+ssl\s+on;"
                conf = re.sub(rep, '', conf)
                rep = r"\s+error_page\s497.+;"
                conf = re.sub(rep, '', conf)
                rep = r"\s+if.+server_port.+\n.+\n\s+\s*}"
                conf = re.sub(rep, '', conf)
                rep = r"\s+listen\s+443.*;"
                conf = re.sub(rep, '', conf)
                rep = r"\s+listen\s+\[\:\:\]\:443.*;"
                conf = re.sub(rep, '', conf)
                mit.writeFile(dst_panel_path, conf)

            mit.writeLog('Panel configuration', 'Panel SSL closed successfully!')
            mit.restartWeb()
            return mit.returnJson(True, 'SSL is closed, please use the http protocol to access the panel!')
        else:
            try:
                if not os.path.exists('ssl/input.ssl'):
                    mit.createSSL()
                mit.writeFile(sslConf, 'True')

                keyPath = mit.getRunDir() + '/ssl/private.pem'
                certPath = mit.getRunDir() + '/ssl/cert.pem'

                conf = mit.readFile(dst_panel_path)
                if conf and mit.isApache():
                    import site_apache
                    mit.backFile(dst_panel_path)
                    mit.writeFile(dst_panel_path, site_apache.addSsl(conf, certPath, keyPath))
                    isError = mit.checkWebConfig()
                    if(isError != True):
                        mit.restoreFile(dst_panel_path)
                        return mit.returnJson(False, 'Certificate error: <br><a style="color:red;">' + isError.replace("\n", '<br>') + '</a>')
                elif conf:
                    if conf.find('ssl_certificate') == -1:
                        sslStr = """#error_page 404/404.html;
    ssl_certificate    %s;
    ssl_certificate_key  %s;
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:HIGH:!aNULL:!MD5:!RC4:!DHE;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    error_page 497  https://$host$request_uri;""" % (certPath, keyPath)
                    if(conf.find('ssl_certificate') != -1):
                        return mit.returnJson(True, 'SSL opened successfully!')

                    conf = conf.replace('#error_page 404/404.html;', sslStr)

                    rep = r"listen\s+([0-9]+)\s*[default_server]*;"
                    tmp = re.findall(rep, conf)
                    if not mit.inArray(tmp, '443'):
                        listen = re.search(rep, conf).group()
                        http_ssl = "\n\tlisten 443 ssl http2;"
                        # http_ssl = http_ssl + "\n\tlisten [::]:443 ssl http2;"
                        conf = conf.replace(listen, listen + http_ssl)

                    mit.backFile(dst_panel_path)
                    mit.writeFile(dst_panel_path, conf)
                    isError = mit.checkWebConfig()
                    if(isError != True):
                        mit.restoreFile(dst_panel_path)
                        return mit.returnJson(False, 'Certificate error: <br><a style="color:red;">' + isError.replace("\n", '<br>') + '</a>')
            except Exception as ex:
                return mit.returnJson(False, 'Failed to open:' + str(ex))
            mit.restartWeb()
            return mit.returnJson(True, 'Open successfully, please use the https protocol to access the panel!')

    def getApi(self):
        data = {}
        return mit.getJson(data)
    ##### ----- end ----- ###

    def getTempLoginApi(self):
        if 'tmp_login_expire' in session:
            return mit.returnJson(False, 'Permission denied')
        limit = request.form.get('limit', '10').strip()
        p = request.form.get('p', '1').strip()
        tojs = request.form.get('tojs', '').strip()

        tempLoginM = mit.M('temp_login')
        tempLoginM.where('state=? and expire<?',
                         (0, int(time.time()))).setField('state', -1)

        start = (int(p) - 1) * (int(limit))
        vlist = tempLoginM.limit(str(start) + ',' + str(limit)).order('id desc').field(
            'id,addtime,expire,login_time,login_addr,state').select()

        data = {}
        data['data'] = vlist

        count = tempLoginM.count()
        page_args = {}
        page_args['count'] = count
        page_args['tojs'] = 'get_temp_login'
        page_args['p'] = p
        page_args['row'] = limit

        data['page'] = mit.getPage(page_args)
        return mit.getJson(data)

    def removeTempLoginApi(self):
        if 'tmp_login_expire' in session:
            return mit.returnJson(False, 'Permission denied')
        sid = request.form.get('id', '10').strip()
        if mit.M('temp_login').where('id=?', (sid,)).delete():
            mit.writeLog('Panel settings', 'Delete temporary login connection')
            return mit.returnJson(True, 'Berhasil dihapus')
        return mit.returnJson(False, 'Failed to delete')

    def setTempLoginApi(self):
        if 'tmp_login_expire' in session:
            return mit.returnJson(False, 'Permission denied')
        s_time = int(time.time())
        mit.M('temp_login').where(
            'state=? and expire>?', (0, s_time)).delete()
        token = mit.getRandomString(48)
        salt = mit.getRandomString(12)

        pdata = {
            'token': mit.md5(token + salt),
            'salt': salt,
            'state': 0,
            'login_time': 0,
            'login_addr': '',
            'expire': s_time + 3600,
            'addtime': s_time
        }

        if not mit.M('temp_login').count():
            pdata['id'] = 101

        if mit.M('temp_login').insert(pdata):
            mit.writeLog('Panel settings', 'Generate temporary connection, expiration time:{}'.format(
                mit.formatDate(times=pdata['expire'])))
            return mit.getJson({'status': True, 'msg': "Koneksi sementara udah dibuat", 'token': token, 'expire': pdata['expire']})
        return mit.returnJson(False, 'Connection generation failed')

    def getTempLoginLogsApi(self):
        if 'tmp_login_expire' in session:
            return mit.returnJson(False, 'Permission denied')

        logs_id = request.form.get('id', '').strip()
        logs_id = int(logs_id)
        data = mit.M('logs').where(
            'uid=?', (logs_id,)).order('id desc').field(
            'id,type,uid,log,addtime').select()
        return mit.returnJson(False, 'ok', data)

    def checkPanelToken(self):
        api_file = self.__api_addr
        if not os.path.exists(api_file):
            return False, ''

        tmp = mit.readFile(api_file)
        data = json.loads(tmp)
        if data['open']:
            return True, data
        else:
            return False, ''

    def setStatusCodeApi(self):
        status_code = request.form.get('status_code', '').strip()
        if re.match(r"^\d+$", status_code):
            status_code = int(status_code)
            if status_code != 0:
                if status_code < 100 or status_code > 999:
                    return mit.returnJson(False, 'Status code range error!')
        else:
            return mit.returnJson(False, 'Status code range error!')

        mit.writeFile('data/unauthorized_status.pl', str(status_code))
        mit.writeLog('Panel settings', 'Set the Unauthorized response status code to:{}'.format(status_code))
        return mit.returnJson(True, 'Berhasil diatur!')

    def getNotifyApi(self):
        data = mit.getNotifyData(True)
        return mit.returnData(True, 'ok', data)

    def setNotifyApi(self):
        tag = request.form.get('tag', '').strip()
        data = request.form.get('data', '').strip()

        cfg = mit.getNotifyData(False)

        crypt_data = mit.enDoubleCrypt(tag, data)
        if tag in cfg:
            cfg[tag]['cfg'] = crypt_data
        else:
            t = {'cfg': crypt_data}
            cfg[tag] = t

        mit.writeNotify(cfg)
        return mit.returnData(True, 'Berhasil diatur')

    def setNotifyTestApi(self):
        tag = request.form.get('tag', '').strip()
        tag_data = request.form.get('data', '').strip()

        if tag == 'tgbot':
            t = json.loads(tag_data)
            test_bool = mit.tgbotNotifyTest(t['app_token'], t['chat_id'])
            if test_bool:
                return mit.returnData(True, 'Verifikasi berhasil')
            return mit.returnData(False, 'Verification failed')

        return mit.returnData(False, 'This verification is not currently supported')

    def setNotifyEnableApi(self):
        tag = request.form.get('tag', '').strip()
        tag_enable = request.form.get('enable', '').strip()

        data = mit.getNotifyData(False)
        op_enable = True
        op_action = 'Turn on'
        if tag_enable != 'true':
            op_enable = False
            op_action = 'Turn off'

        if tag in data:
            data[tag]['enable'] = op_enable

        mit.writeNotify(data)

        return mit.returnData(True, op_action + 'success')

    def getPanelTokenApi(self):
        api_file = self.__api_addr
        tmp = mit.readFile(api_file)
        if not os.path.exists(api_file):
            ready_data = {"open": False, "token": "", "limit_addr": []}
            mit.writeFile(api_file, json.dumps(ready_data))
            mit.execShell("chmod 600 " + api_file)
            tmp = mit.readFile(api_file)
        data = json.loads(tmp)

        if not 'key' in data:
            data['key'] = mit.getRandomString(16)
            mit.writeFile(api_file, json.dumps(data))

        if 'token_crypt' in data:
            data['token'] = mit.deCrypt(data['token'], data['token_crypt'])
        else:
            token = mit.getRandomString(32)
            data['token'] = mit.md5(token)
            data['token_crypt'] = mit.enCrypt(
                data['token'], token)
            mit.writeFile(api_file, json.dumps(data))
            data['token'] = "***********************************"

        data['limit_addr'] = '\n'.join(data['limit_addr'])

        del(data['key'])
        return mit.returnJson(True, 'ok', data)

    def setPanelTokenApi(self):
        op_type = request.form.get('op_type', '').strip()

        if op_type == '1':
            token = mit.getRandomString(32)
            data['token'] = mit.md5(token)
            data['token_crypt'] = mit.enCrypt(
                data['token'], token).decode('utf-8')
            mit.writeLog('API configuration', 'Regenerate API-Token')
            mit.writeFile(api_file, json.dumps(data))
            return mit.returnJson(True, 'ok', token)

        api_file = self.__api_addr
        if not os.path.exists(api_file):
            return mit.returnJson(False, "First configure the API interface")
        else:
            tmp = mit.readFile(api_file)
            data = json.loads(tmp)

        if op_type == '2':
            data['open'] = not data['open']
            stats = {True: 'Turn on', False: 'Turn off'}
            if not 'token_crypt' in data:
                token = mit.getRandomString(32)
                data['token'] = mit.md5(token)
                data['token_crypt'] = mit.enCrypt(
                    data['token'], token).decode('utf-8')

            token = stats[data['open']] + 'success!'
            mit.writeLog('API configuration', '%s API interface' % stats[data['open']])
            mit.writeFile(api_file, json.dumps(data))
            return mit.returnJson(not not data['open'], token)

        elif op_type == '3':

            limit_addr = request.form.get('limit_addr', '').strip()
            data['limit_addr'] = limit_addr.split('\n')
            mit.writeLog('API configuration', 'Changing the IP limit is [%s]' % limit_addr)
            mit.writeFile(api_file, json.dumps(data))
            return mit.returnJson(True, 'Saved successfully!')

    def renderUnauthorizedStatus(self, data):
        cfg_unauth_status = 'data/unauthorized_status.pl'
        if os.path.exists(cfg_unauth_status):
            status_code = mit.readFile(cfg_unauth_status)
            data['status_code'] = status_code
            data['status_code_msg'] = status_code
            if status_code == '0':
                data['status_code_msg'] = "Default - Security Entrance Error Prompt"
            elif status_code == '400':
                data['status_code_msg'] = "400 - Client request error"
            elif status_code == '401':
                data['status_code_msg'] = "401 - Unauthorized access"
            elif status_code == '403':
                data['status_code_msg'] = "403 - Access denied"
            elif status_code == '404':
                data['status_code_msg'] = "404 - Page does not exist"
            elif status_code == '408':
                data['status_code_msg'] = "408 - Client timeout"
            elif status_code == '416':
                data['status_code_msg'] = "416 - Invalid Request"
        else:
            data['status_code'] = '0'
            data['status_code_msg'] = "Default - Security Entrance Error Prompt"
        return data

    def get(self):

        data = {}
        data['title'] = mit.getConfig('title')
        data['root_path'] = mit.getRootDir()
        data['site_path'] = mit.getWwwDir()
        data['backup_path'] = mit.getBackupDir()
        sformat = 'date +"%Y-%m-%d %H:%M:%S %Z %z"'
        data['systemdate'] = mit.execShell(sformat)[0].strip()

        data['port'] = mit.getHostPort()
        data['ip'] = mit.getHostAddr()

        admin_path_file = 'data/admin_path.pl'
        if not os.path.exists(admin_path_file):
            data['admin_path'] = '/'
        else:
            data['admin_path'] = mit.readFile(admin_path_file)

        ipv6_file = 'data/ipv6.pl'
        if os.path.exists(ipv6_file):
            data['ipv6'] = 'checked'
        else:
            data['ipv6'] = ''

        debug_file = 'data/debug.pl'
        if os.path.exists(debug_file):
            data['debug'] = 'checked'
        else:
            data['debug'] = ''

        ssl_file = 'data/ssl.pl'
        if os.path.exists('data/ssl.pl'):
            data['ssl'] = 'checked'
        else:
            data['ssl'] = ''

        basic_auth = 'data/basic_auth.json'
        if os.path.exists(basic_auth):
            bac = mit.readFile(basic_auth)
            bac = json.loads(bac)
            if bac['open']:
                data['basic_auth'] = 'checked'
        else:
            data['basic_auth'] = ''

        cfg_domain = 'data/bind_domain.pl'
        if os.path.exists(cfg_domain):
            domain = mit.readFile(cfg_domain)
            data['bind_domain'] = domain.strip()
        else:
            data['bind_domain'] = ''

        data = self.renderUnauthorizedStatus(data)

        api_token = self.__api_addr
        if os.path.exists(api_token):
            bac = mit.readFile(api_token)
            bac = json.loads(bac)
            if bac['open']:
                data['api_token'] = 'checked'
        else:
            data['api_token'] = ''

        data['site_count'] = mit.M('sites').count()

        # Count databases (MySQL/MariaDB)
        database_count = 0
        database_type = ""
        database_version = ""
        try:
            # Check for MySQL
            mysql_dir = os.path.join(mit.getServerDir(), 'mysql')
            mysql_db = os.path.join(mysql_dir, 'mysql.db')
            if os.path.exists(mysql_db):
                import db
                database_count += db.Sql().dbPos(mysql_dir, 'mysql').table('databases').count()
                database_type = "MySQL"
                v_path = os.path.join(mysql_dir, 'version.pl')
                if os.path.exists(v_path):
                    database_version = mit.readFile(v_path).strip()
            
            # Check for MariaDB
            mariadb_dir = os.path.join(mit.getServerDir(), 'mariadb')
            mariadb_db = os.path.join(mariadb_dir, 'mariadb.db')
            if os.path.exists(mariadb_db):
                import db
                database_count += db.Sql().dbPos(mariadb_dir, 'mariadb').table('databases').count()
                if not database_type:
                    database_type = "MariaDB"
                    v_path = os.path.join(mariadb_dir, 'version.pl')
                    if os.path.exists(v_path):
                        database_version = mit.readFile(v_path).strip()
        except:
            pass
        data['database_count'] = database_count
        data['database_type'] = database_type
        data['database_version'] = database_version

        data['username'] = mit.M('users').where(
            "id=?", (1,)).getField('username')

        data['hook_tag'] = request.args.get('tag', '')

        database_hook_file = 'data/hook_database.json'
        if os.path.exists(database_hook_file):
            df = mit.readFile(database_hook_file)
            df = json.loads(df)
            data['hook_database'] = df
        else:
            data['hook_database'] = []

        menu_hook_file = 'data/hook_menu.json'
        if os.path.exists(menu_hook_file):
            df = mit.readFile(menu_hook_file)
            df = json.loads(df)
            data['hook_menu'] = df
        else:
            data['hook_menu'] = []

        # global_static hook
        global_static_hook_file = 'data/hook_global_static.json'
        if os.path.exists(global_static_hook_file):
            df = mit.readFile(global_static_hook_file)
            df = json.loads(df)
            data['hook_global_static'] = df
        else:
            data['hook_global_static'] = []

        # notiy config
        notify_data = mit.getNotifyData(True)
        notify_tag_list = ['tgbot', 'email']
        for tag in notify_tag_list:
            new_tag = 'notify_' + tag + '_enable'
            data[new_tag] = ''
            if tag in notify_data and 'enable' in notify_data[tag]:
                if notify_data[tag]['enable']:
                    data[new_tag] = 'checked'

        return data
