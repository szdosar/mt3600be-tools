#!/bin/sh
# Verified launcher for online-v1.4; never execute a fixed old download path.
set -eu
umask 077
t=$(mktemp /tmp/mt3600be-launch.XXXXXXXX) || exit 1
trap 'rm -f -- "$t"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap '' HUP
curl -q --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 120 --max-filesize 1048576 --output "$t" https://github.com/szdosar/mt3600be-tools/releases/download/online-v1.4/install.sh
[ -s "$t" ]
printf '%s  %s\n' '658bf8496b2d74526cd36799712dbcd48059ce89c71cf873ad6293647beeeb7f' "$t" | sha256sum -c -
sh -n "$t"
sh "$t" "$@"
