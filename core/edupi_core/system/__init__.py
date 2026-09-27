"""The settings page's System tab: storage, clients, backup, maintenance.

Four small features that only ever read from the machine and one that writes
exactly one file the user asked for:

- ``storage``  — how full the card is, and what is filling it;
- ``clients``  — which browsers are using the dashboard, counted in memory;
- ``backup``   — a consistent snapshot of the database and media, zipped;
- ``history``  — the retention rules behind the "clean history" button.

Nothing here needs root, talks to ``/proc`` or assumes a Raspberry Pi: the
Pi-only measurements are simply absent when the mounts they describe are not
there, which is what keeps the tab testable on a development machine.
"""
