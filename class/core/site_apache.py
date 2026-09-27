# coding: utf-8

# Apache (httpd 2.4) counterpart of the nginx vhost handling in site_api.
#
# The vhost files keep the same marker comments as the nginx ones
# (#301-START, #PROXY-START, #AUTH_START, #SECURITY-START, #BINDING-x-START ...)
# so the generic parts of site_api keep working; only the directives differ.
#
# Layout of a site vhost (web_conf/apache/vhost/<site>.conf):
#   <VirtualHost *:80 *:8080>     main block, one address per domain port
#   #SSL-VHOST-START
#   <VirtualHost *:443>           copy of the main block with SSL directives
#   #SSL-VHOST-END
#   #BINDING-sub.example.com-START
#   <VirtualHost *:80>            one block per sub-directory binding
#   #BINDING-sub.example.com-END

import os
import re
import json

from urllib.parse import urlparse

import mit


REP_BLOCK = r'<VirtualHost\s+[^>]+>(?:.|\n)*?</VirtualHost>'
REP_BINDING = r'#BINDING-(\S+)-START(?:.|\n)*?#BINDING-\1-END'
REP_ROOT = r'DocumentRoot\s+"?([^"\n]+)"?'


def phpConfDir():
    return mit.getServerDir() + '/web_conf/php/apache'


def tplPath(name):
    return mit.getRunDir() + '/data/tpl/' + name


# ------------------------------ conf string helpers ------------------------------

def mapSiteBlocks(conf, fn):
    '''apply fn(block) to every <VirtualHost> block that is not a dir binding'''
    skip = [m.span() for m in re.finditer(REP_BINDING, conf)]

    out = ''
    last = 0
    for m in re.finditer(REP_BLOCK, conf):
        start, end = m.span()
        in_binding = False
        for s in skip:
            if s[0] <= start < s[1]:
                in_binding = True
                break
        out += conf[last:start]
        if in_binding:
            out += m.group()
        else:
            out += fn(m.group())
        last = end
    out += conf[last:]
    return out


def mainBlock(conf):
    m = re.search(REP_BLOCK, conf)
    if m:
        return m.group()
    return ''


def getRoot(conf):
    m = re.search(REP_ROOT, conf)
    if m:
        return m.groups()[0].strip()
    return ''


def blockPorts(block):
    head = re.search(r'<VirtualHost\s+([^>]+)>', block)
    if not head:
        return []
    return [a.split(':')[-1] for a in head.groups()[0].split()]


def setBlockPorts(block, ports):
    addrs = ' '.join(['*:' + p for p in ports])
    return re.sub(r'<VirtualHost\s+[^>]+>', '<VirtualHost ' + addrs + '>', block, 1)


def isSslBlock(block):
    return block.find('SSLEngine') != -1


def insertBeforePhp(block, text):
    # AUTH / SECURITY / LIMIT sections are placed right before the PHP handler
    return block.replace('    #PHP-INFO-START', text + '\n    #PHP-INFO-START', 1)


def hasSsl(conf):
    return conf.find('SSLCertificateFile') != -1


def sslBlockText(block, certPath, keyPath):
    ssl = '''<VirtualHost *:443>
    #SSL-START
    SSLEngine On
    SSLCertificateFile "%s"
    SSLCertificateKeyFile "%s"
    SSLProtocol All -SSLv2 -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:!aNULL:!MD5:!RC4
    SSLHonorCipherOrder On
    <IfModule http2_module>
        Protocols h2 http/1.1
    </IfModule>
    #SSL-END''' % (certPath, keyPath)
    block = re.sub(r'<VirtualHost\s+[^>]+>', ssl, block, 1)
    # the https block must never redirect to itself
    block = re.sub(r'#HTTP_TO_HTTPS_START(?:.|\n)*?#HTTP_TO_HTTPS_END',
                   '#HTTP_TO_HTTPS_START\n    #HTTP_TO_HTTPS_END', block)
    return block


def addSsl(conf, certPath, keyPath):
    if hasSsl(conf):
        return conf
    block = mainBlock(conf)
    if block == '':
        return conf
    ssl = sslBlockText(block, certPath, keyPath)
    return conf.replace(block, block + '\n#SSL-VHOST-START\n' + ssl + '\n#SSL-VHOST-END', 1)


def removeSsl(conf):
    conf = re.sub(r'\n*#SSL-VHOST-START(?:.|\n)*?#SSL-VHOST-END', '', conf)
    return setHttpsRedirect(conf, False)


HTTPS_REDIRECT = '''#HTTP_TO_HTTPS_START
    <IfModule mod_rewrite.c>
        RewriteEngine on
        RewriteCond %{SERVER_PORT} !^443$
        RewriteRule (.*) https://%{SERVER_NAME}$1 [L,R=301]
    </IfModule>
    #HTTP_TO_HTTPS_END'''


def setHttpsRedirect(conf, enable):
    def fn(block):
        if isSslBlock(block):
            return block
        if enable:
            return re.sub(r'#HTTP_TO_HTTPS_START(?:.|\n)*?#HTTP_TO_HTTPS_END', HTTPS_REDIRECT, block)
        return re.sub(r'#HTTP_TO_HTTPS_START(?:.|\n)*?#HTTP_TO_HTTPS_END',
                      '#HTTP_TO_HTTPS_START\n    #HTTP_TO_HTTPS_END', block)
    return mapSiteBlocks(conf, fn)


def isHttpsRedirect(conf):
    return conf.find('RewriteCond %{SERVER_PORT} !^443$') != -1


def makeVhost(siteName, sitePath, ports, phpVersion, aliases=None, logsPath=None):
    content = mit.readFile(tplPath('apache.conf'))
    if aliases is None:
        aliases = [siteName]
    if logsPath is None:
        logsPath = mit.getLogsDir()
    content = content.replace('{$ADDRS}', ' '.join(['*:' + p for p in ports]))
    content = content.replace('{$SERVER_NAME}', siteName)
    content = content.replace('{$SERVER_ALIAS}', ' '.join(aliases))
    content = content.replace('{$ROOT_DIR}', sitePath)
    content = content.replace('{$PHP_DIR}', phpConfDir())
    content = content.replace('{$PHPVER}', phpVersion)
    content = content.replace('{$LOGPATH}', logsPath)
    return content


def makeDirBind(domain, port, webdir, siteName, phpVersion):
    content = mit.readFile(tplPath('apache_dirbind.conf'))
    content = content.replace('{$PORT}', port)
    content = content.replace('{$PHPVER}', phpVersion)
    content = content.replace('{$DIRBIND}', domain)
    content = content.replace('{$ROOT_DIR}', webdir)
    content = content.replace('{$SERVER_MAIN}', siteName)
    content = content.replace('{$PHP_DIR}', phpConfDir())
    content = content.replace('{$LOGPATH}', mit.getLogsDir())
    return content


def makeEnablePhpConf():
    '''enable-php-XX.conf for Apache: hand .php to the PHP-FPM socket of that version'''
    conf_dir = phpConfDir()
    if not os.path.exists(conf_dir):
        mit.execShell('mkdir -p ' + conf_dir)

    versions = ['00', '52', '53', '54', '55', '56', '70', '71', '72',
                '73', '74', '80', '81', '82', '83', '84', '85']
    # custom versions added under web_conf/php/conf (e.g. enable-php-81-custom.conf)
    nginx_conf_dir = mit.getServerDir() + '/web_conf/php/conf'
    if os.path.exists(nginx_conf_dir):
        for name in os.listdir(nginx_conf_dir):
            m = re.match(r'enable-php-(.+)\.conf$', name)
            if m and not m.groups()[0] in versions:
                versions.append(m.groups()[0])

    for v in versions:
        dfile = conf_dir + '/enable-php-' + v + '.conf'
        if os.path.exists(dfile):
            continue
        if v == '00':
            content = '# Pure static, PHP disabled\n'
        else:
            content = '''<FilesMatch \\.php$>
    SetHandler "proxy:unix:/tmp/php-cgi-''' + v + '''.sock|fcgi://localhost"
</FilesMatch>
'''
        mit.writeFile(dfile, content)


def makeDefaultVhost(root, phpVersion='00'):
    content = '''# Default site: answers requests whose Host matches no other site
<VirtualHost *:80>
    ServerName default.localhost
    DocumentRoot "%s"
    IncludeOptional %s/enable-php-%s.conf
    <Directory "%s">
        Options FollowSymLinks
        AllowOverride All
        Require all granted
        DirectoryIndex index.php index.html index.htm default.php default.htm default.html
    </Directory>
</VirtualHost>
''' % (root, phpConfDir(), phpVersion, root)
    vhost_dir = mit.getServerDir() + '/web_conf/apache/vhost'
    if not os.path.exists(vhost_dir):
        mit.execShell('mkdir -p ' + vhost_dir)
    mit.writeFile(vhost_dir + '/0.default.conf', content)


class site_apache:

    def __init__(self, site):
        # site: the calling site_api instance (paths, db helpers)
        self.site = site

    def conf(self, siteName):
        return mit.readFile(self.site.getHostConf(siteName))

    def save(self, siteName, conf):
        mit.writeFile(self.site.getHostConf(siteName), conf)

    # ------------------------------ create / domains ------------------------------
    def addConf(self, siteName, sitePath, port, phpVersion):
        content = makeVhost(siteName, sitePath, [port], phpVersion)
        self.save(siteName, content)

    def addDomain(self, siteName, domain, port):
        conf = self.conf(siteName)
        if not conf:
            return

        def fn(block):
            m = re.search(r'ServerAlias\s+(.+)', block)
            if m:
                names = m.groups()[0].split()
                if not domain in names:
                    block = block.replace(m.group(), m.group() + ' ' + domain, 1)
            else:
                block = re.sub(r'(ServerName\s+.+)', r'\1\n    ServerAlias ' + domain, block, 1)
            if not isSslBlock(block):
                ports = blockPorts(block)
                if not port in ports:
                    block = setBlockPorts(block, ports + [port])
            return block

        self.save(siteName, mapSiteBlocks(conf, fn))

    def delDomain(self, siteName, domain, port, port_count):
        conf = self.conf(siteName)
        if not conf:
            return

        def fn(block):
            m = re.search(r'ServerAlias\s+(.+)', block)
            names = []
            if m:
                names = [n for n in m.groups()[0].split() if n != domain]
                block = block.replace(m.group(), 'ServerAlias ' + ' '.join(names), 1)
            sn = re.search(r'ServerName\s+(\S+)', block)
            if sn and sn.groups()[0] == domain and len(names) > 0:
                block = block.replace(sn.group(), 'ServerName ' + names[0], 1)
            if not isSslBlock(block) and port_count < 2:
                ports = blockPorts(block)
                if port in ports and len(ports) > 1:
                    ports.remove(port)
                    block = setBlockPorts(block, ports)
            return block

        self.save(siteName, mapSiteBlocks(conf, fn))

    def setDefaultSite(self, name):
        if name == '':
            makeDefaultVhost(mit.getServerDir() + '/apache/htdocs')
            return
        sid = mit.M('sites').where('name=?', (name,)).getField('id')
        conf = self.conf(name)
        root = getRoot(conf) if conf else ''
        if root == '':
            root = mit.M('sites').where('id=?', (sid,)).getField('path')
        ver = '00'
        if conf:
            m = re.search(r'enable-php-(.*?)\.conf', conf)
            if m:
                ver = m.groups()[0]
        makeDefaultVhost(root, ver)

    # ------------------------------ root / run path ------------------------------
    def getSitePath(self, siteName):
        conf = self.conf(siteName)
        if conf:
            return getRoot(conf)
        return ''

    def setRunPath(self, siteName, newPath):
        conf = self.conf(siteName)
        if not conf:
            return
        old = getRoot(conf)

        def fn(block):
            block = block.replace('DocumentRoot "' + old + '"', 'DocumentRoot "' + newPath + '"')
            block = block.replace('<Directory "' + old + '">', '<Directory "' + newPath + '">')
            return block

        self.save(siteName, mapSiteBlocks(conf, fn))

    def setRootForAcme(self, conf, root):
        # point every block (bindings too) at the main root while the ACME
        # http-01 challenge runs, same as the nginx variant
        return re.sub(REP_ROOT, 'DocumentRoot "' + root + '"', conf)

    # ------------------------------ logs ------------------------------
    def toggleLogs(self, siteName):
        conf = self.conf(siteName)
        if not conf:
            return
        if re.search(r'^\s*#CustomLog', conf, re.M):
            conf = re.sub(r'^(\s*)#CustomLog', r'\1CustomLog', conf, flags=re.M)
        else:
            conf = re.sub(r'^(\s*)CustomLog', r'\1#CustomLog', conf, flags=re.M)
        self.save(siteName, conf)

    def logsStatus(self, conf):
        if re.search(r'^\s*#CustomLog', conf, re.M):
            return False
        return True

    # ------------------------------ ssl ------------------------------
    def setSslConf(self, siteName, certPath, keyPath):
        conf = self.conf(siteName)
        if not conf:
            return
        self.save(siteName, addSsl(conf, certPath, keyPath))

    def closeSsl(self, siteName):
        conf = self.conf(siteName)
        if not conf:
            return
        self.save(siteName, removeSsl(conf))

    def httpToHttps(self, siteName):
        conf = self.conf(siteName)
        if not conf:
            return True
        if not hasSsl(conf):
            return False
        self.save(siteName, setHttpsRedirect(conf, True))
        return True

    def closeToHttps(self, siteName):
        conf = self.conf(siteName)
        if not conf:
            return
        self.save(siteName, setHttpsRedirect(conf, False))

    # ------------------------------ index ------------------------------
    def getIndex(self, siteName):
        conf = self.conf(siteName)
        m = re.search(r'DirectoryIndex\s+(.+)', conf)
        if m:
            return m.groups()[0].strip().replace(' ', ',')
        return ''

    def setIndex(self, siteName, index_l):
        conf = self.conf(siteName)
        if not conf:
            return

        def fn(block):
            return re.sub(r'DirectoryIndex\s+.+', 'DirectoryIndex ' + index_l, block)

        self.save(siteName, mapSiteBlocks(conf, fn))

    # ------------------------------ traffic limit ------------------------------
    # Apache has no per-server / per-ip connection limit like nginx limit_conn;
    # the rate is enforced by mod_ratelimit, the connection numbers are kept
    # in the marker so the panel form shows what was saved.
    def getLimitNet(self, siteName):
        conf = self.conf(siteName)
        data = {'perserver': 0, 'perip': 0, 'limit_rate': 0}
        m = re.search(r'#LIMIT-START perserver=(\d+) perip=(\d+) rate=(\d+)', conf)
        if m:
            data['perserver'] = int(m.groups()[0])
            data['perip'] = int(m.groups()[1])
            data['limit_rate'] = int(m.groups()[2])
        return data

    def saveLimitNet(self, siteName, perserver, perip, limit_rate):
        conf = self.conf(siteName)
        if not conf:
            return
        text = '''    #LIMIT-START perserver=%s perip=%s rate=%s
    <IfModule ratelimit_module>
        <Location "/">
            SetOutputFilter RATE_LIMIT
            SetEnv rate-limit %s
        </Location>
    </IfModule>
    #LIMIT-END''' % (perserver, perip, limit_rate, limit_rate)
        conf = re.sub(r'\n[ \t]*#LIMIT-START(?:.|\n)*?#LIMIT-END', '', conf)
        self.save(siteName, mapSiteBlocks(conf, lambda b: insertBeforePhp(b, text)))

    def closeLimitNet(self, siteName):
        conf = self.conf(siteName)
        if not conf:
            return
        conf = re.sub(r'\n[ \t]*#LIMIT-START(?:.|\n)*?#LIMIT-END', '', conf)
        self.save(siteName, conf)

    # ------------------------------ anti-leech ------------------------------
    def getSecurity(self, siteName):
        conf = self.conf(siteName)
        m = re.search(r'#SECURITY-START fix=(\S*) domains=(\S*)', conf)
        if not m:
            return None
        return {'fix': m.groups()[0], 'domains': m.groups()[1], 'status': True}

    def setSecurity(self, siteName, fix, domains, enable):
        conf = self.conf(siteName)
        if not conf:
            return
        conf = re.sub(r'\n[ \t]*#SECURITY-START(?:.|\n)*?#SECURITY-END', '', conf)
        if enable:
            fix = fix.strip().replace(' ', '')
            domains = domains.strip().replace(' ', '')
            refs = []
            for d in domains.split(','):
                if d == '':
                    continue
                refs.append(re.escape(d).replace('\\*', '[^/]*'))
            text = '''    #SECURITY-START fix=%s domains=%s
    <IfModule mod_rewrite.c>
        RewriteEngine on
        RewriteCond %%{HTTP_REFERER} !^$
        RewriteCond %%{HTTP_REFERER} !^https?://(%s)(:\\d+)?(/.*)?$ [NC]
        RewriteRule \\.(%s)$ - [R=404,NC,L]
    </IfModule>
    #SECURITY-END''' % (fix, domains, '|'.join(refs), fix.replace(',', '|'))
            conf = mapSiteBlocks(conf, lambda b: insertBeforePhp(b, text))
        self.save(siteName, conf)

    # ------------------------------ password ------------------------------
    def setHasPwd(self, configFile, passFile):
        conf = mit.readFile(configFile)
        if not conf:
            return
        conf = re.sub(r'\n[ \t]*#AUTH_START(?:.|\n)*?#AUTH_END', '', conf)
        text = '''    #AUTH_START
    <Location "/">
        AuthType Basic
        AuthName "Authorization"
        AuthUserFile "%s"
        Require valid-user
    </Location>
    #AUTH_END''' % (passFile,)
        conf = mapSiteBlocks(conf, lambda b: insertBeforePhp(b, text))
        mit.writeFile(configFile, conf)

    def closeHasPwd(self, configFile):
        conf = mit.readFile(configFile)
        if not conf:
            return
        conf = re.sub(r'\n[ \t]*#AUTH_START(?:.|\n)*?#AUTH_END', '', conf)
        mit.writeFile(configFile, conf)

    # ------------------------------ dir binding ------------------------------
    def addDirBind(self, siteName, domain, port, webdir):
        conf = self.conf(siteName)
        m = re.search(r'enable-php-(.*?)\.conf', conf)
        version = m.groups()[0] if m else '00'
        conf += "\n" + makeDirBind(domain, port, webdir, siteName, version)
        self.save(siteName, conf)

    def dirBindRewrite(self, sitePath, dirName, add):
        filename = sitePath + '/' + dirName + '/.htaccess'
        if add == '1' and not os.path.exists(filename):
            mit.writeFile(filename, '')
            mit.setOwn(filename, 'www')
        rewrite_dir = mit.getRunDir() + '/rewrite/apache'
        data = {}
        data['rewrite_dir'] = rewrite_dir
        data['status'] = False
        if os.path.exists(filename):
            data['status'] = True
            data['data'] = mit.readFile(filename)
            data['rlist'] = []
            for ds in sorted(os.listdir(rewrite_dir)):
                if ds[0:1] == '.' or not ds.endswith('.conf'):
                    continue
                data['rlist'].append(ds[0:len(ds) - 5])
            data['filename'] = filename
        return data

    # ------------------------------ rewrite (.htaccess) ------------------------------
    def getRewriteConf(self, siteName):
        root = self.getSitePath(siteName)
        if root == '':
            root = mit.M('sites').where('name=?', (siteName,)).getField('path')
        filename = root + '/.htaccess'
        if not os.path.exists(filename) and os.path.isdir(root):
            mit.writeFile(filename, '')
            mit.setOwn(filename, 'www')
        return filename

    # ------------------------------ redirect / proxy ------------------------------
    def includeConf(self, siteName, marker, path, method):
        '''marker: 301 or PROXY; turns the IncludeOptional of that dir on/off'''
        vhost_file = self.site.getHostConf(siteName)
        content = mit.readFile(vhost_file)
        if not content:
            return
        start = '#' + marker + '-START'
        end = '#' + marker + '-END'
        include = start + '\n    IncludeOptional ' + path + '/*.conf\n    ' + end
        if content.find(end) != -1:
            if method == 'stop':
                content = re.sub(start + r'(?:\n|.)*?' + end, start, content)
            elif content.find('IncludeOptional ' + path + '/') == -1:
                # section was blanked out (site stopped); put the include back
                content = re.sub(start + r'(?:\n|.)*?' + end, include, content)
        elif method == 'start':
            content = content.replace(start, include)
        mit.writeFile(vhost_file, content)

    def redirectContent(self, _from, _to, rtype, dtype, keep):
        '''rtype 0=301 1=302, dtype 0=path 1=domain, keep 1=keep uri'''
        code = '301' if rtype == 0 else '302'
        if dtype == 0:
            if not _from.startswith('/'):
                _from = '/' + _from
            if keep == 1:
                return 'RewriteEngine on\nRewriteRule ^%s(.*)$ %s$1 [R=%s,L]' % (re.escape(_from), _to, code)
            return 'RewriteEngine on\nRewriteRule ^%s %s [R=%s,L]' % (re.escape(_from), _to, code)

        host = re.escape(_from)
        if keep == 1:
            rule = 'RewriteRule ^(.*)$ %s$1 [R=%s,L]' % (_to.rstrip('/'), code)
        else:
            rule = 'RewriteRule ^ %s [R=%s,L]' % (_to, code)
        return 'RewriteEngine on\nRewriteCond %%{HTTP_HOST} ^%s$ [NC]\n%s' % (host, rule)

    def proxyContent(self, _from, _to, _host):
        to = urlparse(_to)
        target = _to
        # nginx "proxy_pass http://x" (no URI) forwards the full path
        if to.path in ('', '/'):
            target = to.scheme + '://' + to.netloc + _from
        ssl_proxy = ''
        if to.scheme == 'https':
            ssl_proxy = '\n    SSLProxyEngine on\n    SSLProxyVerify none\n    SSLProxyCheckPeerName off'
        return '''#PROXY-START%s
<IfModule proxy_module>%s
    <Location "%s">
        ProxyPreserveHost On
        RequestHeader set Host "%s"
        RequestHeader set X-Forwarded-Proto "expr=%%{REQUEST_SCHEME}"
        ProxyPass "%s" upgrade=websocket
        ProxyPassReverse "%s"
    </Location>
</IfModule>
#PROXY-END%s''' % (_from, ssl_proxy, _from, _host, target, target, _from)

    # ------------------------------ migrate from nginx ------------------------------
    def rebuildFromDb(self):
        '''create an Apache vhost for every site that does not have one yet,
        using the database plus whatever the old nginx vhost tells us'''
        made = []
        nginx_vhost = mit.getServerDir() + '/web_conf/nginx/vhost'
        sites = mit.M('sites').field('id,name,path,status').select()
        if type(sites) != list:
            return made

        for s in sites:
            name = s['name']
            vfile = self.site.getHostConf(name)
            if os.path.exists(vfile):
                continue

            nconf = mit.readFile(nginx_vhost + '/' + name + '.conf') or ''
            ver = '00'
            m = re.search(r'enable-php-(.*?)\.conf', nconf)
            if m:
                ver = m.groups()[0]
            root = s['path']
            m = re.search(r'\s*root\s*(.+);', nconf)
            if m and m.groups()[0].strip().startswith(s['path']):
                root = m.groups()[0].strip()

            ports = []
            aliases = []
            domains = mit.M('domain').where('pid=?', (s['id'],)).field('name,port').select()
            for d in domains:
                if not str(d['port']) in ports:
                    ports.append(str(d['port']))
                if not d['name'] in aliases:
                    aliases.append(d['name'])
            if len(ports) == 0:
                ports = ['80']
            if len(aliases) == 0:
                aliases = [name]

            conf = makeVhost(name, root, ports, ver, aliases)

            if nconf.find('ssl_certificate') != -1:
                cert = self.site.sslDir + '/' + name + '/fullchain.pem'
                key = self.site.sslDir + '/' + name + '/privkey.pem'
                if os.path.exists(cert) and os.path.exists(key):
                    conf = addSsl(conf, cert, key)
                    if nconf.find('$server_port !~ 443') != -1:
                        conf = setHttpsRedirect(conf, True)

            bindings = mit.M('binding').where('pid=?', (s['id'],)).field(
                'domain,port,path').select()
            for b in bindings:
                conf += "\n" + makeDirBind(b['domain'], str(b['port']),
                                           s['path'] + '/' + b['path'], name, ver)

            if str(s['status']) == '0':
                conf = conf.replace(s['path'], self.site.setupPath + '/stop')

            mit.writeFile(vfile, conf)
            made.append(name)
        return made
