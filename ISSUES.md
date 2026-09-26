# Known Issues

Open items only.

Re-checked and re-cut 2026-09-26: seven entries were closed that day and the
remaining ones were re-measured against the field Pi. The stash count below is
the number read from the Pi, not a guess.

## Open — the field Pi still holds its accumulated stashes

Every successful update used to leave one stash behind: a tracked build output
(database, uploads, compiled catalogues) left the tree dirty, `git stash`
captured it before the pull, and the stash was popped only when the pull
*failed*. The Pi holds **79**. The cause is fixed in the repository; the
stashes themselves are still on the Pi.

All three sources are now handled: `hide_live_db` / `hide_media` take the
database and the uploads out of the working tree for the duration of the pull,
and the nine compiled `.mo` files are no longer tracked at all, so nothing the
update generates is left dirty for the next run to stash. The stash condition
also stops counting untracked files, which `git stash` never touches anyway.

**The 79 were cleared on 2026-09-26** (79 → 0), with the working tree verified
after: `db.sqlite3` present and the uploaded logo still 18168 bytes, not the
4030-byte committed placeholder, and the app answering 200. Nothing had to be
recovered from a stash — nothing in any of them was a unique copy of anything
current — which is fortunate, because the two newest recorded the *deletion* of
the logo from the update that untracked it (`Bin 4030 -> 0 bytes`) and popping
one would have deleted the live file.

**Confirmed 2026-09-26, after the update that deployed the untracking:** the Pi
pulled `ca8f3c6`, ran the full update, and `git stash list | wc -l` is still 0 —
it no longer creates one. The nine `.mo` were deleted by that pull (they were
tracked in the outgoing commit) and recreated by the update itself, so the
compile step demonstrably ran on the Pi: the files are newer than the pull and
byte-identical to a fresh local compile.

This entry stays open only as a watch item: if a stash ever reappears, something
the update generates has been tracked again.

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