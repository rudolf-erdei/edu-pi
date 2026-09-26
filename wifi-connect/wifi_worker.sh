#!/bin/bash
#
# Tinko Wi-Fi handoff. Started by the Flask portal (portal.py) with the SSID and
# the password the teacher typed, and run as root.
#
# One job: leave the Pi on the network the teacher chose, or leave it exactly as
# it was.
#
# NetworkManager keeps one profile per network on disk and reconnects to them by
# itself from then on, so a network configured here is remembered and nobody
# types its password twice. Two things this worker has to get right for that to
# be true:
#
#   * A profile is not named after its SSID. A Pi imaged with Raspberry Pi
#     Imager or configured with netplan holds the profile as
#     "netplan-wlan0-<SSID>", so matching on the name failed to recognise the
#     network the Pi already knew and created a second profile for it — two
#     profiles for one network, each with its own password, and no way to tell
#     which one wins. Profiles are matched on the SSID they carry instead.
#
#   * A netplan-generated profile lives in /run and is rebuilt from
#     /etc/netplan/*.yaml at every boot. Changing its password through nmcli
#     appears to work, but only in memory: the next boot brings the yaml's
#     password back. An /etc keyfile cannot shadow it either (/run wins).
#     Verified on a Pi running Debian 13 with NetworkManager 1.52. So when a
#     password is changed on such a profile, the credential that just worked is
#     also copied into a profile of our own in /etc, which does survive.
#
# TINKO_DRY=1 reports what it would do and touches nothing, the way
# startup_check.sh can be run on a live Pi.
#
# Usage: wifi_worker.sh <SSID> <PASSWORD>

SSID="$1"
PASSWORD="$2"
LOG_FILE="/var/log/tinko_wifi.log"
HOTSPOT_SSID="Tinko-Setup"
DRY="${TINKO_DRY:-0}"

# The profile made when a netplan-managed profile's password has to be changed:
# a name of our own, in /etc, so it survives a reboot. The priority decides the
# next boot: both profiles autoconnect, and with equal priority NetworkManager
# breaks the tie on "used most recently", which a fresh clone inherits.
PERSISTENT_PROFILE="Tinko-WiFi-${SSID}"
PERSISTENT_PRIORITY=10

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [wifi_worker] $1" | tee -a "$LOG_FILE"
}

# --- profile helpers -------------------------------------------------------

profiles_for_ssid() {
    # Every profile that already carries this SSID, whatever it is called.
    local name
    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        [[ "$name" == "$HOTSPOT_SSID" ]] && continue
        if [[ "$(nmcli -g 802-11-wireless.ssid connection show "$name" 2>/dev/null)" == "$SSID" ]]; then
            printf '%s\n' "$name"
        fi
    done < <(nmcli -t --escape no -f NAME connection show 2>/dev/null)
}

profile_is_persistent() {
    # /etc is on disk and survives a reboot; netplan rebuilds its own into /run.
    #
    # The keyfile path is a display field, not a gettable one: `-f FILENAME`
    # only works in the list form, and asking for it per-profile fails. The
    # list is matched on the UUID, which never contains a colon, so the line
    # splits cleanly whatever the profile is called.
    local uuid filename
    uuid="$(nmcli -g connection.uuid connection show "$1" 2>/dev/null)"
    [[ -z "$uuid" ]] && return 1

    filename="$(nmcli -t --escape no -f UUID,FILENAME connection show 2>/dev/null \
        | grep "^${uuid}:" | cut -d: -f2-)"
    [[ "$filename" == /etc/* ]]
}

stored_psk() {
    nmcli -s -g 802-11-wireless-security.psk connection show "$1" 2>/dev/null
}

keep_the_password() {
    # A netplan-managed profile forgets an nmcli password change at the next
    # boot, so the credential that just worked is written into a profile of our
    # own in /etc. It is left inactive on purpose: the connection is already up
    # and does not need bouncing, and from the next boot this profile wins.
    local source="$1"

    if nmcli -t --escape no -f NAME connection show 2>/dev/null | grep -Fxq "$PERSISTENT_PROFILE"; then
        if nmcli connection modify "$PERSISTENT_PROFILE" \
            wifi-sec.psk "$PASSWORD" \
            connection.autoconnect yes \
            connection.autoconnect-priority "$PERSISTENT_PRIORITY" >/dev/null 2>&1; then
            log "Updated the profile we keep for '$SSID' with the password that worked"
        else
            log "WARNING: could not update '$PERSISTENT_PROFILE'"
        fi
        return
    fi

    if nmcli connection clone "$source" "$PERSISTENT_PROFILE" >/dev/null 2>&1; then
        nmcli connection modify "$PERSISTENT_PROFILE" \
            wifi-sec.psk "$PASSWORD" \
            connection.autoconnect yes \
            connection.autoconnect-priority "$PERSISTENT_PRIORITY" >/dev/null 2>&1
        log "'$source' is not kept across reboots; saved the working password as '$PERSISTENT_PROFILE'"
    else
        log "WARNING: could not keep the password for '$SSID' — '$source' is not saved on disk, so it will be lost at the next reboot"
    fi
}

# --- hotspot ---------------------------------------------------------------

hotspot_down() { nmcli connection down "$HOTSPOT_SSID" 2>/dev/null || true; }

restore_hotspot() {
    if nmcli connection up "$HOTSPOT_SSID" 2>/dev/null; then
        log "Hotspot '${HOTSPOT_SSID}' restored"
    else
        log "ERROR: could not restore hotspot '${HOTSPOT_SSID}'"
    fi

    # Without this, DNS redirection may not work after the radio switch
    # (AP -> station -> AP).
    if systemctl restart dnsmasq 2>/dev/null; then
        log "dnsmasq restarted after hotspot restore"
    else
        log "WARNING: dnsmasq restart failed after hotspot restore"
        log "DNS redirection may be unavailable until the portal restarts"
    fi
}

stop_portal() {
    if [[ -f /run/tinko-portal.pid ]]; then
        local portal_pid
        portal_pid=$(cat /run/tinko-portal.pid)
        if kill -0 "$portal_pid" 2>/dev/null; then
            kill "$portal_pid"
            log "Flask portal (PID $portal_pid) stopped"
        else
            log "Flask portal PID $portal_pid no longer running"
        fi
        rm -f /run/tinko-portal.pid
    else
        log "No PID file found, falling back to pkill"
        pkill -f "python3.*portal.py"
        log "Flask portal stopped via pkill"
    fi
}

# --- main ------------------------------------------------------------------

log "=== WiFi handoff starting for SSID: '$SSID' ==="

# Give the Flask web server 3 seconds to send the HTML "Wait Page" to the
# teacher's phone before the hotspot disappears from under it.
sleep 3

if [[ "$SSID" == "$HOTSPOT_SSID" ]]; then
    log "Refusing to connect to '$SSID': that is this Pi's own hotspot, not a network to join"
    exit 1
fi

mapfile -t known < <(profiles_for_ssid)
PROFILE="${known[0]:-}"

if [[ -n "$PROFILE" ]]; then
    log "'$SSID' is already a known network: profile '$PROFILE' (${#known[@]} profile(s) for it)"
    if profile_is_persistent "$PROFILE"; then
        log "  ...it is stored on disk, so the Pi keeps it across reboots"
    else
        log "  ...it is rebuilt by netplan at every boot"
    fi
else
    log "'$SSID' is not a known network yet; a new profile will be created for it"
fi

if [[ "$DRY" == "1" ]]; then
    log "[dry] would connect to '$SSID' by reusing '${PROFILE:-<new profile>}'"
    log "[dry] nothing changed"
    exit 0
fi

# A single WiFi radio cannot be in AP mode and station mode at the same time.
hotspot_down
sleep 1

CONNECTED=0

if [[ -z "$PROFILE" ]]; then
    # A network the Pi has never seen: this writes a profile of its own, on
    # disk, and connects in one step.
    if nmcli --wait 15 dev wifi connect "$SSID" password "$PASSWORD"; then
        CONNECTED=1
        PROFILE="$(profiles_for_ssid | head -n 1)"
        log "Connected to '$SSID' (new profile '${PROFILE:-unknown}')"
    fi
else
    # A network the Pi already knows: try the password stored for it first, so
    # that picking a network it can already reach changes nothing.
    log "Trying '$PROFILE' with the password the Pi already has for '$SSID'"

    if nmcli --wait 15 connection up "$PROFILE"; then
        CONNECTED=1
        log "Connected to '$SSID' using the saved profile '$PROFILE'"
    else
        log "The saved password for '$SSID' did not work; applying the one just typed"
        PREVIOUS_PSK="$(stored_psk "$PROFILE")"

        if ! nmcli connection modify "$PROFILE" wifi-sec.psk "$PASSWORD" >/dev/null 2>&1; then
            log "ERROR: could not write the password to '$PROFILE'"
        elif nmcli --wait 15 connection up "$PROFILE"; then
            CONNECTED=1
            log "Connected to '$SSID' with the password just typed"
            profile_is_persistent "$PROFILE" || keep_the_password "$PROFILE"
        else
            # A mistyped password must not cost the Pi a network it could reach
            # before this attempt.
            if [[ -n "$PREVIOUS_PSK" ]]; then
                nmcli connection modify "$PROFILE" wifi-sec.psk "$PREVIOUS_PSK" >/dev/null 2>&1 \
                    && log "Restored the previous password on '$PROFILE'"
            else
                log "No previous password stored on '$PROFILE' to put back"
            fi
            log "Connection to '$SSID' failed with the password just typed"
        fi
    fi
fi

if [[ "$CONNECTED" -eq 1 ]]; then
    # The Pi is now on the network the teacher chose.
    stop_portal

    # dnsmasq is only needed in hotspot mode for DNS redirection. Its wildcard
    # DNS (address=/#/10.42.0.1) would break internet access if left running
    # while connected to real WiFi.
    if systemctl stop dnsmasq 2>/dev/null; then
        log "dnsmasq stopped (no longer needed with WiFi internet)"
    else
        log "WARNING: dnsmasq stop returned nonzero (may already be stopped)"
    fi

    # "It says it is connected but nothing loads" is the classic field
    # complaint, and this distinguishes the two causes in one line. A network
    # with its own sign-in page looks exactly like this.
    if curl -s --connect-timeout 3 --max-time 4 -o /dev/null "https://github.com"; then
        log "Internet reachable on '$SSID'"
    else
        log "NOTE: '$SSID' is connected but the internet probe failed — a network that needs its own sign-in page looks like this"
    fi

    # Wait for tinko-wifi.service to finish so systemd naturally starts tinko
    # via the Before=tinko.service ordering (avoids double-start)
    log "WiFi setup complete. Django will start via systemd ordering."
else
    log "Connection to '$SSID' failed (wrong password or out of range). Reverting to hotspot..."
    restore_hotspot
fi
