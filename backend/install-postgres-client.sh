#!/bin/sh
set -eu
apt-get update
apt-get install -y --no-install-recommends curl ca-certificates gpg
install -d /usr/share/postgresql-common/pgdg
curl --fail --silent --show-error https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
task_pg_fingerprint=$(gpg --show-keys --with-colons /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc 2>/dev/null | awk -F: '/^fpr:/ {print $10; exit}')
[ "$task_pg_fingerprint" = B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8 ]
. /etc/os-release
printf 'Types: deb\nURIs: https://apt.postgresql.org/pub/repos/apt\nSuites: %s-pgdg\nComponents: main\nSigned-By: /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc\n' "$VERSION_CODENAME" > /etc/apt/sources.list.d/pgdg.sources
apt-get update
apt-get install -y --no-install-recommends postgresql-client-16
rm -rf /var/lib/apt/lists/*
