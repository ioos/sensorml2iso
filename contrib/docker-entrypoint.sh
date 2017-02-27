#!/bin/bash

set -eu

for init in $(ls /etc/my_init.d); do
    /etc/my_init.d/${init}
done


if [[ $# -eq 0 ]]; then
    rsyslogd
    cron
    exec tail -f /var/log/syslog
fi

exec /sbin/setuser app sensorml2iso "$@"
