#!/bin/bash
# Drive AmneziaVPN fork builds from adb, without taps (A12). Two builds carry the control:
#   org.amnezia.vpn.strict  test release (feat, AdbControl.kt, extra adb_ctl, tag AmneziaAdbCtl)
#   org.amnezia.vpn.exp     experimental build (local exp/lab, ExpControl.kt, extra exp_ctl,
#                           tag AmneziaExpCtl) — also a live filter switch and counters
#
#   tools/awgctl.sh "cmd=status"
#   tools/awgctl.sh "cmd=reconnect mode=include add=com.termux strict=1"
#   AWG_PKG=org.amnezia.vpn.exp tools/awgctl.sh "cmd=connect"
#   AWG_PKG=org.amnezia.vpn.exp tools/awgctl.sh strict 0|1   # exp only: remove/restore the
#                                                          # filter in the running tunnel
#
# Command words, space-separated, at most 91 bytes (a property value):
#   cmd=connect|disconnect|reconnect|status   connect does nothing while connected;
#                                             reconnect applies changes to a live tunnel
#   mode=off|include|exclude   apps=a,b  add=a,b  del=a,b   strict=0|1
# Changes apply to the config the service saved last and are saved on connect; the app's own
# settings screen does not see them. The screen must be on (am start brings the app up).
# Set ANDROID_SERIAL when adb lists the phone twice (IP:port and mDNS name).
set -u
PKG=${AWG_PKG:-org.amnezia.vpn.strict}
case "$PKG" in
    *.exp) EXTRA=exp_ctl; TAG=AmneziaExpCtl ;;
    *) EXTRA=adb_ctl; TAG=AmneziaAdbCtl ;;
esac
if [ "$1" = strict ]; then
    adb shell setprop debug.awg.strict "$2"
    sleep 2
    adb logcat -d -s 'AmneziaWG/uidfilter:*' | grep -E "strict (suspended|restored)" | tail -1
    exit 0
fi
adb logcat -c
adb shell setprop debug.awg.ctl "'$1'"
adb shell am start -n "$PKG/org.amnezia.vpn.AmneziaActivity" --ez "$EXTRA" true >/dev/null
case "$1" in *connect*) sleep 8 ;; *) sleep 3 ;; esac
adb logcat -d -s "$TAG:*" | grep -v "^---------"
adb shell 'ip -o -4 addr show 2>/dev/null | grep tun || echo "no tun"'
