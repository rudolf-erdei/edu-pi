"""The app's own share of the SD card's writes.

Every other part of the card's life is the operating system's business — the
scripts in ``scripts/update_infra.sh`` turn off what can be turned off. This
file covers the two writers the app owns and cannot hand to anyone else:

* ``logs/``, which grew to 8.7MB on the field Pi because a plain FileHandler
  never stops writing to the same file, and the LCD service logged every panel
  refresh at DEBUG;
* the database, which the noise monitor commits to every five seconds for as
  long as the Pi is switched on.

Both were measurable on the deployed Pi: 26,369 readings after a day and a
half, and two log files with no rotation at all.
"""

from pathlib import Path

from django.conf import settings

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = REPO_ROOT / "config" / "settings.py"


class FakeCursor:
    """Records the SQL a connection would have run."""

    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)


class FakeConnection:
    def __init__(self, vendor="sqlite"):
        self.vendor = vendor
        self._cursor = FakeCursor()

    def cursor(self):
        return self._cursor


def pragmas_for(vendor="sqlite"):
    from config.settings import set_sqlite_pragmas

    connection = FakeConnection(vendor)
    set_sqlite_pragmas(None, connection)
    return connection._cursor.statements


def test_the_log_handlers_roll_over():
    """A plain FileHandler grows forever; a rolling one reuses its bytes."""
    handlers = settings.LOGGING["handlers"]

    for name in ("file", "lcd_file"):
        handler = handlers[name]
        assert handler["class"].endswith("RotatingFileHandler"), name
        assert handler["maxBytes"] > 0, name
        assert handler["backupCount"] >= 1, name
        assert handler["delay"] is True, name


def test_the_logs_cannot_outgrow_the_card():
    """maxBytes times (backupCount + 1) is the whole footprint of a log file,
    however long the Pi runs."""
    for name in ("file", "lcd_file"):
        handler = settings.LOGGING["handlers"][name]
        footprint = handler["maxBytes"] * (handler["backupCount"] + 1)

        assert footprint <= 8 * 1024 * 1024, f"{name} can reach {footprint} bytes"


def test_the_lcd_logger_no_longer_logs_every_refresh():
    """DEBUG there was a write per panel redraw, for information the LCD page
    already shows."""
    loggers = settings.LOGGING["loggers"]

    for name in ("plugins.edupi.lcd_display", "plugins.edupi.lcd_display.lcd_service"):
        assert loggers[name]["level"] != "DEBUG", name


def test_the_database_asks_for_the_write_ahead_log():
    """The mode is what makes a power cut survivable *and* cheaper.

    With the default rollback journal, `synchronous=NORMAL` is the one
    combination SQLite documents as corruption-prone on power loss, and every
    commit writes the journal and the page. In WAL, NORMAL is safe.
    """
    statements = pragmas_for()

    assert "PRAGMA journal_mode=WAL" in statements
    assert "PRAGMA synchronous=NORMAL" in statements
    assert "PRAGMA temp_store=MEMORY" in statements


def test_the_ahead_log_is_kept_from_growing_between_checkpoints():
    statements = pragmas_for()

    checkpoint = [s for s in statements if "wal_autocheckpoint" in s]

    assert len(checkpoint) == 1
    pages = int(checkpoint[0].rsplit("=", 1)[1])
    assert 0 < pages <= 1000, "a big window means a big log to replay"


def test_a_non_sqlite_database_is_left_alone():
    """These PRAGMAs are SQLite's; running them elsewhere is an error."""
    assert pragmas_for(vendor="postgresql") == []


def test_the_pragma_is_installed_on_every_connection():
    """Not once at startup: Django opens and closes connections, and a
    connection that arrives without the mode is a connection on the rollback
    journal."""
    text = SETTINGS_FILE.read_text(encoding="utf-8")

    assert "connection_created.connect(set_sqlite_pragmas)" in text


def test_the_logs_are_not_tracked_by_git():
    """Untracked logs mean the update's merge cannot stash them — the same
    class of problem as the .mo catalogues and the uploaded logo."""
    ignore = REPO_ROOT / "logs" / ".gitignore"

    assert ignore.exists()
    assert "*.log" in ignore.read_text(encoding="utf-8")
