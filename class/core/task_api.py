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


class task_api:

    def __init__(self):
        pass

    def countApi(self):
        c = mit.M('tasks').where("status!=?", ('1',)).count()
        return str(c)

    def listApi(self):

        p = request.form.get('p', '1')
        limit = request.form.get('limit', '10').strip()
        search = request.form.get('search', '').strip()

        start = (int(p) - 1) * int(limit)
        limit_str = str(start) + ',' + str(limit)

        _list = mit.M('tasks').where('', ()).field(
            'id,name,type,status,addtime,start,end').limit(limit_str).order('id desc').select()
        _ret = {}
        _ret['data'] = _list

        count = mit.M('tasks').where('', ()).count()
        _page = {}
        _page['count'] = count
        _page['tojs'] = 'remind'
        _page['p'] = p

        # return data
        _ret['count'] = count
        _ret['page'] = mit.getPage(_page)
        return mit.getJson(_ret)

    def getExecLogApi(self):
        file = mit.getRunDir() + "/tmp/panelExec.log"
        v = mit.getLastLine(file, 100)
        return v

    def getTaskSpeedApi(self):
        tempFile = mit.getRunDir() + '/tmp/panelExec.log'
        freshFile = mit.getRunDir() + '/tmp/panelFresh'

        find = mit.M('tasks').where('status=? OR status=?',
                                   ('-1', '0')).field('id,type,name,execstr').find()
        if not len(find):
            return mit.returnJson(False, 'No task queue is currently executing -2!')

        mit.triggerTask()

        data = {}
        data['name'] = find['name']
        data['execstr'] = find['execstr']
        if find['type'] == 'download':
            readLine = ""
            for i in range(3):
                try:
                    readLine = mit.readFile(tempFile)
                    if len(readLine) > 10:
                        data['msg'] = json.loads(readLine)
                        data['isDownload'] = True
                        break
                except Exception as e:
                    if i == 2:
                        mit.M('tasks').where("id=?", (find['id'],)).save(
                            'status', ('0',))
                        return mit.returnJson(False, 'No task queue is currently executing -4:' + str(e))
                time.sleep(0.5)
        else:
            data['msg'] = mit.getLastLine(tempFile, 10)
            data['isDownload'] = False

        data['task'] = mit.M('tasks').where("status!=?", ('1',)).field(
            'id,status,name,type').order("id asc").select()
        return mit.getJson(data)
