# coding: utf-8

import psutil
import time
import os
import sys
import mit
import re
import json
import pwd

from flask import request


class firewall_api:

    __isFirewalld = False
    __isIptables = False
    __isUfw = False
    __isMac = False

    def __init__(self):
        iptables_file = mit.systemdCfgDir() + '/iptables.service'
        if os.path.exists('/usr/sbin/firewalld'):
            self.__isFirewalld = True
        elif os.path.exists('/usr/sbin/ufw'):
            self.__isUfw = True
        elif os.path.exists(iptables_file):
            self.__isIptables = True
        elif mit.isAppleSystem():
            self.__isMac = True

    ##### ----- start ----- ###
    def addDropAddressApi(self):
        import re
        port = request.form.get('port', '').strip()
        ps = request.form.get('ps', '').strip()

        rep = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(\/\d{1,2})?$"
        if not re.search(rep, port):
            return mit.returnJson(False, 'Alamat IP yang kamu masukin nggak valid!')
        address = port
        if mit.M('firewall').where("port=?", (address,)).count() > 0:
            return mit.returnJson(False, 'The IP you want to block already exists in the block list, so there is no need to repeat it!')
        if self.__isUfw:
            mit.execShell('ufw deny from ' + address + ' to any')
        else:
            if self.__isIptables:
                cmd = 'iptables -I INPUT -s ' + address + ' -j DROP'
                mit.execShell(cmd)
            elif self.__isFirewalld:
                cmd = 'firewall-cmd --permanent --add-rich-rule=\'rule family=ipv4 source address="' + \
                    address + '" drop\''
                mit.execShell(cmd)
            else:
                pass

        msg = mit.getInfo('Block IP [{1}] successfully!', (address,))
        mit.writeLog("Firewall management", msg)
        addtime = time.strftime('%Y-%m-%d %X', time.localtime())
        mit.M('firewall').add('port,ps,addtime', (address, ps, addtime))
        self.firewallReload()
        return mit.returnJson(True, 'Berhasil ditambahin!')

    def addAcceptPortApi(self):
        if not self.getFwStatus():
            return mit.returnJson(False, 'Aturan cuma bisa ditambahin pas firewall nyala!')

        port = request.form.get('port', '').strip()
        ps = request.form.get('ps', '').strip()
        stype = request.form.get('type', '').strip()

        data = self.addAcceptPortArgs(port, ps, stype)
        return mit.getJson(data)

    def addAcceptPortArgs(self, port, ps, stype):
        import re
        import time

        if not self.getFwStatus():
            self.setFw(0)

        rep = r"^\d{1,5}(:\d{1,5})?$"
        if not re.search(rep, port):
            return mit.returnData(False, 'Rentang port salah!')

        if mit.M('firewall').where("port=?", (port,)).count() > 0:
            return mit.returnData(False, 'The port you want to allow already exists, so there is no need to allow it again!')

        msg = mit.getInfo('Successfully released port [{1}]', (port,))
        mit.writeLog("Firewall management", msg)
        addtime = time.strftime('%Y-%m-%d %X', time.localtime())
        mit.M('firewall').add('port,ps,addtime', (port, ps, addtime))

        self.addAcceptPort(port)
        self.firewallReload()
        return mit.returnData(True, 'Add release (' + port + ') port successfully!')

    def delDropAddressApi(self):
        if not self.getFwStatus():
            return mit.returnJson(False, 'Aturan cuma bisa dihapus pas firewall nyala!')

        port = request.form.get('port', '').strip()
        ps = request.form.get('ps', '').strip()
        sid = request.form.get('id', '').strip()
        address = port
        if self.__isUfw:
            mit.execShell('ufw delete deny from ' + address + ' to any')
        elif self.__isFirewalld:
            mit.execShell(
                'firewall-cmd --permanent --remove-rich-rule=\'rule family=ipv4 source address="' + address + '" drop\'')
        else:
            pass

        msg = mit.getInfo('Unblock IP[{1}]!', (address,))
        mit.writeLog("Firewall management", msg)
        mit.M('firewall').where("id=?", (sid,)).delete()

        self.firewallReload()
        return mit.returnJson(True, 'Berhasil dihapus!')

    def delAcceptPortApi(self):
        port = request.form.get('port', '').strip()
        sid = request.form.get('id', '').strip()
        mit_port = mit.readFile('data/port.pl')
        try:
            if(port == mit_port):
                return mit.returnJson(False, 'Failed, cannot delete current panel port!')
            if self.__isUfw:
                mit.execShell('ufw delete allow ' + port + '/tcp')
            elif self.__isFirewalld:
                port = port.replace(':', '-')
                mit.execShell(
                    'firewall-cmd --permanent --zone=public --remove-port=' + port + '/tcp')
                mit.execShell(
                    'firewall-cmd --permanent --zone=public --remove-port=' + port + '/udp')
            elif self.__isIptables:
                mit.execShell(
                    'iptables -D INPUT -p tcp -m state --state NEW -m tcp --dport ' + port + ' -j ACCEPT')
            else:
                pass
            msg = mit.getInfo('Deleting the firewall port [{1}] succeeded!', (port,))
            mit.writeLog("Firewall management", msg)
            mit.M('firewall').where("id=?", (sid,)).delete()

            self.firewallReload()
            return mit.returnJson(True, 'Berhasil dihapus!')
        except Exception as e:
            return mit.returnJson(False, 'Failed to delete!:' + str(e))

    def getWwwPathApi(self):
        path = mit.getLogsDir()
        return mit.getJson({'path': path})

    def getListApi(self):
        p = request.form.get('p', '1').strip()
        limit = request.form.get('limit', '10').strip()
        return self.getList(int(p), int(limit))

    def getLogListApi(self):
        p = request.form.get('p', '1').strip()
        limit = request.form.get('limit', '10').strip()
        search = request.form.get('search', '').strip()
        return self.getLogList(int(p), int(limit), search)

    def getSshInfoApi(self):
        data = {}

        file = '/etc/ssh/sshd_config'
        conf = mit.readFile(file)
        rep = r"#*Port\s+([0-9]+)\s*\n"
        port = re.search(rep, conf).groups(0)[0]

        isPing = True
        try:
            if mit.isAppleSystem():
                isPing = True
            else:
                file = '/etc/sysctl.conf'
                sys_conf = mit.readFile(file)
                rep = r"#*net\.ipv4\.icmp_echo_ignore_all\s*=\s*([0-9]+)"
                tmp = re.search(rep, sys_conf).groups(0)[0]
                if tmp == '1':
                    isPing = False
        except:
            isPing = True

        status = True
        cmd = "service sshd status | grep -P '(dead|stop)'|grep -v grep"
        ssh_status = mit.execShell(cmd)
        if ssh_status[0] != '':
            status = False

        cmd = "systemctl status sshd.service | grep 'dead'|grep -v grep"
        ssh_status = mit.execShell(cmd)
        if ssh_status[0] != '':
            status = False

        data['pass_prohibit_status'] = False
        pass_rep = r"#PasswordAuthentication\s+(\w*)\s*\n"
        pass_status = re.search(pass_rep, conf)
        if pass_status:
            data['pass_prohibit_status'] = True

        if not data['pass_prohibit_status']:
            pass_rep = r"PasswordAuthentication\s+(\w*)\s*\n"
            pass_status = re.search(pass_rep, conf)
            if pass_status and pass_status.groups(0)[0].strip() == 'no':
                data['pass_prohibit_status'] = True

        data['port'] = port
        data['status'] = status
        data['ping'] = isPing
        if mit.isAppleSystem():
            data['firewall_status'] = False
        else:
            data['firewall_status'] = self.getFwStatus()
        return mit.getJson(data)

    def setSshPortApi(self):
        port = request.form.get('port', '1').strip()
        if int(port) < 22 or int(port) > 65535:
            return mit.returnJson(False, 'Rentang port harus antara 22-65535!')

        ports = ['21', '25', '80', '443', '888']
        if port in ports:
            return mit.returnJson(False, '(' + port + ')' + ' special port cannot be set!')

        file = '/etc/ssh/sshd_config'
        conf = mit.readFile(file)

        rep = r"#*Port\s+([0-9]+)\s*\n"
        conf = re.sub(rep, "Port " + port + "\n", conf)
        mit.writeFile(file, conf)

        self.addAcceptPortArgs(port, 'SSH port modification', 'port')
        if self.__isUfw:
            mit.execShell("service ssh restart")
        elif self.__isIptables:
            mit.execShell("/etc/init.d/sshd restart")
        elif self.__isFirewalld:
            mit.execShell("systemctl restart sshd.service")
        else:
            return mit.returnJson(False, 'Fail to edit!')
        return mit.returnJson(True, 'Berhasil diubah!')

    def setSshStatusApi(self):
        if mit.isAppleSystem():
            return mit.returnJson(True, 'The development machine cannot operate!')

        status = request.form.get('status', '1').strip()
        msg = 'SSH service is enabled'
        act = 'start'
        if status == "1":
            msg = 'SSH service is disabled'
            act = 'stop'

        ssh_service = mit.systemdCfgDir() + '/sshd.service'
        if os.path.exists(ssh_service):
            mit.execShell("systemctl " + act + " sshd.service")
        else:
            mit.execShell('service sshd ' + act)

        if os.path.exists('/etc/init.d/sshd'):
            mit.execShell('/etc/init.d/sshd ' + act)

        mit.writeLog("Firewall management", msg)
        return mit.returnJson(True, 'Operasi berhasil!')

    def setSshPassStatusApi(self):
        if mit.isAppleSystem():
            return mit.returnJson(True, 'The development machine cannot operate!')

        status = request.form.get('status', '1').strip()
        msg = 'Prohibition of password login success'
        if status == "1":
            msg = 'Open the password and log in successfully'

        file = '/etc/ssh/sshd_config'
        if not os.path.exists(file):
            return mit.returnJson(False, 'Cannot be set!')

        conf = mit.readFile(file)

        if status == '1':
            rep = r"(#)?PasswordAuthentication\s+(\w*)\s*\n"
            conf = re.sub(rep, "PasswordAuthentication yes\n", conf)
        else:
            rep = r"(#)?PasswordAuthentication\s+(\w*)\s*\n"
            conf = re.sub(rep, "PasswordAuthentication no\n", conf)
        mit.writeFile(file, conf)
        mit.execShell("systemctl restart sshd.service")
        mit.writeLog("SSH management", msg)
        return mit.returnJson(True, msg)

    def setPingApi(self):
        if mit.isAppleSystem():
            return mit.returnJson(True, 'The development machine cannot operate!')

        status = request.form.get('status')
        filename = '/etc/sysctl.conf'
        conf = mit.readFile(filename)
        if conf.find('net.ipv4.icmp_echo') != -1:
            rep = r"net\.ipv4\.icmp_echo.*"
            conf = re.sub(rep, 'net.ipv4.icmp_echo_ignore_all=' + status, conf)
        else:
            conf += "\nnet.ipv4.icmp_echo_ignore_all=" + status

        mit.writeFile(filename, conf)
        mit.execShell('sysctl -p')
        return mit.returnJson(True, 'Berhasil diatur!')

    def setFwApi(self):
        if mit.isAppleSystem():
            return mit.returnJson(True, 'The development machine cannot be set!')

        status = request.form.get('status', '1')
        return mit.getJson(self.setFw(status))

    def setFwIptables(self, status):
        if status == '1':
            mit.execShell('service iptables save')
            mit.execShell('service iptables stop')
        else:
            _list = mit.M('firewall').field('id,port,ps,addtime').limit(
                '0,1000').order('id desc').select()

            mit.execShell('iptables -P INPUT DROP')
            mit.execShell('iptables -P OUTPUT ACCEPT')
            for x in _list:
                port = x['port']
                if mit.isIpAddr(port):
                    cmd = 'iptables -I INPUT -s ' + port + ' -j DROP'
                    mit.execShell(cmd)
                else:
                    self.addAcceptPort(port)

            mit.execShell('service iptables save')
            mit.execShell('service iptables start')

    def setFw(self, status):

        if self.__isIptables:
            self.setFwIptables(status)
            return mit.returnData(True, 'Berhasil diatur!')

        if status == '1':
            if self.__isUfw:
                mit.execShell('/usr/sbin/ufw disable')

            elif self.__isFirewalld:
                mit.execShell('systemctl stop firewalld.service')
                mit.execShell('systemctl disable firewalld.service')
            else:
                pass
        else:
            if self.__isUfw:
                mit.execShell("echo 'y'| ufw enable")
            elif self.__isFirewalld:
                mit.execShell('systemctl start firewalld.service')
                mit.execShell('systemctl enable firewalld.service')
            else:
                pass

        return mit.returnData(True, 'Berhasil diatur!')

    def delPanelLogsApi(self):
        mit.M('logs').where('id>?', (0,)).delete()
        mit.writeLog('Panel settings', 'Panel operation log has been cleared!')
        return mit.returnJson(True, 'Log operasi panel udah dibersihin!')

    ##### ----- start ----- ###

    def getList(self, page, limit):

        start = (page - 1) * limit

        _list = mit.M('firewall').field('id,port,ps,addtime').limit(
            str(start) + ',' + str(limit)).order('id desc').select()
        data = {}
        data['data'] = _list

        count = mit.M('firewall').count()
        _page = {}
        _page['count'] = count
        _page['tojs'] = 'showAccept'
        _page['p'] = page

        data['page'] = mit.getPage(_page)
        return mit.getJson(data)

    def getLogList(self, page, limit, search=''):
        find_search = ''
        if search != '':
            find_search = "type like '%" + search + "%' or log like '%" + \
                search + "%' or addtime like '%" + search + "%'"

        start = (page - 1) * limit

        _list = mit.M('logs').where(find_search, ()).field(
            'id,type,log,addtime').limit(str(start) + ',' + str(limit)).order('id desc').select()
        data = {}
        data['data'] = _list

        count = mit.M('logs').where(find_search, ()).count()
        _page = {}
        _page['count'] = count
        _page['tojs'] = 'getLogs'
        _page['p'] = page

        data['page'] = mit.getPage(_page)
        return mit.getJson(data)

    def addAcceptPort(self, port):
        if self.__isUfw:
            mit.execShell('ufw allow ' + port + '/tcp')
        elif self.__isFirewalld:
            port = port.replace(':', '-')
            cmd = 'firewall-cmd --permanent --zone=public --add-port=' + port + '/tcp'
            mit.execShell(cmd)
        elif self.__isIptables:
            cmd = 'iptables -I INPUT -p tcp -m state --state NEW -m tcp --dport ' + port + ' -j ACCEPT'
            mit.execShell(cmd)
        else:
            pass
        return True

    def firewallReload(self):
        if self.__isUfw:
            mit.execShell('/usr/sbin/ufw reload')
            return
        elif self.__isIptables:
            mit.execShell('service iptables save')
            mit.execShell('service iptables restart')
        elif self.__isFirewalld:
            mit.execShell('firewall-cmd --reload')
        else:
            pass

    def getFwStatus(self):
        if self.__isUfw:
            cmd = "/usr/sbin/ufw status| grep Status | awk -F ':' '{print $2}'"
            data = mit.execShell(cmd)
            if data[0].strip() == 'inactive':
                return False
            return True
        elif self.__isIptables:
            cmd = "systemctl status iptables | grep 'inactive'"
            data = mit.execShell(cmd)
            if data[0] != '':
                return False
            return True
        elif self.__isFirewalld:
            cmd = "ps -ef|grep firewalld |grep -v grep | awk '{print $2}'"
            data = mit.execShell(cmd)
            if data[0] == '':
                return False
            return True
        else:
            return False
