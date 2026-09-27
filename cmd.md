### Description of common commands


- Panel related commands

```
/etc/init.d/mit default

service mit [start|stop|reload|restart|status]
```

- Nginx (OpenResty)

```

systemctl [start|stop|reload|restart|status] openresty

```

- Apache

```

systemctl [start|stop|reload|restart|status] apache

/opt/mit/server/apache/bin/apachectl -t        # test configuration

```

- MySQL

```

systemctl [start|stop|reload|restart|status] mysql

```

- PHP

```

systemctl [start|stop|reload|restart|status] php[56-85]

systemctl start php71
```

- Watchdog

```

tail -f /opt/mit/server/panel/logs/watchdog.log

touch /opt/mit/server/panel/data/watchdog_off.pl     # disable
rm /opt/mit/server/panel/data/watchdog_off.pl        # enable

```
