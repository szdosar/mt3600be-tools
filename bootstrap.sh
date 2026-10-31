#!/bin/sh
# Verified launcher for online-v1.3; never execute a fixed old download path.
set -eu
umask 077
t=$(mktemp /tmp/mt3600be-launch.XXXXXXXX) || exit 1
trap 'rm -f -- "$t"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap '' HUP
curl -q --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 120 --max-filesize 1048576 --output "$t" https://github.com/szdosar/mt3600be-tools/releases/download/online-v1.3/install.sh
[ -s "$t" ]
printf '%s  %s\n' '1bf93767c99771a5b34c74d6c7c3ae90706927250386fc955008222e2e4221c8' "$t" | sha256sum -c -
sh -n "$t"
sh "$t" "$@"
