# Known Issues

Open items only.

Re-checked against the field Pi 2026-09-26. Every open item says why it is still
open and what would close it.

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

## Open — per-plugin settings tabs never render

`SettingsRegistry` is filled only when a `PluginSettings` instance is
constructed (`core/plugin_system/settings.py:118`), and no plugin instantiates
one: nothing imports `plugins/*/plugin_settings.py`. `views.py:262-274` therefore
builds no plugin tabs, so the Settings page shows Global and Updates only and the
`PluginSettingsForm` classes written for the plugins are unreachable. Found
2026-09-26 by an audit of what the manual claims against what the code does.

Closing it means picking a registration path — e.g. instantiate each plugin's
settings class during `register()` — and deciding whether the tabs are per-plugin
(section per form) or one section per plugin inside Global.

## Open — nothing asks for a login, and the settings area now deletes and hands over data

Every page and endpoint outside `/admin/` is unauthenticated: there is no
`@login_required` under `core/` or `plugins/`, no login route, and
`LoginRequiredMiddleware` (which would let this be fixed with one setting) only
arrived in Django 5.1 while the project is on 4.2. `settings_view` accepts a
POST that changes the school name and logo with no check at all.

The System tab added 2026-09-27 sharpened this rather than creating it. It
brought four endpoints, all open, and two of them act:

- `GET /settings/system/backup/` **returns the entire database** to any client
  that asks. A URL that starts a download is also a URL a browser follows from a
  link preview or a crawler, so this is not only about a person typing it.
- `POST /settings/system/clean/` deletes rows permanently, with no undo.
- `POST /settings/system/vacuum/` rewrites the database file.
- `GET /settings/system/clients/` discloses the addresses of other clients on
  the network and the page each is on.

The mitigation in place is real but partial: the two destructive endpoints are
POST-only and require Django's CSRF token, so a *third-party page* cannot
trigger them — the token cannot be read cross-origin. It does not stop a client
that fetches `/settings/?tab=system` first and takes the token from the form.

**Why it is open.** PIN-based authentication for teacher settings is a stated
requirement (`REQUIREMENTS.md` → `### Security`) and is not built; building it
as part of this feature would have meant designing how a teacher signs in, what
happens when the PIN is forgotten (the Pi has no keyboard most of the time, and
a lockout is the failure this project must never have), and how the captive
portal's setup page works before any PIN exists. That is a feature, not a
hardening pass.

**What closes it.** A login for the settings surface — Global, Updates and
System — with a recovery path that does not need SSH; then `@login_required` (or
the middleware, if the Django version has moved) on `settings_view` and the four
`/settings/system/` routes, exempting the captive portal's own pages. Until
then the deployment guidance is "school network only, not the open internet",
which is stated in `docs/teacher/settings.md` and `README.md`.

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