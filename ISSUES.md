# Known Issues

Open items only.

Re-checked and re-cut 2026-09-26: entries were closed as they were fixed and the
rest were re-measured against the field Pi. Every open item says why it is still
open and what would close it.

*(Closed 2026-09-26: one stash left behind per update. The Pi held 79, the three
tracked build inputs — `db.sqlite3`, `media/`, the nine compiled `.mo` — are now
protected or untracked, and the count has stayed 0 across a full update since.
A stash reappearing means something the update generates is tracked again.)*

## Open — captive portal offline/setup branch has never run on hardware

The hotspot itself, NetworkManager shared-mode NAT, and the credential
handoff/revert in `wifi_worker.sh` have never been exercised on the Pi.
Bringing the hotspot up drops the only SSH link, so the branch must be tested
where a failure cannot strand the device.

**Decision 2026-09-26: on-site only, for now.** No Ethernet cable is
available. Two remote alternatives were considered and declined:

- **Ethernet shortcut.** Plug a cable into the Pi. `eth0` is free
  (`NO-CARRIER` on the field Pi 4), so SSH rides the wire while wlan0 runs the
  hotspot — the whole branch becomes testable remotely with no risk. Still the
  best option the moment a cable is at hand.
- **Virtual radio (`mac80211_hwsim`).** The module is present on the field Pi
  (`/lib/modules/6.18.39+rpt-rpi-v8/.../mac80211_hwsim.ko.xz`, not loaded), so
  two fake wifi radios could be created — build the AP on one, associate the
  other as a real client — without touching wlan0. It would genuinely cover AP
  creation, NM assigning 10.42.0.1, shared-mode nftables NAT, and a real client
  association. Declined for now because it cannot run the shipped scripts
  verbatim: `wlan0` is hardcoded throughout `startup_check.sh`, `portal.py` and
  `/etc/dnsmasq.conf`, with no interface override.

Run it on-site:

1. Put the Pi where its configured WiFi is unavailable (or disable the saved
   network), reboot, then on another device:
2. Join `Tinko-Setup` (pass `tinko1234`) → expect captive popup / page at
   `http://10.42.0.1`.
3. Enter real WiFi credentials → expect wait page, hotspot vanishes, Django
   appears on `http://tinko.local`.
4. Wrong password → expect hotspot + portal to come back in ~20s.
5. Watch `sudo journalctl -u tinko-wifi -f` and `/var/log/tinko_wifi.log`.

Already proven by the zero-risk `dummy0` test (method: see the
`captive-portal-test-method` memory): wildcard DNS answers, all six
captive-detection routes return `302 -> http://10.42.0.1/`, the form serves,
and the SSID/password validators reject bad input.

## Open — housekeeping: `origin/development` is still on GitHub

The local `development` branch is gone and work now happens on `master`
directly, so no pull request is needed for routine changes. The remote branch
could not be deleted from this machine — no GitHub credentials (`gh` is not
installed, and the HTTPS remote rejects password auth): `git push origin
--delete development` fails with *"Invalid username or token"*. Delete it in
the GitHub branches page, then `git fetch --prune` locally to drop the stale
`remotes/origin/development` ref.

## Known-inherent — single-radio wildcard DNS

`address=/#/10.42.0.1` breaks the Pi's own DNS while dnsmasq runs. Inherent to
a one-radio design; it cannot be removed, only contained. Contained by the
boot gate (the wildcard dnsmasq only starts when the Pi is genuinely offline)
and by stopping dnsmasq on handoff and on watchdog teardown. No action.