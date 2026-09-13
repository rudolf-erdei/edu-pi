#!/bin/bash
#
# Tinko Wi-Fi captive portal startup check.
# Runs once at boot (tinko-wifi.service, as root).
#
# Flow:
#   1. Decide whether the Pi is really online, robustly:
#      wait for NetworkManager, then retried HTTPS probe (never ICMP), and
#      respect "wlan0 is already on a real network". We never tear down a
#      live connection just because one probe failed.
#   2. Online  -> exit 0, Django boots normally.
#   3. Offline -> bring up the 'Tinko-Setup' hotspot, dnsmasq wildcard DNS
#      and the Flask portal. Every step is verified and retried; failures
#      are reported loudly instead of failing silently.
#   4. Watchdog tears setup mode down after PORTAL_TIMEOUT seconds so the Pi
#      can never be wedged in setup mode forever. dnsmasq is cleaned up too.

LOG_FILE="/var/log/tinko_wifi.log"

HOTSPOT_SSID="Tinko-Setup"
HOTSPOT_PASSWORD="tinko1234"
HOTSPOT_IP="10.42.0.1"

INTERNET_URL="https://github.com"
CURL_TIMEOUT=4
INTERNET_RETRIES=6
INTERNET_RETRY_SLEEP=7
NM_ONLINE_TIMEOUT=45

HOTSPOT_WAIT=20        # seconds to wait for the hotspot to come up
DNSMASQ_WAIT=12        # seconds to wait for dnsmasq to bind :53
PORTAL_WAIT=8          # seconds to wait for Flask to answer on :80

PORTAL_TIMEOUT=600     # seconds before the watchdog tears setup mode down
WATCHDOG_INTERVAL=30

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [startup_check] $1" | tee -a "$LOG_FILE"; }

# --- decision helpers ------------------------------------------------------

nm_online() {
    # Warm-up wait so we don't probe while NM is still starting.
    if command -v nm-online >/dev/null 2>&1; then
        nm-online -s -q --timeout="${NM_ONLINE_TIMEOUT}" >/dev/null 2>&1
    fi
    return 0
}

internet_is_up() {
    # Retried HTTPS probe. curl, not ping: ICMP is frequently blocked on
    # school networks, which made the old single-ping gate a permanent
    # false negative on perfectly-good connections.
    local i
    for i in $(seq "${INTERNET_RETRIES}"); do
        if curl -s --connect-timeout 3 --max-time "${CURL_TIMEOUT}" -o /dev/null "${INTERNET_URL}"; then
            return 0
        fi
        sleep "${INTERNET_RETRY_SLEEP}"
    done
    return 1
}

wlan0_info() {
    # Prints "STATE<CONNECTION" e.g. "connected<Tinko-Setup".
    nmcli -g GENERAL.STATE,GENERAL.CONNECTION device show wlan0 2>/dev/null | tr '\n' '\t'
}

wlan0_has_realtime_connection() {
    # True when wlan0 is associated to a real network (not our hotspot).
    local info
    info=$(wlan0_info)
    [[ "$info" == connected* && "$info" != *"${HOTSPOT_SSID}"* ]]
}

hotspot_is_up() {
    local state conn ip
    state=$(nmcli -g GENERAL.STATE device show wlan0 2>/dev/null)
    conn=$(nmcli -g GENERAL.CONNECTION device show wlan0 2>/dev/null)
    ip=$(nmcli -g IP4.ADDRESS device show wlan0 2>/dev/null)
    [[ "$state" == connected* && "$conn" == "${HOTSPOT_SSID}" && "$ip" == "${HOTSPOT_IP}/"* ]]
}

wait_for_hotspot() {
    local i
    for i in $(seq "${HOTSPOT_WAIT}"); do
        hotspot_is_up && return 0
        sleep 1
    done
    return 1
}

# --- setup-mode steps ------------------------------------------------------

ensure_system_configs() {
    # Idempotent: the pieces that stop NM's own dnsmasq taking :53 and stop
    # the Pi's resolver pointing at a local listener. Written at install and
    # re-verified here so runtime state matches (issue: configs applied once,
    # never checked again).
    if [[ ! -f /etc/NetworkManager/conf.d/dns-upstream.conf ]]; then
        sudo mkdir -p /etc/NetworkManager/conf.d
        sudo tee /etc/NetworkManager/conf.d/dns-upstream.conf >/dev/null <<'EOF'
[global-dns-domain-*]
servers=8.8.8.8,8.8.4.4
EOF
    fi
    if [[ ! -f /etc/NetworkManager/conf.d/no-connectivity-check.conf ]]; then
        sudo mkdir -p /etc/NetworkManager/conf.d
        sudo tee /etc/NetworkManager/conf.d/no-connectivity-check.conf >/dev/null <<'EOF'
[connectivity]
interval=0
EOF
    fi
    if [[ ! -f /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf ]]; then
        sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d
        echo "port=0" | sudo tee /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf >/dev/null
    fi
    if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
        if [[ ! -f /etc/systemd/resolved.conf.d/no-stub.conf ]]; then
            sudo mkdir -p /etc/systemd/resolved.conf.d
            sudo tee /etc/systemd/resolved.conf.d/no-stub.conf >/dev/null <<'EOF'
[Resolve]
DNSStubListener=no
EOF
            sudo systemctl restart systemd-resolved 2>/dev/null || true
        fi
    fi
    # Make NM re-read conf.d (affects how it spawns its internal dnsmasq).
    nmcli general reload 2>/dev/null || true
}

start_hotspot() {
    if nmcli -t connection show 2>/dev/null | grep -q "${HOTSPOT_SSID}"; then
        log "Hotspot profile exists, activating..."
        nmcli connection up "${HOTSPOT_SSID}"
    else
        log "Creating hotspot '${HOTSPOT_SSID}' for the first time..."
        nmcli dev wifi hotspot ifname wlan0 ssid "${HOTSPOT_SSID}" \
            password "${HOTSPOT_PASSWORD}" con-name "${HOTSPOT_SSID}"
    fi

    # Disable IPv6 on the hotspot to prevent connection cycling.
    nmcli connection modify "${HOTSPOT_SSID}" ipv6.method disabled 2>/dev/null || true

    if wait_for_hotspot; then
        log "Hotspot active on ${HOTSPOT_IP}"
        return 0
    fi
    log "ERROR: hotspot did not come up on wlan0 within ${HOTSPOT_WAIT}s"
    nmcli connection show "${HOTSPOT_SSID}" 2>/dev/null | grep -E 'connection.state|IP4.ADDRESS' || true
    return 1
}

start_dnsmasq() {
    # Stop any previous instance so it can't hold :53 with a stale binding.
    systemctl stop dnsmasq 2>/dev/null || true
    sleep 1

    if ! systemctl start dnsmasq; then
        log "ERROR: dnsmasq failed to start"
        return 1
    fi

    # Verify it is actually bound to the hotspot IP on :53 and answering.
    # (bind-interfaces requires the interface + address to exist first; we
    # have already verified the hotspot is up, so this races only with IP
    # propagation.)
    local i
    for i in $(seq "${DNSMASQ_WAIT}"); do
        if ! ss -ulnp 2>/dev/null | grep -q "${HOTSPOT_IP}:53"; then
            sleep 1
            continue
        fi
        if command -v dig >/dev/null 2>&1; then
            if dig +time=1 +tries=1 "@${HOTSPOT_IP}" "${HOTSPOT_SSID}" +short 2>/dev/null | grep -q "${HOTSPOT_IP}"; then
                log "dnsmasq bound to ${HOTSPOT_IP}:53 and answering"
                return 0
            fi
        elif command -v nslookup >/dev/null 2>&1; then
            if nslookup -timeout=1 -retry=0 "${HOTSPOT_SSID}" "${HOTSPOT_IP}" 2>/dev/null | grep -q "${HOTSPOT_IP}"; then
                log "dnsmasq bound to ${HOTSPOT_IP}:53 and answering"
                return 0
            fi
        else
            # No resolver tooling installed — socket-bound check is enough.
            log "dnsmasq bound to ${HOTSPOT_IP}:53"
            return 0
        fi
        sleep 1
    done
    log "ERROR: dnsmasq not answering on ${HOTSPOT_IP}:53 after ${DNSMASQ_WAIT}s"
    return 1
}

start_portal() {
    # Port 80 must be free (a stale daphne would make Flask die instantly).
    if ss -tlnp 2>/dev/null | grep -q ':80 '; then
        log "ERROR: port 80 already in use:"
        ss -tlnp 2>/dev/null | grep ':80 ' || true
        return 1
    fi

    rm -f /run/tinko-portal.pid
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    HOTSPOT_SSID="${HOTSPOT_SSID}" HOTSPOT_PASSWORD="${HOTSPOT_PASSWORD}" \
        python3 "${SCRIPT_DIR}/portal.py" &
    local PORTAL_PID=$!
    echo "$PORTAL_PID" > /run/tinko-portal.pid

    local i
    for i in $(seq "${PORTAL_WAIT}"); do
        if curl -s -o /dev/null --max-time 2 "http://127.0.0.1/"; then
            log "Flask portal responding on port 80 (PID $PORTAL_PID)"
            return 0
        fi
        if ! kill -0 "$PORTAL_PID" 2>/dev/null; then
            break
        fi
        sleep 1
    done
    log "ERROR: Flask portal did not answer on port 80"
    kill "$PORTAL_PID" 2>/dev/null || true
    rm -f /run/tinko-portal.pid
    return 1
}

run_setup_mode() {
    log "Entering setup mode (hotspot + captive portal)"
    ensure_system_configs
    start_hotspot || return 1
    start_dnsmasq || log "WARNING: continuing without DNS redirection (manual http://10.42.0.1 still works)"
    start_portal || return 1

    local PORTAL_PID
    PORTAL_PID=$(cat /run/tinko-portal.pid 2>/dev/null || echo "")

    local ELAPSED=0
    while [[ -n "$PORTAL_PID" ]] && kill -0 "$PORTAL_PID" 2>/dev/null; do
        if (( ELAPSED >= PORTAL_TIMEOUT )); then
            log "Watchdog: setup mode has run for ${PORTAL_TIMEOUT}s. Tearing it down."
            kill "$PORTAL_PID" 2>/dev/null
            rm -f /run/tinko-portal.pid
            systemctl stop dnsmasq 2>/dev/null || true
            # Free the radio so NM can reconnect any saved network.
            nmcli connection down "${HOTSPOT_SSID}" 2>/dev/null || true
            log "Setup mode torn down. Django will start on port 80."
            return 0
        fi
        sleep "${WATCHDOG_INTERVAL}"
        ELAPSED=$((ELAPSED + WATCHDOG_INTERVAL))
    done

    # Portal exited by itself = successful WiFi handoff (wifi_worker killed it).
    log "Flask portal exited after ${ELAPSED}s — WiFi likely configured"
    rm -f /run/tinko-portal.pid
    # Belt & braces: the wildcard dnsmasq must not survive a successful handoff.
    if ! wlan0_has_realtime_connection; then
        log "No real connection on wlan0 — stopping dnsmasq"
        systemctl stop dnsmasq 2>/dev/null || true
    fi
    return 0
}

# --- main ------------------------------------------------------------------

main() {
    log "=== Startup check beginning ==="

    if [[ "${TINKO_DRY}" == "1" ]]; then
        # Dry run: decide but change nothing. For testing on a live system.
        nm_online
        if internet_is_up; then
            log "[dry] internet verified -> normal boot"
        elif wlan0_has_realtime_connection; then
            log "[dry] wlan0 on real network but probe failed -> normal boot (no teardown)"
        else
            log "[dry] offline -> would enter setup mode"
        fi
        exit 0
    fi

    nm_online

    if internet_is_up; then
        log "Internet verified. Booting Django server..."
        exit 0
    fi

    if wlan0_has_realtime_connection; then
        # Interface is up on a real network, but our probe failed. Tearing
        # this down is exactly the false-positive that broke field Pis.
        log "wlan0 is connected to a real network but the internet probe failed."
        log "NOT entering setup mode (would break the existing connection)."
        exit 0
    fi

    run_setup_mode
    exit $?
}

main "$@"
