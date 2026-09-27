[Unit]
Description=Apache HTTP Server
After=network.target remote-fs.target nss-lookup.target

[Service]
Type=forking
PIDFile={$SERVER_PATH}/apache/logs/httpd.pid
ExecStart={$SERVER_PATH}/apache/bin/apachectl -k start
ExecReload={$SERVER_PATH}/apache/bin/apachectl -k graceful
ExecStop={$SERVER_PATH}/apache/bin/apachectl -k stop
KillMode=mixed
PrivateTmp=false
Restart=on-failure

[Install]
WantedBy=multi-user.target
