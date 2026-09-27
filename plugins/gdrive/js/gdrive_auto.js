// Google Drive: credentials guide + automatic daily backup of all sites / databases

function gdCredentials() {
    var steps = '<ol style="line-height:22px;padding-left:18px;margin-bottom:10px">'
        + '<li>Buka <a class="btlink" href="https://console.cloud.google.com/projectcreate" target="_blank">Google Cloud Console</a> dengan akun Google Anda, buat Project baru. <b>Gratis, tidak perlu kartu kredit.</b></li>'
        + '<li>Menu <b>APIs &amp; Services &rarr; Library</b>: cari <b>Google Drive API</b>, klik <b>Enable</b>.</li>'
        + '<li>Menu <b>OAuth consent screen</b>: pilih <b>External</b>, isi nama aplikasi dan email. Tidak perlu menambah scope.</li>'
        + '<li>Masih di OAuth consent screen: klik <b>Publish App</b> (status <b>In production</b>). '
        + '<span style="color:#d9534f">Penting:</span> jika tetap "Testing", izin kedaluwarsa tiap 7 hari dan backup berhenti.</li>'
        + '<li>Menu <b>Credentials &rarr; Create credentials &rarr; OAuth client ID</b>, tipe <b>Desktop app</b>, lalu <b>Download JSON</b>.</li>'
        + '<li>Buka file JSON itu, salin seluruh isinya ke kotak di bawah, klik Simpan.</li>'
        + '</ol>'
        + '<textarea class="bt-input-text gd_cred_json" style="width:100%;height:130px;font-family:monospace;font-size:12px" placeholder=\'{"installed":{"client_id":"...","client_secret":"..."}}\'></textarea>'
        + '<p class="c9" style="margin-top:6px">Panel hanya meminta izin <b>drive.file</b>: aplikasi ini hanya bisa melihat file yang dibuatnya sendiri, bukan isi Drive Anda yang lain. '
        + 'Ruang gratis Google Drive 15GB; panel menghapus backup lama sesuai jumlah simpan.</p>';

    var idx = layer.open({
        type: 1,
        title: 'Kredensial Google Drive',
        area: '640px',
        closeBtn: 1,
        content: '<div class="pd20">' + steps + '</div>',
        btn: ['Simpan', 'Batal'],
        yes: function () {
            var json = $('.gd_cred_json').val();
            if ($.trim(json) == '') {
                layer.msg('Tempel isi file JSON dulu', { icon: 2 });
                return;
            }
            gdPost('set_credentials', { json: json }, function (data) {
                var rdata = $.parseJSON(data.data);
                layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2, time: 4000 });
                if (rdata.status) {
                    layer.close(idx);
                    authApi();
                }
            });
        }
    });
}

function gdAutoBackup() {
    gdPost('get_setup', {}, function (data) {
        var rdata = $.parseJSON(data.data).data;
        if (!rdata.has_credentials) {
            gdCredentials();
            return;
        }
        if (!rdata.authorized) {
            layer.msg('Otorisasi Google Drive dulu', { icon: 0 });
            authApi();
            return;
        }

        var rows = '';
        var cur = null;
        for (var i = 0; i < rdata.tasks.length; i++) {
            var t = rdata.tasks[i];
            if (t.name.indexOf('[Auto GDrive]') == 0 && !cur) cur = t;
            rows += '<tr><td>' + t.name + '</td><td>' + ('0' + t.where_hour).slice(-2) + ':' + ('0' + t.where_minute).slice(-2)
                + '</td><td>' + t.save + '</td></tr>';
        }
        if (rows == '') rows = '<tr><td colspan="3" class="text-center c9">Belum ada backup ke Google Drive</td></tr>';

        var hour = cur ? cur.where_hour : 2;
        var minute = cur ? cur.where_minute : 30;
        var save = cur ? cur.save : 7;
        var dbNote = rdata.db_types.length ? '' : ' <span class="c9">(MySQL/MariaDB belum terpasang)</span>';

        var con = '<div class="pd20">'
            + '<p style="margin-bottom:10px">Setiap hari semua situs dan database dibackup lalu diunggah ke folder <b>backup/</b> di Google Drive. '
            + 'Tugasnya bisa dilihat dan diubah juga di menu <b>Cron</b>.</p>'
            + '<p style="margin-bottom:8px"><span style="display:inline-block;width:140px">Jam backup</span>'
            + '<input class="bt-input-text" type="number" min="0" max="23" name="gd_hour" value="' + hour + '" style="width:60px"> : '
            + '<input class="bt-input-text" type="number" min="0" max="59" name="gd_minute" value="' + minute + '" style="width:60px"></p>'
            + '<p style="margin-bottom:8px"><span style="display:inline-block;width:140px">Simpan backup</span>'
            + '<input class="bt-input-text" type="number" min="1" max="365" name="gd_save" value="' + save + '" style="width:60px"> terakhir (per situs / database)</p>'
            + '<p style="margin-bottom:4px"><span style="display:inline-block;width:140px">Yang dibackup</span>'
            + '<label style="font-weight:normal"><input type="checkbox" name="gd_sites" checked> Semua situs</label> &nbsp; '
            + '<label style="font-weight:normal"><input type="checkbox" name="gd_dbs" checked> Semua database</label>' + dbNote + '</p>'
            + '<table class="table table-bordered" style="margin-top:12px"><tr><th>Tugas ke Google Drive</th><th>Jam</th><th>Simpan</th></tr>' + rows + '</table>'
            + '</div>';

        var idx = layer.open({
            type: 1,
            title: 'Backup Otomatis ke Google Drive',
            area: '600px',
            closeBtn: 1,
            content: con,
            btn: ['Simpan', 'Jalankan Sekarang', 'Matikan'],
            yes: function () {
                gdPost('set_auto_backup', {
                    hour: $("input[name='gd_hour']").val(),
                    minute: $("input[name='gd_minute']").val(),
                    save: $("input[name='gd_save']").val(),
                    sites: $("input[name='gd_sites']").prop('checked'),
                    databases: $("input[name='gd_dbs']").prop('checked')
                }, function (data) {
                    var r = $.parseJSON(data.data);
                    layer.msg(r.msg, { icon: r.status ? 1 : 2, time: 6000 });
                    if (r.status) layer.close(idx);
                });
            },
            btn2: function () {
                gdPost('run_auto_backup', {}, function (data) {
                    var r = $.parseJSON(data.data);
                    layer.msg(r.msg, { icon: r.status ? 1 : 2, time: 5000 });
                });
                return false;
            },
            btn3: function () {
                gdPost('del_auto_backup', {}, function (data) {
                    var r = $.parseJSON(data.data);
                    layer.msg(r.msg, { icon: r.status ? 1 : 2 });
                });
            }
        });
    });
}
