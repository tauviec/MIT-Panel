# coding:utf-8
import warnings
warnings.filterwarnings("ignore")

import sys
import io
import os
import time
import re
import json

# Suppress annoying warnings
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
except ImportError:
    pass


# print(sys.platform)
# dynamic path
panel_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(panel_path)

sys.path.append(panel_path + "/class/core")
import mit as mw

app_debug = False
if mw.isAppleSystem():
    app_debug = True


def getPluginName():
    return 'gdrive'


def getPluginDir():
    return panel_path + '/plugins/' + getPluginName()


def getServerDir():
    return os.path.dirname(panel_path) + '/' + getPluginName()


def in_array(name, arr=[]):
    for x in arr:
        if name == x:
            return True
    return False


# add class path
sys.path.append(panel_path + "/plugins/gdrive/class")
from gdriveclient import gdriveclient


gd = gdriveclient(getPluginDir(), getServerDir())
gd.setDebug(False)


def getArgs():
    # the panel passes args unquoted to the shell; the UI sends base64(JSON)
    # so values with ':' '&' or spaces (auth URL, credentials) arrive intact
    args = sys.argv[2:]
    import base64
    for a in reversed(args):
        try:
            data = json.loads(base64.b64decode(a.strip(), validate=True).decode('utf-8'))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    tmp = {}
    args_len = len(args)
    if args_len == 1:
        t = args[0].strip('{').strip('}')
        if t.strip() == '':
            tmp = []
        else:
            t = t.split(':', 1)
            tmp[t[0]] = t[1]
    elif args_len > 1:
        for i in range(len(args)):
            t = args[i].split(':', 1)
            tmp[t[0]] = t[1]
    return tmp


def checkArgs(data, ck=[]):
    for i in range(len(ck)):
        if not ck[i] in data:
            return (False, mw.returnJson(False, 'Parameter: (' + ck[i] + ') tidak ada!'))
    return (True, mw.returnJson(True, 'ok'))


def status():
    return 'start'


def start():
    return 'ok'


def stop():
    return 'ok'


def restart():
    return 'ok'


def reload():
    return 'ok'


def isAuthApi():
    cfg = getServerDir() + "/token.json"
    if os.path.exists(cfg):
        return True
    return False


def credFile():
    return getPluginDir() + '/credentials.json'


def getConf():
    if not os.path.exists(credFile()):
        return mw.returnJson(False, "Kredensial Google belum diisi", {'need_credentials': True})
    if not isAuthApi():
        sign_in_url, state = gd.get_sign_in_url()
        if not sign_in_url:
            return mw.returnJson(False, "Belum diotorisasi: " + str(state))
        return mw.returnJson(False, "Belum diotorisasi!", {'auth_url': sign_in_url})
    return mw.returnJson(True, "OK")


def setCredentials():
    """save the OAuth client JSON downloaded from Google Cloud Console"""
    args = getArgs()
    raw = args.get('json', '').strip()
    try:
        data = json.loads(raw)
    except Exception:
        return mw.returnJson(False, 'Isi bukan JSON yang valid. Tempel seluruh isi file client_secret_xxx.json.')
    client = data.get('installed') or data.get('web')
    if not client or not client.get('client_id') or not client.get('client_secret'):
        return mw.returnJson(False, 'JSON tidak berisi OAuth client (butuh "installed" atau "web" dengan client_id dan client_secret).')
    mw.writeFile(credFile(), json.dumps(data))
    os.chmod(credFile(), 0o600)
    # a token issued for another client no longer works
    token = getServerDir() + "/token.json"
    if os.path.exists(token):
        os.remove(token)
    kind = 'Desktop app' if 'installed' in data else 'Web application'
    return mw.returnJson(True, 'Kredensial disimpan (%s). Lanjutkan ke otorisasi.' % kind)


def setAuthUrl():
    args = getArgs()
    data = checkArgs(args, ['url'])
    if not data[0]:
        return data[1]
    try:
        return gd.set_auth_url(args['url'].strip())
    except Exception as e:
        return mw.returnJson(False, "Otorisasi gagal: " + str(e))


def clearAuth():
    token = getServerDir() + "/token.json"
    if os.path.exists(token):
        os.remove(token)
    return mw.returnJson(True, "Hapus otorisasi berhasil!")


def getList():
    if not isAuthApi():
        return mw.returnJson(False, "Belum dikonfigurasi, silakan klik`Otorisasi`", [])

    args = getArgs()
    data = checkArgs(args, ['file_id'])
    if not data[0]:
        return data[1]

    try:
        flist = gd.get_list(args['file_id'])
        return mw.returnJson(True, "ok", flist)
    except Exception as e:
        return mw.returnJson(False, str(e), [])


def createDir():
    if not isAuthApi():
        return mw.returnJson(False, "Belum dikonfigurasi, silakan klik`Otorisasi`", [])

    args = getArgs()
    data = checkArgs(args, ['parents', 'name'])
    if not data[0]:
        return data[1]
    isok = gd.create_folder(args['name'], args['parents'])
    if isok:
        return mw.returnJson(True, "Berhasil dibuat")
    return mw.returnJson(False, "Gagal dibuat")


def deleteDir():
    args = getArgs()
    data = checkArgs(args, ['dir_name', 'path'])
    if not data[0]:
        return data[1]

    isok = gd.delete_file_by_id(args['dir_name'])
    if isok:
        return mw.returnJson(True, "Berhasil dihapus")
    return mw.returnJson(False, "File tidak kosong, gagal dihapus!")


def deleteFile():
    args = getArgs()
    data = checkArgs(args, ['path', 'filename'])
    if not data[0]:
        return data[1]

    isok = gd.delete_file(args['filename'])
    if isok:
        return mw.returnJson(True, "Berhasil dihapus")
    return mw.returnJson(False, "Gagal dihapus")


def findPathName(path, filename):
    f = os.scandir(path)
    l = []
    for ff in f:
        t = {}
        if ff.name.find(filename) > -1:
            t['filename'] = path + '/' + ff.name
            l.append(t)
    return l


def dbPluginPath(stype):
    plugin = 'mysql'
    if stype.find('database_') > -1:
        plugin = stype.replace('database_', '')
    return mw.getServerDir() + '/' + plugin


def listNames(stype):
    """names behind the ALL option of a scheduled task"""
    if stype == 'site':
        rows = mw.M('sites').field('name').select()
    elif stype == 'database' or stype.find('database_') > -1:
        rows = mw.M('databases').dbPos(dbPluginPath(stype), 'mysql').field('name').select()
    else:
        return []
    if type(rows) != list:
        return []
    return [r['name'] for r in rows]


def backupOne(stype, name, num):
    """make a local backup with the panel script, upload it, keep `num` on Drive"""
    backup_dir = mw.getBackupDir()
    run_dir = mw.getRunDir()

    prefix_dict = {
        "site": "web",
        "database": "db",
        "path": "path",
    }

    cmd = 'python3 ' + run_dir + '/scripts/backup.py ' + stype + ' ' + name + ' ' + str(num)
    if stype.find('database_') > -1:
        plugin_name = stype.replace('database_', '')
        cmd = 'python3 ' + run_dir + '/plugins/' + plugin_name + '/scripts/backup.py database ' + name + ' ' + str(num)
    os.system(cmd)

    if stype.find('database_') > -1:
        bk_name = 'database'
        bk_prefix = stype.replace('database_', '') + '/db'
        data_type = 'database'
    else:
        bk_prefix = prefix_dict[stype]
        bk_name = stype
        data_type = stype

    base = os.path.basename(name) if stype == 'path' else name
    find_path = backup_dir + '/' + bk_name + '/' + bk_prefix + '_' + base
    find_new_file = "ls " + find_path + "_* | grep '.gz' | cut -d \\  -f 1 | awk 'END {print}'"
    filename = mw.execShell(find_new_file)[0].strip()
    if filename == "":
        mw.echoInfo("File backup untuk {} tidak ditemukan!".format(name))
        return False

    mw.echoInfo("Mengunggah {}".format(filename))
    try:
        gd.upload_file(filename, data_type)
    except Exception as e:
        mw.echoInfo("Upload {} gagal: {}".format(filename, e))
        return False
    mw.echoInfo("Berhasil diunggah")

    try:
        for fn in gd.prune(data_type, filename, num):
            mw.echoInfo("---Menghapus backup lama di Google Drive: " + fn)
    except Exception as e:
        mw.echoInfo("Membersihkan backup lama gagal: {}".format(e))
    return True


def backupAllFunc(stype):
    if not isAuthApi():
        mw.echoInfo("Google Drive belum diotorisasi, backup tidak bisa diunggah!")
        mw.notifyMessage('[MIT Panel] Backup Google Drive gagal: belum diotorisasi', 'gdrive_backup', 3600, False)
        return ''

    stype = sys.argv[1]
    name = sys.argv[2]
    num = sys.argv[3]

    names = listNames(stype) if name == 'ALL' else [name]
    failed = []
    for n in names:
        mw.echoStart('Backup {} {}'.format(stype, n))
        if not backupOne(stype, n, num):
            failed.append(n)
        mw.echoEnd('Selesai {}'.format(n))

    if failed:
        msg = 'Backup ke Google Drive gagal untuk {}: {}'.format(stype, ', '.join(failed))
        mw.writeLog('Google Drive', msg)
        mw.notifyMessage('[MIT Panel] ' + msg, 'gdrive_backup', 3600, False)
    return ''


# ---------------------------------------------------------------- automatic backup
AUTO_PREFIX = '[Auto GDrive] '


def autoTasks():
    rows = mw.M('crontab').where('backup_to=?', ('gdrive',)).field(
        'id,name,where_hour,where_minute,save,stype,sname,echo').select()
    if type(rows) != list:
        return []
    return rows


def dbStypes():
    """backup types of the installed database engines"""
    types = []
    if os.path.exists(mw.getServerDir() + '/mysql/etc/my.cnf'):
        types.append('database')
    if os.path.exists(mw.getServerDir() + '/mariadb/etc/my.cnf'):
        types.append('database_mariadb')
    return types


def getSetup():
    data = {
        'has_credentials': os.path.exists(credFile()),
        'authorized': isAuthApi(),
        'redirect_uri': 'http://localhost',
        'tasks': autoTasks(),
        'db_types': dbStypes(),
    }
    return mw.returnJson(True, 'ok', data)


def setAutoBackup():
    """create (or replace) daily ALL-sites / ALL-databases tasks that upload to Drive"""
    if not isAuthApi():
        return mw.returnJson(False, 'Google Drive belum diotorisasi.')
    args = getArgs()
    try:
        hour = int(args.get('hour', 2))
        minute = int(args.get('minute', 30))
        save = int(args.get('save', 7))
    except Exception:
        return mw.returnJson(False, 'Jam, menit dan jumlah simpan harus angka.')
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 1 <= save <= 365):
        return mw.returnJson(False, 'Jam 0-23, menit 0-59, jumlah simpan 1-365.')

    import crontab_api
    cron = crontab_api.crontab_api()

    for t in autoTasks():
        if t['name'].startswith(AUTO_PREFIX):
            cron.delete(t['id'])

    wanted = []
    if args.get('sites', True):
        wanted.append(('site', 'Semua situs'))
    if args.get('databases', True):
        for st in dbStypes():
            wanted.append((st, 'Semua database' + (' MariaDB' if st == 'database_mariadb' else '')))

    made = []
    for i, (stype, label) in enumerate(wanted):
        params = {
            'name': AUTO_PREFIX + label,
            'type': 'day', 'week': '', 'where1': '',
            # databases 15 minutes after the sites so they do not overlap
            'hour': str((hour + (minute + 15 * i) // 60) % 24),
            'minute': str((minute + 15 * i) % 60),
            'save': str(save), 'backup_to': 'gdrive',
            'stype': stype, 'sname': 'ALL', 'sbody': '', 'urladdress': '',
        }
        res = cron.add(params)
        if type(res) == dict or not res:
            return mw.returnJson(False, 'Gagal membuat tugas: ' + str(res))
        made.append(label)

    msg = 'Backup otomatis ke Google Drive aktif setiap hari %02d:%02d: %s (simpan %d terakhir).' % (
        hour, minute, ', '.join(made), save)
    mw.writeLog('Google Drive', msg)
    return mw.returnJson(True, msg)


def delAutoBackup():
    import crontab_api
    cron = crontab_api.crontab_api()
    n = 0
    for t in autoTasks():
        if t['name'].startswith(AUTO_PREFIX):
            cron.delete(t['id'])
            n += 1
    return mw.returnJson(True, '%d tugas backup otomatis dihapus.' % n)


def runAutoBackup():
    """start all Drive backup tasks now, in the background"""
    tasks = autoTasks()
    if not tasks:
        return mw.returnJson(False, 'Belum ada tugas backup ke Google Drive.')
    cron_dir = mw.getServerDir() + '/cron'
    for t in tasks:
        script = cron_dir + '/' + t['echo']
        if os.path.exists(script):
            mw.execShell('nohup bash ' + script + ' >> ' + script + '.log 2>&1 &')
    return mw.returnJson(True, 'Backup dijalankan di background. Lihat log di menu Cron.')


def installPreInspection():
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
    elif func == 'install_pre_inspection':
        print(installPreInspection())
    elif func == 'conf':
        print(getConf())
    elif func == 'set_auth_url':
        print(setAuthUrl())
    elif func == 'set_credentials':
        print(setCredentials())
    elif func == 'get_setup':
        print(getSetup())
    elif func == 'set_auto_backup':
        print(setAutoBackup())
    elif func == 'del_auto_backup':
        print(delAutoBackup())
    elif func == 'run_auto_backup':
        print(runAutoBackup())
    elif func == 'clear_auth':
        print(clearAuth())
    elif func == "get_list":
        print(getList())
    elif func == "create_dir":
        print(createDir())
    elif func == "delete_dir":
        print(deleteDir())
    elif func == 'delete_file':
        print(deleteFile())
    elif in_array(func, ['site', 'database', 'path']) or func.find('database_') > -1:
        print(backupAllFunc(func))
    else:
        print('error')
