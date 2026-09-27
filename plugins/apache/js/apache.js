function apPost(method, args, callback){
    var loadT = layer.msg('Retrieving...', { icon: 16, time: 0, shade: 0.3 });
    $.post('/plugins/run', {name:'apache', func:method, args:JSON.stringify(args)}, function(data) {
        layer.close(loadT);
        if (!data.status){
            layer.msg(data.msg,{icon:0,time:2000,shade: [0.3, '#000']});
            return;
        }

        if(typeof(callback) == 'function'){
            callback(data);
        }
    },'json');
}

function apPluginService(_name){
    apPost('status', {}, function(data){
        apPluginSetService(_name, data.data == 'start');
    });
}

function apPluginSetService(_name, status){
    var serviceCon ='<p class="status">Current status：<span>'+(status ? 'start' : 'stop' )+
        '</span><span style="color: '+
        (status?'#20a53a;':'red;')+
        ' margin-left: 3px;" class="glyphicon ' + (status?'glyphicon glyphicon-play':'glyphicon-pause')+'"></span></p><div class="sfm-opt">\
            <button class="btn btn-default btn-sm" onclick="apPluginOpService(\''+_name+'\',\''+(status?'stop':'start')+'\')">'+(status?'Stop':'Start')+'</button>\
            <button class="btn btn-default btn-sm" onclick="apPluginOpService(\''+_name+'\',\'restart\')">Restart</button>\
            <button class="btn btn-default btn-sm" onclick="apPluginOpService(\''+_name+'\',\'reload\')">Reload</button>\
        </div>';
    $(".soft-man-con").html(serviceCon);
}

function apPluginOpService(_name, method) {
    layer.confirm(msgTpl('Do you really want {1} {2} service？', [method, _name]), {icon:3, closeBtn: 2}, function() {
        var e = layer.msg(msgTpl('Serving {1} {2}, please wait...', [method, _name]), {icon: 16, time: 0});
        $.post('/plugins/run', {name:_name, func:method}, function(g) {
            layer.close(e);
            var ok = g.data == 'ok';
            layer.msg(ok ? msgTpl('{1} service has been {2}', [_name, method]) : g.data, {icon: ok ? 1 : 2, time: ok ? 2000 : 10000});
            if (ok && method == 'start') {
                apPluginSetService(_name, true);
            } else if (ok && method == 'stop') {
                apPluginSetService(_name, false);
            }
        },'json').error(function() {
            layer.close(e);
            layer.msg('Abnormal operation!', {icon: 2});
        });
    });
}

function getApStatus() {
    $.post('/plugins/run', {name:'apache', func:'run_info'}, function(data) {
        try {
            var rdata = $.parseJSON(data.data);
            var con = "<div><table class='table table-hover table-bordered'>";
            for (var k in rdata) {
                con += "<tr><th>" + k + "</th><td>" + rdata[k] + "</td></tr>";
            }
            con += "</table></div>";
            $(".soft-man-con").html(con);
        } catch(err) {
            showMsg(data.data, function(){}, null, 3000);
        }
    },'json');
}

function setApCfg(){
    apPost('get_cfg', {}, function(data){
        var rdata = $.parseJSON(data.data).data;
        var mlist = '';
        for (var i = 0; i < rdata.length; i++) {
            var ibody = '<input style="width: 110px;" class="bt-input-text mr5" name="' + rdata[i].name + '" value="' + rdata[i].value + '" type="text" >';
            if (rdata[i].type == 1) {
                ibody = '<select class="bt-input-text mr5" name="' + rdata[i].name + '" style="width: 110px;">\
                    <option value="On" ' + (rdata[i].value == 'On' ? 'selected' : '') + '>On</option>\
                    <option value="Off" ' + (rdata[i].value == 'Off' ? 'selected' : '') + '>Off</option>\
                </select>';
            }
            mlist += '<p style="margin-top:15px;"><span style="display:inline-block;width:170px">' + rdata[i].name + '</span>' + ibody + ', <font class="c9">' + rdata[i].ps + '</font></p>';
        }
        var con = '<div class="conf_p" style="margin-bottom:0">' + mlist + '\
                    <div style="margin-top:10px; padding-right:15px" class="text-right">\
                        <button class="btn btn-success btn-sm mr5" onclick="setApCfg()">Refresh</button>\
                        <button class="btn btn-success btn-sm mr5" onclick="submitApConf()">Save</button>                        <button class="btn btn-danger btn-sm" name="apache" onclick="autoTuneWeb(this.name)">Tuning Otomatis (RAM)</button>\
                    </div>\
                </div>';
        $(".soft-man-con").html(con);
    });
}

function submitApConf() {
    var data = {};
    $(".conf_p input, .conf_p select").each(function(){
        data[$(this).attr('name')] = $(this).val();
    });
    apPost('set_cfg', data, function(rdata){
        var rdata = $.parseJSON(rdata.data);
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
    });
}

function apRebuildVhost() {
    var con = '<p>Buat vhost Apache untuk situs yang belum punya (misalnya situs yang dibuat saat masih memakai Nginx).</p>\
        <p class="c9">Vhost yang sudah ada tidak diubah.</p>\
        <button class="btn btn-success btn-sm mt10" onclick="apRebuildVhostRun()">Rebuild Vhost</button>';
    $(".soft-man-con").html(con);
}

function apRebuildVhostRun() {
    apPost('rebuild_vhost', {}, function(data){
        var rdata = $.parseJSON(data.data);
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2, time: 5000 });
    });
}

function autoTuneWeb(name) {
    $.post('/plugins/run', {name: name, func: 'get_tune_profile'}, function (data) {
        var rdata = $.parseJSON(data.data);
        var p = rdata.data.profile;
        var rows = '';
        for (var k in p) {
            rows += '<tr><td>' + k + '</td><td>' + p[k] + '</td></tr>';
        }
        layer.confirm('<p>Profil ' + rdata.data.label + ':</p><table class="table table-bordered">' + rows + '</table>'
            + '<p class="c9">Konfigurasi lama dibackup dan dikembalikan otomatis jika gagal.</p>',
            { icon: 3, title: 'Tuning Otomatis', area: '420px', closeBtn: 2 }, function () {
            var loadT = layer.msg('Menerapkan tuning...', { icon: 16, time: 0, shade: 0.3 });
            $.post('/plugins/run', {name: name, func: 'auto_tune'}, function (res) {
                layer.close(loadT);
                var r = $.parseJSON(res.data);
                layer.msg(r.msg, { icon: r.status ? 1 : 2, time: 8000 });
            }, 'json');
        });
    }, 'json');
}
