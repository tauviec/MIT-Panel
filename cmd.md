### Description of common commands


- Panel related commands

```
/etc/init.d/mit default

service mit [start|stop|reload|restart|status]
```

- Forgot login info (URL, username, password)

```

mit default         # show panel URL, username and default password
mit 11              # set a new panel password
mit 12              # change panel username
mit 5               # change panel port
mit                 # menu with all panel tools

```

`mit default` can only show the default password; once it has been changed it
prints `Password has been changed!`, so use `mit 11` to set a new one.
The URL must include the security path at the end (e.g. `/soimk7ho`).

- Windows (WSL2): run the same commands from PowerShell or CMD

```

wsl -d Ubuntu -u root -- mit default
wsl -d Ubuntu -u root -- mit 11
wsl -d Ubuntu -u root -- mit restart

```

Open the panel from Windows with the `MIT-Panel-Url-Localhost` address
(`http://localhost:<port>/<path>`).

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
