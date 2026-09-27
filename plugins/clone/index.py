#!/usr/bin/python3
# coding:utf-8

import sys
import os
import json
import time
import base64
import signal
import subprocess

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/class/core")
import mit


def getPluginDir():
    return mit.getPluginDir() + '/clone'


def getServerDir():
    return mit.getServerDir() + '/clone'


def getArgs():
    '''arguments arrive as base64(JSON) so passwords survive the shell'''
    for a in reversed(sys.argv[2:]):
        try:
            return json.loads(base64.b64decode(a.strip()).decode('utf-8'))
        except Exception:
            continue
    return {}


def statusFile():
    return getServerDir() + '/status.json'


def logFile():
    return getServerDir() + '/clone.log'


def readStatus():
    try:
        return json.loads(mit.readFile(statusFile()))
    except Exception:
        return {'state': 'idle', 'step': '', 'percent': 0}


def isRunning(st=None):
    st = st or readStatus()
    if st.get('state') != 'running':
        return False
    try:
        os.kill(int(st.get('pid', 0)), 0)
        return True
    except Exception:
        return False


def remoteFor(args):
    sys.path.insert(0, getPluginDir())
    import clone_task
    if args.get('password'):
        os.environ['SSHPASS'] = args['password']
    else:
        os.environ.pop('SSHPASS', None)
    return clone_task, clone_task.Remote(args)


def checkArgs(args):
    if not args.get('host'):
        return 'Alamat server tujuan wajib diisi'
    if not args.get('password') and not args.get('key'):
        return 'Isi password SSH atau path private key'
    if args.get('key') and not os.path.exists(args['key']):
        return 'File private key tidak ditemukan: ' + args['key']
    if args['host'] in ('127.0.0.1', 'localhost', mit.getLocalIp()):
        return 'Server tujuan tidak boleh server ini sendiri'
    return ''


def testConn():
    args = getArgs()
    err = checkArgs(args)
    if err:
        return mit.returnJson(False, err)
    try:
        ct, rm = remoteFor(args)
        if rm.use_pass and ct.local('command -v sshpass')[0] != 0:
            return mit.returnJson(False, 'sshpass belum terpasang di server ini. Pasang ulang plugin ini atau pakai SSH key.')
        code, out, err = rm.run('uname -sr; id -u; (. /etc/os-release 2>/dev/null; echo "$PRETTY_NAME"); '
                                'free -m | awk \'/Mem:/{print $2}\'; df -h / | awk \'NR==2{print $4}\'', check=False)
        if code != 0:
            return mit.returnJson(False, 'SSH gagal: ' + (err.strip() or out.strip())[-400:])
        lines = out.strip().split('\n') + [''] * 5
        if lines[1].strip() != '0':
            return mit.returnJson(False, 'User SSH harus root di server tujuan')

        info = {
            'kernel': lines[0], 'os': lines[2], 'ram_mb': lines[3], 'disk_free': lines[4],
            'panel': rm.exists(ct.PANEL + '/app.py'),
            'software': [],
        }
        for name, version in ct.installedSoftware():
            info['software'].append({'name': name, 'version': version,
                                     'installed': ct.remoteHasSoftware(rm, name, version)})
        return mit.returnJson(True, 'Terhubung', info)
    except Exception as e:
        return mit.returnJson(False, 'Tes koneksi gagal: ' + str(e))


def runCmd():
    '''run one command on the target over SSH and return its output'''
    args = getArgs()
    err = checkArgs(args)
    if err:
        return mit.returnJson(False, err)
    command = args.get('cmd', '').strip()
    if command == '':
        return mit.returnJson(False, 'Perintah kosong')
    try:
        ct, rm = remoteFor(args)
        code, out, err = rm.run(command, check=False, timeout=int(args.get('timeout', 120)))
    except subprocess.TimeoutExpired:
        return mit.returnJson(False, 'Perintah melebihi batas waktu. Untuk proses panjang gunakan terminal interaktif.')
    except Exception as e:
        return mit.returnJson(False, 'SSH gagal: ' + str(e))
    mit.writeLog('Clone Server', 'SSH %s@%s: %s' % (args.get('user', 'root'), args['host'], command[:200]))
    return mit.returnJson(True, 'ok', {'code': code, 'out': out[-60000:], 'err': err[-20000:]})


def saveSshHost():
    '''register the target in the WebSSH host list so the interactive terminal
    can log in with a private key; the key itself never goes to the browser'''
    args = getArgs()
    err = checkArgs(args)
    if err:
        return mit.returnJson(False, err)
    info = {'port': str(args.get('port', '22') or '22'), 'username': args.get('user', 'root') or 'root',
            'ps': 'Clone target'}
    if args.get('key'):
        info['type'] = '1'
        info['pkey'] = mit.readFile(args['key'])
        info['pkey_passwd'] = ''
    else:
        info['type'] = '0'
        info['password'] = args.get('password', '')
    host_dir = mit.getServerDir() + '/webssh/host/' + args['host'].strip()
    if not os.path.exists(host_dir):
        os.makedirs(host_dir)
    mit.writeFile(host_dir + '/info.json', mit.enDoubleCrypt('mit', json.dumps(info)))
    os.chmod(host_dir + '/info.json', 0o600)
    return mit.returnJson(True, 'Host disimpan di daftar WebSSH')


def startClone():
    if isRunning():
        return mit.returnJson(False, 'Clone sedang berjalan')
    args = getArgs()
    err = checkArgs(args)
    if err:
        return mit.returnJson(False, err)

    if not os.path.exists(getServerDir()):
        os.makedirs(getServerDir())
    job = {
        'host': args['host'].strip(),
        'port': str(args.get('port', '22')).strip() or '22',
        'user': args.get('user', 'root').strip() or 'root',
        'key': args.get('key', '').strip(),
        'panel': bool(args.get('panel', True)),
        'install_soft': bool(args.get('install_soft', True)),
        'sites': bool(args.get('sites', True)),
        'databases': bool(args.get('databases', True)),
    }
    job_file = getServerDir() + '/job_%d.json' % int(time.time())
    mit.writeFile(job_file, json.dumps(job))
    os.chmod(job_file, 0o600)

    env = dict(os.environ)
    env.pop('SSHPASS', None)
    if args.get('password'):
        env['SSHPASS'] = args['password']

    mit.writeFile(statusFile(), json.dumps({'state': 'running', 'step': 'Mulai', 'percent': 0, 'pid': 0}))
    p = subprocess.Popen([sys.executable, getPluginDir() + '/clone_task.py', job_file],
                         cwd=mit.getRunDir(), env=env, stdout=subprocess.DEVNULL,
                         stderr=open(getServerDir() + '/clone.err', 'w'), start_new_session=True)
    mit.writeFile(statusFile(), json.dumps({'state': 'running', 'step': 'Mulai', 'percent': 0, 'pid': p.pid}))
    mit.writeLog('Clone Server', 'Clone ke %s dimulai' % job['host'])
    return mit.returnJson(True, 'Clone dimulai')


def getStatus():
    st = readStatus()
    if st.get('state') == 'running' and not isRunning(st) and st.get('pid'):
        err = mit.readFile(getServerDir() + '/clone.err') or ''
        st = {'state': 'failed', 'step': 'Proses berhenti tiba-tiba. ' + err[-300:], 'percent': 0}
    log = mit.readFile(logFile()) or ''
    st['log'] = log[-20000:]
    return mit.returnJson(True, 'ok', st)


def cancelClone():
    st = readStatus()
    if not isRunning(st):
        return mit.returnJson(False, 'Tidak ada clone yang berjalan')
    try:
        os.killpg(os.getpgid(int(st['pid'])), signal.SIGTERM)
    except Exception as e:
        return mit.returnJson(False, 'Gagal membatalkan: ' + str(e))
    mit.writeFile(statusFile(), json.dumps({'state': 'failed', 'step': 'Dibatalkan', 'percent': 0}))
    mit.writeFile(logFile(), time.strftime('%H:%M:%S') + ' Dibatalkan oleh admin\n', 'a+')
    return mit.returnJson(True, 'Clone dibatalkan')


if __name__ == "__main__":
    func = sys.argv[1]
    if func == 'status':
        print('start')
    elif func in ('start', 'stop', 'restart', 'reload'):
        print('ok')
    elif func == 'test_conn':
        print(testConn())
    elif func == 'start_clone':
        print(startClone())
    elif func == 'get_status':
        print(getStatus())
    elif func == 'cancel_clone':
        print(cancelClone())
    elif func == 'run_cmd':
        print(runCmd())
    elif func == 'save_ssh_host':
        print(saveSshHost())
    else:
        print('error')
