#!/bin/sh
# Verified launcher for online-v1.2.1; never execute a fixed old download path.
set -eu
umask 077
t=$(mktemp /tmp/mt3600be-launch.XXXXXXXX) || exit 1
trap 'rm -f -- "$t"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap '' HUP
curl -q --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 120 --max-filesize 1048576 --output "$t" https://github.com/szdosar/mt3600be-tools/releases/download/online-v1.2.1/install.sh
[ -s "$t" ]
printf '%s  %s\n' 'eca4a13e7cf30cdfec72e1ae39c53a2429310963864c5d8dc5d8a37f35d74514' "$t" | sha256sum -c -
sh -n "$t"
sh "$t" "$@"
