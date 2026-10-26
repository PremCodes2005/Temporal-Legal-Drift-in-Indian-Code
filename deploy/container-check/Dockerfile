FROM debian:12-slim
RUN apt-get update && apt-get install -y --no-install-recommends systemd systemd-sysv python3 python3-venv curl ca-certificates bsdutils && rm -rf /var/lib/apt/lists/*
RUN useradd --system --create-home tldrift
COPY app /srv/temporal-legal-drift
WORKDIR /srv/temporal-legal-drift
RUN python3 -m venv .venv && .venv/bin/pip install --quiet -e . "pypdf==6.16.2" && .venv/bin/tldrift restore-release-inputs >/dev/null && chown -R tldrift:tldrift /srv/temporal-legal-drift
RUN mkdir -p /etc/tldrift && printf 'TLDRIFT_ALERT_COMMAND="tee -a /srv/temporal-legal-drift/data/tldrift-alerts.log"\nTLDRIFT_HEARTBEAT_URL=\n' > /etc/tldrift/tldrift.env \
 && chmod 0640 /etc/tldrift/tldrift.env && chgrp tldrift /etc/tldrift/tldrift.env \
 && cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/ \
 && systemctl enable tldrift-monitor.timer tldrift-health.timer
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
