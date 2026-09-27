// arguments go to the plugin as base64(JSON) so passwords survive the shell
function clonePost(func, args, callback, title) {
    var b64 = args ? btoa(unescape(encodeURIComponent(JSON.stringify(args)))) : '';
    var loadT = layer.msg(title || 'Memproses...', { icon: 16, time: 0, shade: 0.3 });
    $.post('/plugins/run', { name: 'clone', func: func, args: b64 }, function (data) {
        layer.close(loadT);
        var rdata;
        try {
            rdata = $.parseJSON(data.data);
        } catch (e) {
            layer.msg(data.msg || data.data || 'Error', { icon: 2 });
            return;
        }
        callback(rdata);
    }, 'json');
}

function cloneArgs() {
    return {
        host: $("input[name='clone_host']").val(),
        port: $("input[name='clone_port']").val(),
        user: $("input[name='clone_user']").val(),
        password: $("input[name='clone_pass']").val(),
        key: $("input[name='clone_key']").val(),
        panel: $("input[name='clone_panel']").prop('checked'),
        install_soft: $("input[name='clone_soft']").prop('checked'),
        sites: $("input[name='clone_sites']").prop('checked'),
        databases: $("input[name='clone_dbs']").prop('checked')
    };
}

function cloneRow(label, input) {
    return '<p style="margin-bottom:8px"><span style="display:inline-block;width:150px">' + label + '</span>' + input + '</p>';
}

function cloneCheck(name, label) {
    return '<label style="font-weight:normal;display:block"><input type="checkbox" name="' + name + '" checked> ' + label + '</label>';
}

// target entered in the form; kept in memory only (never stored) so the
// SSH tab can use it after switching tabs
var cloneTarget = null;

function cloneForm() {
    cloneCloseTerm();
    var con = '<div class="clone-form">'
        + cloneRow('IP / host tujuan', '<input class="bt-input-text" name="clone_host" style="width:220px" placeholder="203.0.113.10">')
        + cloneRow('Port SSH', '<input class="bt-input-text" name="clone_port" style="width:80px" value="22">')
        + cloneRow('User', '<input class="bt-input-text" name="clone_user" style="width:120px" value="root">')
        + cloneRow('Password SSH', '<input class="bt-input-text" name="clone_pass" type="password" style="width:220px" autocomplete="new-password">')
        + cloneRow('atau private key', '<input class="bt-input-text" name="clone_key" style="width:220px" placeholder="/root/.ssh/id_rsa">')
        + '<div style="margin:10px 0 10px 150px">'
        + cloneCheck('clone_panel', 'Salin / pasang MIT Panel di tujuan')
        + cloneCheck('clone_soft', 'Pasang software yang belum ada (versi sama)')
        + cloneCheck('clone_sites', 'Situs, vhost, SSL, rewrite, proxy')
        + cloneCheck('clone_dbs', 'Database + user database')
        + '</div>'
        + '<div style="margin-left:150px">'
        + '<button class="btn btn-default btn-sm mr5" onclick="cloneTest()">Tes Koneksi</button>'
        + '<button class="btn btn-success btn-sm" onclick="cloneStart()">Mulai Clone</button>'
        + '</div>'
        + '<div class="clone-plan" style="margin-top:15px"></div>'
        + '<ul class="help-info-text c7 mtb15">'
        + '<li>Server tujuan sebaiknya server baru. Situs dan database dengan nama sama di tujuan akan ditimpa.</li>'
        + '<li>Login panel dan password root database di server tujuan tidak diubah.</li>'
        + '<li>Password SSH hanya dipakai selama proses berjalan dan tidak disimpan.</li>'
        + '<li>Setelah selesai, arahkan DNS domain ke IP server tujuan.</li>'
        + '</ul></div>';
    $(".soft-man-con").html(con);

    if (cloneTarget) {
        $("input[name='clone_host']").val(cloneTarget.host);
        $("input[name='clone_port']").val(cloneTarget.port);
        $("input[name='clone_user']").val(cloneTarget.user);
        $("input[name='clone_pass']").val(cloneTarget.password);
        $("input[name='clone_key']").val(cloneTarget.key);
    }
    $(".clone-form input").on('input change', function () {
        cloneTarget = cloneArgs();
    });
}

function cloneTest() {
    clonePost('test_conn', cloneArgs(), function (rdata) {
        if (!rdata.status) {
            layer.msg(rdata.msg, { icon: 2, time: 6000 });
            return;
        }
        var d = rdata.data;
        var soft = '';
        for (var i = 0; i < d.software.length; i++) {
            var s = d.software[i];
            soft += '<tr><td>' + s.name + '</td><td>' + s.version + '</td><td>'
                + (s.installed ? '<span style="color:#20a53a">sudah ada</span>' : '<span style="color:#f0ad4e">akan dipasang</span>')
                + '</td></tr>';
        }
        var html = '<table class="table table-bordered">'
            + '<tr><th>Sistem tujuan</th><td colspan="2">' + d.os + ' (' + d.kernel + ')</td></tr>'
            + '<tr><th>RAM / disk kosong</th><td colspan="2">' + d.ram_mb + 'MB / ' + d.disk_free + '</td></tr>'
            + '<tr><th>MIT Panel</th><td colspan="2">' + (d.panel ? 'sudah terpasang' : 'belum ada, akan dipasang') + '</td></tr>'
            + '<tr><th>Software</th><th>Versi</th><th>Di tujuan</th></tr>' + soft
            + '</table>';
        $(".clone-plan").html(html);
        layer.msg('Koneksi berhasil', { icon: 1 });
    }, 'Menguji koneksi SSH...');
}

function cloneStart() {
    layer.confirm('Mulai clone ke server tujuan? Proses bisa memakan waktu lama jika software perlu dikompilasi.', { icon: 3, closeBtn: 2 }, function () {
        clonePost('start_clone', cloneArgs(), function (rdata) {
            layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
            if (rdata.status) {
                $(".bt-w-menu p").removeClass('bgw').eq(1).addClass('bgw');
                cloneProgress();
            }
        });
    });
}

var cloneTimer = null;
function cloneProgress() {
    cloneCloseTerm();
    if (cloneTimer) clearTimeout(cloneTimer);
    $.post('/plugins/run', { name: 'clone', func: 'get_status', args: '' }, function (data) {
        var rdata = $.parseJSON(data.data);
        var st = rdata.data;
        var color = st.state == 'failed' ? '#d9534f' : (st.state == 'done' ? '#20a53a' : '#337ab7');
        var labels = { idle: 'Belum ada proses', running: 'Berjalan', done: 'Selesai', failed: 'Gagal' };
        var label = labels[st.state] || st.state;
        var con = '<p><b>Status:</b> <span style="color:' + color + '">' + label + '</span> &nbsp; ' + $('<div>').text(st.step || '').html() + '</p>'
            + '<div class="progress" style="margin:8px 0"><div class="progress-bar" style="width:' + (st.percent || 0) + '%;background:' + color + '">' + (st.percent || 0) + '%</div></div>'
            + '<textarea readonly class="bt-input-text" style="width:100%;height:330px;font-family:monospace;font-size:12px">' + $('<div>').text(st.log || '').html() + '</textarea>'
            + (st.state == 'running' ? '<button class="btn btn-danger btn-sm mt10" onclick="cloneCancel()">Batalkan</button>' : '');
        // only redraw while the progress tab is the one on screen
        if ($(".bt-w-menu p.bgw").index() == 1) {
            $(".soft-man-con").html(con);
            var ta = $(".soft-man-con textarea")[0];
            if (ta) ta.scrollTop = ta.scrollHeight;
        }
        if (st.state == 'running') {
            cloneTimer = setTimeout(cloneProgress, 3000);
        }
    }, 'json');
}

function cloneCancel() {
    layer.confirm('Batalkan proses clone?', { icon: 3, closeBtn: 2 }, function () {
        clonePost('cancel_clone', {}, function (rdata) {
            layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
            cloneProgress();
        });
    });
}


// ------------------------------ SSH to the target ------------------------------
var cloneTerm = null;

function cloneCloseTerm() {
    if (cloneTerm) {
        try { cloneTerm.close(); } catch (e) {}
        cloneTerm = null;
    }
}

var cloneQuickCmds = [
    ['Info sistem', 'hostnamectl 2>/dev/null || uname -a; echo; uptime; echo; free -h; echo; df -h -x tmpfs -x devtmpfs'],
    ['Status layanan', 'for s in apache openresty mysql mariadb $(ls /opt/mit/server/php 2>/dev/null | sed "s/^/php/"); do printf "%-12s %s\n" $s "$(systemctl is-active $s 2>/dev/null)"; done'],
    ['Login panel', 'mit default 2>/dev/null || bash /etc/init.d/mit default'],
    ['Watchdog log', 'tail -n 50 /opt/mit/server/panel/logs/watchdog.log 2>/dev/null || echo "belum ada log"'],
    ['Error web server', 'tail -n 50 /opt/mit/server/apache/logs/error_log 2>/dev/null || tail -n 50 /opt/mit/server/openresty/nginx/logs/error.log'],
    ['Proses teratas', 'ps aux --sort=-%mem | head -n 15']
];

function cloneSsh() {
    cloneCloseTerm();
    if (!cloneTarget || !cloneTarget.host) {
        layer.msg('Isi data server tujuan di tab "Clone Server" dulu', { icon: 0 });
        $(".bt-w-menu p").removeClass('bgw').eq(0).addClass('bgw');
        cloneForm();
        return;
    }
    var t = cloneTarget;
    var quick = '';
    for (var i = 0; i < cloneQuickCmds.length; i++) {
        quick += '<button class="btn btn-default btn-xs mr5" style="margin-bottom:5px" onclick="cloneRunQuick(' + i + ')">' + cloneQuickCmds[i][0] + '</button>';
    }
    var con = '<p style="margin-bottom:8px"><b>Server tujuan:</b> ' + $('<div>').text((t.user || 'root') + '@' + t.host + ':' + (t.port || '22')).html()
        + ' &nbsp; <button class="btn btn-success btn-sm" onclick="cloneOpenTerm()">Buka Terminal Interaktif</button></p>'
        + '<div id="clone_term" style="height:360px;background:#000;display:none;margin-bottom:10px"></div>'
        + '<div class="clone-cmd">'
        + '<p style="margin-bottom:6px">' + quick + '</p>'
        + '<p style="margin-bottom:6px"><input class="bt-input-text" name="clone_cmd" style="width:78%" placeholder="Perintah, contoh: systemctl status mysql">'
        + ' <button class="btn btn-default btn-sm" onclick="cloneRunCmd()">Jalankan</button></p>'
        + '<pre class="clone-cmd-out" style="height:300px;overflow:auto;background:#1e1e1e;color:#ddd;font-size:12px;padding:8px;margin:0;white-space:pre-wrap"></pre>'
        + '</div>';
    $(".soft-man-con").html(con);
    $("input[name='clone_cmd']").keyup(function (e) {
        if (e.keyCode == 13) cloneRunCmd();
    });
}

function cloneRunQuick(i) {
    $("input[name='clone_cmd']").val(cloneQuickCmds[i][1]);
    cloneRunCmd();
}

function cloneRunCmd() {
    var cmd = $("input[name='clone_cmd']").val();
    if ($.trim(cmd) == '') return;
    var args = $.extend({}, cloneTarget, { cmd: cmd });
    clonePost('run_cmd', args, function (rdata) {
        var out = $('.clone-cmd-out');
        if (!rdata.status) {
            out.text(rdata.msg);
            return;
        }
        var d = rdata.data;
        var nl = String.fromCharCode(10);
        out.text('$ ' + cmd + nl + d.out + (d.err ? nl + d.err : '') + nl + '[exit ' + d.code + ']');
        out.scrollTop(out[0].scrollHeight);
    }, 'Menjalankan perintah di server tujuan...');
}

function cloneOpenTerm() {
    var t = cloneTarget;
    var open = function (info) {
        cloneCloseTerm();
        $('#clone_term').show().html('');
        cloneTerm = new Terms_WebSocketIO('#clone_term', { ssh_info: info });
        cloneTerm.registerCloseCallBack(function () {
            layer.msg('Terminal ditutup', { icon: 1 });
            $('#clone_term').hide();
            cloneTerm = null;
        });
    };
    if (t.key) {
        // the private key stays on the server: register the host, then connect by name
        clonePost('save_ssh_host', t, function (rdata) {
            if (!rdata.status) {
                layer.msg(rdata.msg, { icon: 2 });
                return;
            }
            open({ host: t.host, id: 'clone_term' });
        }, 'Menyiapkan koneksi...');
    } else {
        open({ host: t.host, port: t.port || '22', username: t.user || 'root', password: t.password, type: '0', id: 'clone_term' });
    }
}


// ------------------------------ in-panel guide ------------------------------
function cloneGuide() {
    cloneCloseTerm();
    var docs = 'https://github.com/tauviec/MIT-Panel/blob/main/docs/';
    var con = '<div style="line-height:22px">'
        + '<p><b>Clone Server</b> menyalin seluruh server ini ke server lain <b>sekali jalan</b>: MIT Panel, software dengan versi sama, '
        + 'situs, vhost, SSL, database beserta user-nya. Setelah itu kedua server berjalan sendiri-sendiri.</p>'
        + '<ol style="padding-left:18px;margin:10px 0">'
        + '<li>Siapkan server tujuan: Linux baru, login SSH <b>root</b>, disk cukup.</li>'
        + '<li>Tab <b>Clone Server</b>: isi IP, port SSH, user, password atau path private key.</li>'
        + '<li>Klik <b>Tes Koneksi</b> dan periksa daftar software (sudah ada / akan dipasang).</li>'
        + '<li>Klik <b>Mulai Clone</b>, pantau di tab <b>Progres &amp; Log</b>. Kompilasi software bisa 10-60 menit per software; halaman boleh ditutup.</li>'
        + '<li>Setelah <b>Selesai</b>, cek di tab <b>Terminal SSH</b> → <b>Status layanan</b>.</li>'
        + '<li>Uji situs lewat file <i>hosts</i> komputer Anda, lalu ubah DNS ke IP tujuan.</li>'
        + '</ol>'
        + '<p><b>Tidak ikut tersalin:</b> jadwal Cron, firewall, file di luar folder situs.</p>'
        + '<p style="margin-top:8px"><b>Clone atau Master-Slave?</b> Clone = salinan sekali (pindah server / siapkan server cadangan). '
        + 'Master-Slave = database tersalin terus-menerus (menu MySQL/MariaDB → Master-Slave). '
        + 'Untuk server cadangan: clone sekali, lalu aktifkan Master-Slave dan Rsyncd untuk file.</p>'
        + '<p style="margin-top:8px">Panduan lengkap: '
        + '<a class="btlink" target="_blank" href="' + docs + 'clone-server.md">Clone Server</a> · '
        + '<a class="btlink" target="_blank" href="' + docs + 'master-slave.md">Master-Slave</a> · '
        + '<a class="btlink" target="_blank" href="' + docs + 'server-cadangan.md">Server utama + cadangan</a></p>'
        + '</div>';
    $(".soft-man-con").html(con);
}
