"""Whether the running process is the server, or a one-shot command.

The plugin system loads in every process that touches Django: the daphne
service, the ``collectstatic`` that runs as its ExecStartPre, ``migrate`` from
the install and update scripts, and the test run. Plugins that start background
services or claim hardware on load have to tell those apart — a process that
exits in two seconds has no business holding the microphone or the display, and
while it does it is competing with the service that is about to start.
"""

import sys

# Management commands that load the plugin system but are not the server.
# collectstatic is the one that matters: the service file runs it as an
# ExecStartPre, immediately before the real process starts.
BATCH_COMMANDS = {
    "check",
    "collectstatic",
    "compilemessages",
    "createsuperuser",
    "dumpdata",
    "loaddata",
    "makemigrations",
    "migrate",
    "shell",
    "showmigrations",
    "test",
}


def running_under_pytest() -> bool:
    """Whether this process is a test run.

    Its own function so tests can say "pretend this is the server" without
    pulling pytest out of ``sys.modules``.
    """
    return "pytest" in sys.modules


def is_server_process() -> bool:
    """Whether this process is the one that should hold the hardware.

    Anything not on the batch list counts as the server, so a service whose
    command line changes keeps working instead of quietly stopping.

    Pytest is the exception the batch list cannot express: its command line is
    the test paths, so ``sys.argv[1]`` is not a management command and the
    check below read a test run as the server. That started a real noise
    monitor thread at Django setup in every test session, which sampled
    throughout the run and made the suite fail intermittently wherever another
    test touched the display that thread was painting.
    """
    if running_under_pytest():
        return False

    if len(sys.argv) < 2:
        return True

    return sys.argv[1] not in BATCH_COMMANDS
