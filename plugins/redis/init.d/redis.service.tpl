[Unit]
Description=Redis In-Memory Data Store (MIT Panel)
After=network.target

[Service]
Type=simple
User=redis
Group=redis
ExecStart={$SERVER_PATH}/redis/bin/redis-server {$SERVER_PATH}/redis/redis.conf --daemonize no
ExecStop=/bin/kill -s TERM $MAINPID
Restart=on-failure
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
