#!/usr/bin/python3
# coding:utf-8

# Background job of the Clone Server plugin: copies this server to a target
# server over SSH. Started by index.py, which passes the job file path as the
# first argument and the SSH password (if any) in the SSHPASS environment
# variable, so the password is never written to disk.
#
# Steps
#   1. connect, make sure rsync exists on the target
#   2. copy the panel code, install the panel on the target if it is missing
#   3. install the same software versions that run here (web server, PHP,
#      MySQL / MariaDB, phpMyAdmin) when missing on the target
#   4. copy website files, web_conf (vhost, SSL, rewrite, proxy, redirect),
#      acme.sh certificates and the site list of the panel
#   5. copy databases (mysqldump streamed over SSH), their users and grants,
#      and the database list of the panel; the target root password is kept
#   6. restart services on the target

import os
import sys
import json
import time
import shlex
import sqlite3
import subprocess

PANEL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PANEL + '/class/core')
import mit

SERVER = mit.getServerDir()
ROOT = mit.getRootDir()
WORK = SERVER + '/clone'
LOG = WORK + '/clone.log'
STATUS = WORK + '/status.json'

SYSTEM_DBS = ('information_schema', 'performance_schema', 'mysql', 'sys')
SYSTEM_USERS = ('root', 'mysql.sys', 'mysql.session', 'mysql.infoschema', 'mariadb.sys', 'debian-sys-maint', '')
# panel tables that describe websites (users / tokens of the target panel are kept)
SITE_TABLES = ('sites', 'domain', 'binding', 'site_types')


class CloneError(Exception):
    pass


# ------------------------------ logging / status ------------------------------

def log(msg):
    line = time.strftime('%H:%M:%S') + ' ' + msg
    print(line)
    with open(LOG, 'a') as f:
        f.write(line + '\n')


def setStatus(state, step, percent):
    data = {'state': state, 'step': step, 'percent': percent, 'pid': os.getpid(), 'time': int(time.time())}
    with open(STATUS, 'w') as f:
        f.write(json.dumps(data))


# ------------------------------ ssh helpers ------------------------------

class Remote:

    def __init__(self, job):
        self.host = job['host']
        self.port = str(job.get('port', '22'))
        self.user = job.get('user', 'root')
        self.key = job.get('key', '')
        self.use_pass = os.environ.get('SSHPASS', '') != ''

    def sshOpts(self):
        opts = ['-p', self.port, '-o', 'StrictHostKeyChecking=accept-new',
                '-o', 'ServerAliveInterval=30', '-o', 'ConnectTimeout=15']
        if self.key:
            opts += ['-i', self.key]
        if not self.use_pass:
            opts += ['-o', 'BatchMode=yes']
        return opts

    def wrap(self, cmd):
        return (['sshpass', '-e'] + cmd) if self.use_pass else cmd

    def target(self):
        return self.user + '@' + self.host

    def run(self, command, check=True, stdin=None, data=None, timeout=None):
        cmd = self.wrap(['ssh'] + self.sshOpts() + [self.target(), command])
        if data is not None:
            p = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        else:
            p = subprocess.run(cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out = p.stdout.decode('utf-8', 'ignore')
        err = p.stderr.decode('utf-8', 'ignore')
        if check and p.returncode != 0:
            raise CloneError('Perintah di server tujuan gagal: %s\n%s' % (command[:200], err.strip()[-800:]))
        return p.returncode, out, err

    def exists(self, path):
        return self.run('test -e ' + shlex.quote(path), check=False)[0] == 0

    def rsync(self, src, dst, extra=None):
        ssh = 'ssh ' + ' '.join([shlex.quote(o) for o in self.sshOpts()])
        cmd = self.wrap(['rsync', '-aHAX', '--numeric-ids', '--info=stats1', '-e', ssh] + (extra or []) +
                        [src, self.target() + ':' + dst])
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode not in (0, 24):  # 24: some files vanished during transfer
            raise CloneError('rsync %s gagal: %s' % (src, p.stderr.decode('utf-8', 'ignore').strip()[-800:]))


def local(cmd):
    p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode('utf-8', 'ignore'), p.stderr.decode('utf-8', 'ignore')


# ------------------------------ what runs here ------------------------------

def readVersion(name):
    v = mit.readFile(SERVER + '/' + name + '/version.pl')
    return v.strip() if v else ''


def installedSoftware():
    '''[(plugin, version)] of the software this server runs'''
    items = []
    for name in ('apache', 'openresty', 'mysql', 'mariadb'):
        v = readVersion(name)
        if v:
            items.append((name, v))
    php_dir = SERVER + '/php'
    if os.path.exists(php_dir):
        for v in sorted(os.listdir(php_dir)):
            if v.isdigit() and os.path.exists(php_dir + '/' + v + '/bin/php'):
                items.append(('php', v))
    v = readVersion('phpmyadmin')
    if v:
        items.append(('phpmyadmin', v))
    return items


def remoteHasSoftware(rm, name, version):
    if name == 'php':
        return rm.exists(SERVER + '/php/' + version + '/bin/php')
    code, out, err = rm.run('cat ' + shlex.quote(SERVER + '/' + name + '/version.pl'), check=False)
    return code == 0 and out.strip() == version


# ------------------------------ steps ------------------------------

def stepConnect(rm):
    log('Menghubungi %s:%s sebagai %s ...' % (rm.host, rm.port, rm.user))
    if rm.use_pass and local('command -v sshpass')[0] != 0:
        raise CloneError('sshpass belum terpasang di server ini. Pasang ulang plugin Clone Server atau pakai SSH key.')
    code, out, err = rm.run('uname -a; id -u', check=False)
    if code != 0:
        raise CloneError('SSH gagal: ' + err.strip()[-500:])
    lines = out.strip().split('\n')
    log('Terhubung: ' + lines[0])
    if lines[-1].strip() != '0':
        raise CloneError('User SSH harus root (atau punya uid 0) di server tujuan.')
    if rm.run('command -v rsync', check=False)[0] != 0:
        log('Memasang rsync di server tujuan...')
        rm.run('(command -v apt-get >/dev/null && apt-get install -y rsync) || '
               '(command -v dnf >/dev/null && dnf install -y rsync) || '
               '(command -v yum >/dev/null && yum install -y rsync) || '
               '(command -v pacman >/dev/null && pacman -Sy --noconfirm rsync) || '
               '(command -v zypper >/dev/null && zypper install -y rsync)')


def stepPanel(rm):
    has_panel = rm.exists(PANEL + '/app.py')
    log('Menyalin kode panel ke server tujuan...')
    rm.run('mkdir -p ' + shlex.quote(PANEL))
    rm.rsync(PANEL + '/', PANEL + '/', ['--exclude', 'data/', '--exclude', 'logs/', '--exclude', 'tmp/',
                                        '--exclude', 'ssl/', '--exclude', '__pycache__/', '--exclude', '*.pyc'])
    if not has_panel:
        log('MIT Panel belum ada di tujuan, menjalankan instalasi (beberapa menit)...')
        rm.run('bash ' + shlex.quote(PANEL + '/scripts/install.sh') + ' > /tmp/mit-clone-install.log 2>&1')
        log('MIT Panel terpasang di server tujuan.')
    else:
        log('MIT Panel sudah ada di tujuan, kode panel diperbarui.')


def stepSoftware(rm, job):
    items = installedSoftware()
    log('Software di server ini: ' + ', '.join(['%s %s' % i for i in items]))

    # only one web server may run on the target
    web = [i for i in items if i[0] in ('apache', 'openresty')]
    if web:
        other = 'openresty' if web[0][0] == 'apache' else 'apache'
        if rm.exists(SERVER + '/' + other):
            raise CloneError('Server tujuan memakai %s, server ini memakai %s. Hapus %s di tujuan dulu.' % (
                other, web[0][0], other))

    missing = [i for i in items if not remoteHasSoftware(rm, i[0], i[1])]
    if not missing:
        log('Semua software sudah terpasang di tujuan.')
        return
    if not job.get('install_soft', True):
        raise CloneError('Software belum ada di tujuan: ' + ', '.join(['%s %s' % i for i in missing]) +
                         '. Aktifkan opsi "Pasang software yang belum ada".')

    # web server and database before PHP / phpMyAdmin
    order = {'openresty': 0, 'apache': 0, 'mysql': 1, 'mariadb': 1, 'php': 2, 'phpmyadmin': 3}
    missing.sort(key=lambda i: order.get(i[0], 9))
    for name, version in missing:
        log('Memasang %s %s di tujuan (kompilasi bisa 10-60 menit)...' % (name, version))
        plugin = shlex.quote(PANEL + '/plugins/' + name)
        rm.run('cd %s && bash install.sh install %s > /tmp/mit-clone-%s.log 2>&1' % (plugin, shlex.quote(version), name))
        rm.run('cd %s && python3 plugins/%s/index.py start %s; python3 plugins/%s/index.py initd_install %s' % (
            shlex.quote(PANEL), name, shlex.quote(version), name, shlex.quote(version)), check=False)
        if not remoteHasSoftware(rm, name, version):
            raise CloneError('Instalasi %s %s di tujuan gagal, lihat /tmp/mit-clone-%s.log di server tujuan.' % (name, version, name))
        log('%s %s terpasang.' % (name, version))


def sitePaths():
    db = sqlite3.connect(PANEL + '/data/default.db')
    try:
        rows = db.execute('select name, path from sites').fetchall()
    finally:
        db.close()
    return rows


def stepSites(rm):
    rows = sitePaths()
    log('Menyalin %d situs...' % len(rows))
    copied = []
    www = mit.getWwwDir()
    if os.path.exists(www):
        rm.run('mkdir -p ' + shlex.quote(www))
        rm.rsync(www + '/', www + '/')
        copied.append(www)
    for name, path in rows:
        if not path or not os.path.exists(path) or path.startswith(www + '/') or path in copied:
            continue
        rm.run('mkdir -p ' + shlex.quote(path))
        rm.rsync(path.rstrip('/') + '/', path.rstrip('/') + '/')
        copied.append(path)
        log('  situs %s -> %s' % (name, path))

    log('Menyalin konfigurasi web (vhost, SSL, rewrite, proxy, redirect)...')
    rm.rsync(SERVER + '/web_conf/', SERVER + '/web_conf/')
    if os.path.exists('/root/.acme.sh'):
        log('Menyalin sertifikat acme.sh...')
        rm.rsync('/root/.acme.sh/', '/root/.acme.sh/')
    for f in ('default_site.pl', 'site.pl'):
        if os.path.exists(PANEL + '/data/' + f):
            rm.rsync(PANEL + '/data/' + f, PANEL + '/data/' + f)

    # site list of the panel: copy the website tables into the target panel db
    tmp = '/tmp/mit-clone-default.db'
    rm.rsync(PANEL + '/data/default.db', tmp)
    rm.run(pyMergeTables(PANEL + '/data/default.db', tmp, SITE_TABLES))
    rm.run('rm -f ' + tmp)
    log('Daftar situs panel disalin.')


def pyMergeTables(dst_db, src_db, tables):
    '''remote command: replace the rows of the given tables in dst_db with those of src_db'''
    code = (
        "import sqlite3\n"
        "d=sqlite3.connect(%r)\n"
        "d.execute('attach database ? as s', (%r,))\n"
        "for t in %r:\n"
        "    if not d.execute(\"select name from s.sqlite_master where type='table' and name=?\", (t,)).fetchone(): continue\n"
        "    if not d.execute(\"select name from sqlite_master where type='table' and name=?\", (t,)).fetchone():\n"
        "        sql=d.execute(\"select sql from s.sqlite_master where name=?\", (t,)).fetchone()[0]\n"
        "        d.execute(sql)\n"
        "    d.execute('delete from main.'+t)\n"
        "    d.execute('insert into main.'+t+' select * from s.'+t)\n"
        "d.commit()\n"
    ) % (dst_db, src_db, tuple(tables))
    return 'python3 -c ' + shlex.quote(code)


# ------------------------------ databases ------------------------------

def dbEngine():
    for name in ('mysql', 'mariadb'):
        if os.path.exists(SERVER + '/' + name + '/etc/my.cnf'):
            return name
    return ''


def confValue(content, key):
    import re
    m = re.search(r'(?m)^\s*' + key + r'\s*=\s*(.+)$', content or '')
    return m.groups()[0].strip() if m else ''


def rootPwd(sqlite_file):
    db = sqlite3.connect(sqlite_file)
    try:
        return db.execute('select mysql_root from config where id=1').fetchone()[0]
    finally:
        db.close()


def binPath(engine, names):
    for n in names:
        p = SERVER + '/' + engine + '/bin/' + n
        if os.path.exists(p):
            return p
    return SERVER + '/' + engine + '/bin/' + names[-1]


def stepDatabases(rm):
    engine = dbEngine()
    if engine == '':
        log('Tidak ada MySQL/MariaDB di server ini, database dilewati.')
        return

    my_cnf = mit.readFile(SERVER + '/' + engine + '/etc/my.cnf')
    socket = confValue(my_cnf, 'socket')
    src_pwd = rootPwd(SERVER + '/' + engine + '/mysql.db')

    # client credentials in a private file instead of the command line
    cred = WORK + '/client.cnf'
    with open(cred, 'w') as f:
        f.write('[client]\nuser=root\npassword="%s"\nsocket=%s\n' % (src_pwd.replace('"', '\\"'), socket))
    os.chmod(cred, 0o600)

    mysql_bin = binPath(engine, ['mariadb', 'mysql'])
    dump_bin = binPath(engine, ['mariadb-dump', 'mysqldump'])
    base = '%s --defaults-extra-file=%s' % (mysql_bin, cred)

    try:
        code, out, err = local(base + ' -N -e "show databases"')
        if code != 0:
            raise CloneError('Tidak bisa login ke %s lokal: %s' % (engine, err.strip()))
        dbs = [d for d in out.split() if d not in SYSTEM_DBS]

        # target credentials: read on the target, used only there
        remote_sqlite = SERVER + '/' + engine + '/mysql.db'
        code, out, err = rm.run('python3 -c ' + shlex.quote(
            "import sqlite3;print(sqlite3.connect(%r).execute('select mysql_root from config where id=1').fetchone()[0])" % remote_sqlite))
        dst_pwd = out.strip()
        code, out, err = rm.run('cat ' + shlex.quote(SERVER + '/' + engine + '/etc/my.cnf'))
        dst_socket = confValue(out, 'socket')
        rcred = '/tmp/mit-clone-client.cnf'
        rm.run('umask 077; cat > ' + rcred, data=('[client]\nuser=root\npassword="%s"\nsocket=%s\n' % (
            dst_pwd.replace('"', '\\"'), dst_socket)).encode('utf-8'))
        rmysql = '%s --defaults-extra-file=%s' % (binPath(engine, ['mariadb', 'mysql']), rcred)

        log('Menyalin %d database: %s' % (len(dbs), ', '.join(dbs)))
        for i, db in enumerate(dbs):
            log('  [%d/%d] %s ...' % (i + 1, len(dbs), db))
            dump = subprocess.Popen(
                '%s --defaults-extra-file=%s --single-transaction --quick --routines --triggers --events '
                '--hex-blob --databases %s | gzip -1' % (dump_bin, cred, shlex.quote(db)),
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            rm.run('gunzip | ' + rmysql, stdin=dump.stdout)
            dump.wait()
            if dump.returncode != 0:
                raise CloneError('mysqldump %s gagal: %s' % (db, dump.stderr.read().decode('utf-8', 'ignore')[-500:]))

        log('Menyalin user database dan hak aksesnya...')
        sql = userGrantsSql(base)
        if sql:
            rm.run(rmysql, data=sql.encode('utf-8'))

        # database list of the panel (names, users, passwords shown in the UI)
        tmp = '/tmp/mit-clone-mysql.db'
        rm.rsync(SERVER + '/' + engine + '/mysql.db', tmp)
        rm.run(pyMergeTables(remote_sqlite, tmp, ('databases',)))
        rm.run('rm -f ' + tmp + ' ' + rcred)
        log('Database selesai disalin.')
    finally:
        os.remove(cred)


def userGrantsSql(base):
    code, out, err = local(base + ' -N -e "select user, host from mysql.user"')
    if code != 0:
        raise CloneError('Gagal membaca user database: ' + err.strip())
    sql = ''
    for line in out.strip().split('\n'):
        if '\t' not in line:
            continue
        user, host = line.split('\t', 1)
        if user in SYSTEM_USERS:
            continue
        acct = "'%s'@'%s'" % (user.replace("'", "\\'"), host.replace("'", "\\'"))
        # MySQL 8 caching_sha2 hashes are binary: ask for them in hex when supported
        c, create, e = local(base + ' -N --raw -e ' + shlex.quote(
            'set session print_identified_with_as_hex=1; show create user ' + acct))
        if c != 0:
            c, create, e = local(base + ' -N --raw -e ' + shlex.quote('show create user ' + acct))
        c2, grants, e2 = local(base + ' -N --raw -e ' + shlex.quote('show grants for ' + acct))
        if c != 0 or c2 != 0:
            log('  lewati user %s (%s)' % (acct, (e or e2).strip()))
            continue
        sql += 'DROP USER IF EXISTS %s;\n' % acct
        sql += create.strip() + ';\n'
        for g in grants.strip().split('\n'):
            if g.strip():
                sql += g.strip() + ';\n'
    if sql:
        sql += 'FLUSH PRIVILEGES;\n'
    return sql


# ------------------------------ finish ------------------------------

def stepRestart(rm):
    log('Menyalakan ulang layanan di server tujuan...')
    items = installedSoftware()
    for name, version in items:
        if name == 'phpmyadmin':
            continue
        rm.run('cd %s && python3 plugins/%s/index.py restart %s' % (shlex.quote(PANEL), name, shlex.quote(version)), check=False)
    if mit.isApache():
        rm.run('cd %s && python3 plugins/apache/index.py reload' % shlex.quote(PANEL), check=False)
    code, out, err = rm.run('mit default 2>/dev/null || bash /etc/init.d/mit default', check=False)
    for line in out.strip().split('\n'):
        if line.strip():
            log('  ' + line.strip())


def main():
    job = json.loads(mit.readFile(sys.argv[1]))
    rm = Remote(job)
    open(LOG, 'w').close()
    steps = [('Koneksi', lambda: stepConnect(rm))]
    if job.get('panel', True):
        steps.append(('Panel', lambda: stepPanel(rm)))
    steps.append(('Software', lambda: stepSoftware(rm, job)))
    if job.get('sites', True):
        steps.append(('Situs & SSL', lambda: stepSites(rm)))
    if job.get('databases', True):
        steps.append(('Database', lambda: stepDatabases(rm)))
    steps.append(('Restart layanan', lambda: stepRestart(rm)))

    started = time.time()
    try:
        for i, (title, fn) in enumerate(steps):
            setStatus('running', title, int(100 * i / len(steps)))
            log('=== %s ===' % title)
            fn()
        setStatus('done', 'Selesai', 100)
        msg = 'Clone ke %s selesai dalam %d menit.' % (rm.host, (time.time() - started) / 60)
        log(msg)
        mit.writeLog('Clone Server', msg)
    except Exception as e:
        setStatus('failed', str(e)[:300], 0)
        log('GAGAL: ' + str(e))
        mit.writeLog('Clone Server', 'Clone ke %s gagal: %s' % (rm.host, str(e)[:200]))
    finally:
        os.remove(sys.argv[1])


if __name__ == '__main__':
    main()
