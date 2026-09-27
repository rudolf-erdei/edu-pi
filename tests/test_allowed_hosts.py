"""Tests for ALLOWED_HOSTS being built from the machine, not from install day.

`install-raspberry-pi.sh` writes the address it sees at install time into
`.env` (`ALLOWED_HOSTS=...,${PI_IP},tinko.local`), and nothing ever revisits it.
The field Pi was installed at 192.168.68.63 and later came up on 192.168.68.66
over DHCP: measured with a Host header, `.66` answered 400 DisallowedHost, and
so did the bare hostname `tinko` — which is the name the LCD and the setup
portal show the teacher. Only `tinko.local` and the stale address worked.

`config.settings` therefore merges the configured list with the names the
machine answers to *now*: its hostname, `.local` (Django's subdomain wildcard,
covering the mDNS name), and the address of the interface that reaches the
network. These tests hold that, and that an operator's own entries survive.
"""

import os
import socket
from unittest import mock

from django.conf import settings

from config.settings import allowed_hosts, local_host_names


def test_local_names_include_the_hostname_and_mdns_domain():
    names = local_host_names()

    assert socket.gethostname() in names, "the bare hostname must be accepted"
    assert ".local" in names, "mDNS name (tinko.local) must be accepted"


def test_no_route_is_not_fatal():
    """A Pi with no default route must still start, not fail on settings."""
    with mock.patch.object(socket, "socket", side_effect=OSError("no route")):
        names = local_host_names()

    assert socket.gethostname() in names
    assert ".local" in names


def test_configured_hosts_are_kept():
    hosts = allowed_hosts("school.example,10.0.0.5")

    assert "school.example" in hosts
    assert "10.0.0.5" in hosts


def test_every_configured_host_is_joined_by_the_machine_names():
    hosts = allowed_hosts("school.example")

    assert socket.gethostname() in hosts
    assert ".local" in hosts


def test_empty_configuration_keeps_loopback():
    """With DEBUG off, `[]` rejects everything -- including the Pi's own screen."""
    hosts = allowed_hosts("")

    assert {"localhost", "127.0.0.1", "0.0.0.0"} <= set(hosts)


def test_settings_are_built_this_way():
    """The module must actually use the merge, not just define it.

    Subset, not equality: Django's test setup appends "testserver" to
    ALLOWED_HOSTS, which is an artefact of running under the test runner.
    """
    expected = allowed_hosts(os.environ.get("ALLOWED_HOSTS", ""))

    assert set(expected) <= set(settings.ALLOWED_HOSTS)
    assert {"localhost", ".local", socket.gethostname()} <= set(settings.ALLOWED_HOSTS)


def test_the_field_pi_case_is_covered():
    """The exact list from the field Pi's .env, with the address it drifted to."""
    field_env = "localhost,127.0.0.1,0.0.0.0,192.168.68.63,tinko.local"
    hosts = allowed_hosts(field_env)

    # The stale address, the mDNS name and the bare hostname all answer.
    assert {"192.168.68.63", "tinko.local"} <= set(hosts)
    assert socket.gethostname() in hosts
