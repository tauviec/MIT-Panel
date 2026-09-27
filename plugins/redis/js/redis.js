var redis = {

    // args travel as base64(JSON): the panel passes them to index.py unquoted
    post: function (method, args, callback) {
        var loadT = layer.msg('Lagi ambil data...', { icon: 16, time: 0, shade: 0.3 });
        var req_data = { name: 'redis', func: method };
        if (args) {
            req_data['args'] = btoa(unescape(encodeURIComponent(JSON.stringify(args))));
        }
        $.post('/plugins/run', req_data, function (data) {
            layer.close(loadT);
            if (!data.status) {
                layer.msg(data.msg, { icon: 0, time: 3000, shade: [0.3, '#000'] });
                return;
            }
            var rdata;
            try {
                rdata = $.parseJSON(data.data);
            } catch (err) {
                layer.msg(data.data, { icon: 2, time: 3000 });
                return;
            }
            callback(rdata);
        }, 'json');
    },

    esc: function (s) {
        return String(s === undefined ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },

    connInfo: function () {
        redis.post('conn_info', null, function (rdata) {
            var d = rdata.data;
            var e = redis.esc;
            var pass = d.password ? e(d.password) : '<span style="color:red">(tanpa password)</span>';
            var auth = d.password ? " -a '" + e(d.password) + "'" : '';
            var con = "<table class='table table-hover table-bordered'>\
                <tr><th style='width:130px'>Versi</th><td>" + e(d.version) + "</td></tr>\
                <tr><th>Host</th><td>" + e(d.host) + "</td></tr>\
                <tr><th>Port</th><td>" + e(d.port) + "</td></tr>\
                <tr><th>Password</th><td>" + pass + "</td></tr>\
                <tr><th>Bind</th><td>" + e(d.bind) + "</td></tr>\
            </table>\
            <ul class='help-info-text c7'>\
                <li>Laravel (.env): <code>REDIS_HOST=127.0.0.1</code> <code>REDIS_PORT=" + e(d.port) + "</code> <code>REDIS_PASSWORD=" + e(d.password) + "</code></li>\
                <li>PHP butuh ekstensi <b>redis</b>: Aplikasi &rarr; PHP &rarr; Atur &rarr; Ekstensi &rarr; pasang <b>redis</b>.</li>\
                <li>Terminal: <code>" + e(d.cli) + " -p " + e(d.port) + auth + "</code></li>\
                <li>Password dan port bisa diganti di menu <b>Pengaturan</b>.</li>\
            </ul>\
            <div style='margin-top:10px'><button class='btn btn-danger btn-sm' onclick='redis.flushAll()'>Kosongkan semua data (FLUSHALL)</button></div>";
            $('.soft-man-con').html(con);
        });
    },

    flushAll: function () {
        layer.confirm('Semua key di semua database Redis akan dihapus permanen. Lanjutkan?', { icon: 3, closeBtn: 1 }, function () {
            redis.post('flush_all', null, function (rdata) {
                layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
            });
        });
    },

    runInfo: function () {
        redis.post('run_info', null, function (rdata) {
            if (!rdata.status) {
                layer.msg(rdata.msg, { icon: 2, time: 3000 });
                return;
            }
            var d = rdata.data;
            var e = redis.esc;
            var rows = [
                ['Versi', d.redis_version, 'Versi Redis'],
                ['Uptime', d.uptime_in_days + ' hari', 'Lama berjalan sejak start terakhir'],
                ['Port', d.tcp_port, 'Port yang dipakai'],
                ['Klien terhubung', d.connected_clients, 'Jumlah koneksi aktif'],
                ['Memori terpakai', d.used_memory_human, 'Memori yang dipakai data'],
                ['Memori puncak', d.used_memory_peak_human, 'Pemakaian memori tertinggi'],
                ['Batas memori', d.maxmemory_human === '0B' ? 'tanpa batas' : d.maxmemory_human, 'maxmemory'],
                ['Jumlah key', d.total_keys, 'Total key di semua database'],
                ['Hit rate', d.hit_rate, 'Persentase key yang ditemukan saat dibaca'],
                ['Perintah diproses', d.total_commands_processed, 'Sejak start terakhir'],
                ['Operasi/detik', d.instantaneous_ops_per_sec, 'Saat ini'],
                ['Simpan RDB terakhir', d.rdb_last_bgsave_status, 'Status snapshot terakhir'],
                ['AOF', d.aof_enabled === '1' ? 'aktif' : 'mati', 'appendonly'],
            ];
            var con = "<table class='table table-hover table-bordered'><thead><tr><th>Item</th><th>Nilai</th><th>Keterangan</th></tr></thead><tbody>";
            for (var i = 0; i < rows.length; i++) {
                con += '<tr><th>' + rows[i][0] + '</th><td>' + e(rows[i][1]) + '</td><td>' + rows[i][2] + '</td></tr>';
            }
            con += '</tbody></table>';
            $('.soft-man-con').html(con);
        });
    },

    settings: function () {
        redis.post('get_redis_conf', null, function (rdata) {
            var d = rdata.data;
            var e = redis.esc;
            var policies = '';
            for (var i = 0; i < d.memory_policies.length; i++) {
                var p = d.memory_policies[i];
                policies += '<option value="' + p + '"' + (p == d['maxmemory-policy'] ? ' selected' : '') + '>' + p + '</option>';
            }
            var field = function (label, name, value, width, tip) {
                return '<p><span style="display:inline-block;width:130px">' + label + '</span>' +
                    '<input class="bt-input-text mr5" name="' + name + '" value="' + e(value) + '" style="width:' + width + 'px" type="text"> ' +
                    '<font style="color:#999">' + tip + '</font></p>';
            };
            var con = '<div class="conf_p redis-conf" style="margin-bottom:0">' +
                field('bind', 'bind', d.bind, 180, '127.0.0.1 = hanya lokal, 0.0.0.0 = semua alamat') +
                field('port', 'port', d.port, 100, 'Port Redis') +
                field('requirepass', 'requirepass', d.requirepass, 180, 'Password koneksi') +
                field('timeout', 'timeout', d.timeout, 100, 'Detik, 0 = tidak pernah putus') +
                field('databases', 'databases', d.databases, 100, 'Jumlah database') +
                field('maxclients', 'maxclients', d.maxclients, 100, 'Maksimal koneksi') +
                field('maxmemory', 'maxmemory', d.maxmemory, 100, 'MB, 0 = tanpa batas') +
                '<p><span style="display:inline-block;width:130px">maxmemory-policy</span>' +
                '<select class="bt-input-text mr5" name="maxmemory-policy" style="width:180px">' + policies + '</select> ' +
                '<font style="color:#999">Saat memori penuh</font></p>' +
                '<p><span style="display:inline-block;width:130px">appendonly</span>' +
                '<select class="bt-input-text mr5" name="appendonly" style="width:100px">' +
                '<option value="no"' + (d.appendonly == 'no' ? ' selected' : '') + '>no</option>' +
                '<option value="yes"' + (d.appendonly == 'yes' ? ' selected' : '') + '>yes</option>' +
                '</select> <font style="color:#999">Simpan tiap perubahan ke disk (AOF)</font></p>' +
                '<div style="margin-top:10px;padding-right:15px" class="text-right">' +
                '<button class="btn btn-success btn-sm" onclick="redis.saveSettings()">Simpan</button></div>' +
                '</div>' +
                '<ul class="help-info-text c7"><li>Menyimpan akan me-restart Redis.</li>' +
                '<li>Kalau bind dibuka ke luar (0.0.0.0), password wajib diisi dan buka port-nya di menu Keamanan.</li></ul>';
            $('.soft-man-con').html(con);
        });
    },

    saveSettings: function () {
        var args = {};
        $('.redis-conf input, .redis-conf select').each(function () {
            args[$(this).attr('name')] = $(this).val();
        });
        redis.post('submit_redis_conf', args, function (rdata) {
            layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2, time: 3000 });
        });
    }
};
