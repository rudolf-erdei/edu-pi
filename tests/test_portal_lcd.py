"""The captive portal's LCD shows the hotspot name and password.

The screen is the only way a teacher who has just unboxed the Pi can learn what
to connect a phone to, so two things have to hold: the credentials really are
drawn, and the portal really does run under an interpreter that can draw them.

The second one is the failure this file exists for. ``startup_check.sh`` starts
the portal with the system ``python3``, but the adafruit/PIL stack lives only in
the project venv — so the import at the top of ``portal.py`` failed, the screen
stayed dark, and nothing on the setup page said so.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORTAL_PATH = PROJECT_ROOT / "wifi-connect" / "portal.py"

SCREEN = (320, 240)


def load_portal():
    """Import portal.py, which lives outside any Python package."""
    spec = importlib.util.spec_from_file_location("tinko_portal", PORTAL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["tinko_portal"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def portal():
    return load_portal()


class FakeLcd:
    """Stands in for the ILI9341, keeping the last image it was given."""

    def __init__(self, fail=False):
        self.images = []
        self.fail = fail

    def image(self, img):
        if self.fail:
            raise OSError("SPI bus went away")
        self.images.append(img)


class TestLcdDrawing:
    def test_the_hotspot_name_and_password_are_drawn(self, portal):
        """The reported need: the screen tells the teacher what to join."""
        lcd = FakeLcd()
        portal._lcd_device = lcd

        portal._show_wifi_on_lcd("Tinko-Setup", "tinko1234")

        assert len(lcd.images) == 1
        assert lcd.images[0].size == SCREEN

    def test_no_lcd_connected_is_not_an_error(self, portal):
        portal._lcd_device = None

        assert portal._show_wifi_on_lcd("Tinko-Setup", "tinko1234") is None

    def test_a_failing_lcd_does_not_take_the_portal_down(self, portal):
        """A dead screen must not cost the teacher the setup page."""
        portal._lcd_device = FakeLcd(fail=True)

        assert portal._show_wifi_on_lcd("Tinko-Setup", "tinko1234") is None


class TestCredentialTextFits:
    """A network name longer than the screen must shrink, not run off it."""

    @pytest.fixture
    def scalable_fonts(self, portal, monkeypatch):
        """Make _lcd_font size-aware, since this box has no DejaVu."""
        monkeypatch.setattr(
            portal,
            "_lcd_font",
            lambda size: ImageFont.load_default(size=size),
        )
        return portal

    MAX_WIDTH = SCREEN[0] - 28

    def _width(self, draw, text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def test_a_short_name_gets_the_largest_font(self, scalable_fonts):
        portal = scalable_fonts
        draw = portal.ImageDraw.Draw(Image.new("RGB", SCREEN))

        font = portal._fitted_font(draw, "Tinko-Setup", self.MAX_WIDTH)

        assert font.size == portal.CREDENTIAL_SIZES[0]

    def test_a_long_name_is_shrunk_to_fit(self, scalable_fonts):
        portal = scalable_fonts
        draw = portal.ImageDraw.Draw(Image.new("RGB", SCREEN))
        name = "A-Very-Long-School-Network-Name-With-Many-Words"

        font, lines = portal._fit_credential(draw, name, self.MAX_WIDTH)

        assert font.size < portal.CREDENTIAL_SIZES[0]
        assert lines == [name]
        assert self._width(draw, name, font) <= self.MAX_WIDTH

    def test_a_password_too_long_for_one_line_wraps_whole(self, scalable_fonts):
        """A clipped password is the wrong password, so it must not be clipped."""
        portal = scalable_fonts
        draw = portal.ImageDraw.Draw(Image.new("RGB", SCREEN))
        password = "x" * 63  # the longest a Wi-Fi password can be

        font, lines = portal._fit_credential(draw, password, self.MAX_WIDTH)

        assert len(lines) == 2
        assert "".join(lines) == password
        for line in lines:
            assert self._width(draw, line, font) <= self.MAX_WIDTH

    def test_every_length_ends_up_inside_the_screen(self, scalable_fonts):
        """Nothing overflows, and nothing is lost up to the 63-character limit."""
        portal = scalable_fonts
        draw = portal.ImageDraw.Draw(Image.new("RGB", SCREEN))

        for length in range(1, 64):
            text = "x" * length
            font, lines = portal._fit_credential(draw, text, self.MAX_WIDTH)
            assert "".join(lines) == text, f"{length} characters were lost"
            for line in lines:
                assert self._width(draw, line, font) <= self.MAX_WIDTH, (
                    f"{length} chars overflows the screen"
                )

    def test_a_credential_too_long_for_two_lines_is_clipped_and_marked(
        self, scalable_fonts
    ):
        """Beyond wrapping, a marked cut beats a blank screen or a raise."""
        portal = scalable_fonts
        draw = portal.ImageDraw.Draw(Image.new("RGB", SCREEN))

        font, lines = portal._fit_credential(draw, "x" * 200, self.MAX_WIDTH)

        assert len(lines) == 1
        assert lines[0].endswith("...")
        assert self._width(draw, lines[0], font) <= self.MAX_WIDTH

    def test_an_over_long_credential_still_reaches_the_screen(self, portal):
        """Nothing may raise: a clipped name beats a blank screen."""
        lcd = FakeLcd()
        portal._lcd_device = lcd

        portal._show_wifi_on_lcd("x" * 200, "y" * 200)

        assert len(lcd.images) == 1


class TestInterpreterSwitch:
    """The portal must move itself to an interpreter that can drive the LCD."""

    def test_it_reexecs_under_an_interpreter_that_has_the_libraries(
        self, portal, monkeypatch
    ):
        executed = []
        monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
        monkeypatch.setattr(
            portal, "_lcd_capable_interpreters", lambda: iter(["/opt/edu-pi/.venv/bin/python"])
        )
        monkeypatch.setattr(
            portal, "_can_run_portal_with_lcd", lambda path: path == "/opt/edu-pi/.venv/bin/python"
        )
        monkeypatch.setattr(portal.os, "execv", lambda path, argv: executed.append((path, argv)))
        monkeypatch.delenv(portal.REEXEC_ENV_FLAG, raising=False)

        portal.use_lcd_capable_interpreter()

        assert executed, "the portal stayed on an interpreter with no LCD support"
        assert executed[0][0] == "/opt/edu-pi/.venv/bin/python"
        # The new interpreter must be handed the portal script, not a shell.
        assert executed[0][1][1] == str(PORTAL_PATH)
        assert portal.os.environ[portal.REEXEC_ENV_FLAG] == "1"

    def test_it_does_not_reexec_twice(self, portal, monkeypatch):
        """The flag is what stops a re-exec loop between two interpreters."""
        executed = []
        monkeypatch.setattr(portal.os, "environ", {portal.REEXEC_ENV_FLAG: "1"})
        monkeypatch.setattr(portal.os, "execv", lambda path, argv: executed.append(path))
        monkeypatch.setattr(portal, "_can_run_portal_with_lcd", lambda path: False)

        portal.use_lcd_capable_interpreter()

        assert executed == []

    def test_it_stays_put_when_the_current_interpreter_is_already_capable(
        self, portal, monkeypatch
    ):
        executed = []
        monkeypatch.setattr(portal.os, "execv", lambda path, argv: executed.append(path))
        monkeypatch.setattr(portal, "_can_run_portal_with_lcd", lambda path: True)

        portal.use_lcd_capable_interpreter()

        assert executed == []

    def test_it_never_reexecs_into_itself(self, portal, monkeypatch):
        executed = []
        monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
        monkeypatch.setattr(
            portal, "_lcd_capable_interpreters", lambda: iter(["/usr/bin/python3"])
        )
        monkeypatch.setattr(portal, "_can_run_portal_with_lcd", lambda path: True)
        monkeypatch.setattr(portal.os, "execv", lambda path, argv: executed.append(path))

        portal.use_lcd_capable_interpreter()

        assert executed == []

    def test_with_no_candidate_the_portal_still_serves(self, portal, monkeypatch):
        """No LCD libraries anywhere is a dark screen, never a dead portal."""
        executed = []
        monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
        monkeypatch.setattr(portal, "_lcd_capable_interpreters", lambda: iter([]))
        monkeypatch.setattr(portal, "_can_run_portal_with_lcd", lambda path: False)
        monkeypatch.setattr(portal.os, "execv", lambda path, argv: executed.append(path))

        portal.use_lcd_capable_interpreter()

        assert executed == []


    def test_a_candidate_that_will_not_execute_leaves_the_portal_running(
        self, portal, monkeypatch
    ):
        """No screen is bad; a portal that dies is worse, so never depend on execv."""
        monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
        monkeypatch.setattr(
            portal,
            "_lcd_capable_interpreters",
            lambda: iter(["/broken/.venv/bin/python"]),
        )
        monkeypatch.setattr(portal, "_can_run_portal_with_lcd", lambda path: True)

        def refuse(path, argv):
            raise OSError(2, "No such file or directory")

        monkeypatch.setattr(portal.os, "execv", refuse)
        monkeypatch.delenv(portal.REEXEC_ENV_FLAG, raising=False)

        portal.use_lcd_capable_interpreter()  # Must return, not raise.

        assert portal.os.environ.get(portal.REEXEC_ENV_FLAG) is None


class TestCandidateInterpreters:
    def test_the_environment_override_is_tried_first(self, portal, monkeypatch, tmp_path):
        monkeypatch.setattr(portal, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setenv("TINKO_VENV_PYTHON", "/custom/python")

        candidates = list(portal._lcd_capable_interpreters())

        assert candidates[0] == "/custom/python"

    def test_the_venv_beside_the_script_is_found(self, portal, monkeypatch, tmp_path):
        """At install time portal.py is copied next to the project directory."""
        venv_python = tmp_path / "edu-pi" / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
        monkeypatch.setattr(portal, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.delenv("TINKO_VENV_PYTHON", raising=False)

        assert str(venv_python) in list(portal._lcd_capable_interpreters())

    def test_no_candidate_is_offered_twice(self, portal, monkeypatch, tmp_path):
        venv_python = tmp_path / "edu-pi" / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
        monkeypatch.setattr(portal, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setenv("TINKO_VENV_PYTHON", str(venv_python))

        candidates = list(portal._lcd_capable_interpreters())

        assert candidates.count(str(venv_python)) == 1


def test_the_shipped_launcher_starts_the_portal_with_an_interpreter():
    """Guard the contract the re-exec depends on: it is the portal that switches.

    If startup_check.sh ever gained its own interpreter logic the two would
    fight, so it must keep calling plain python3 and let portal.py decide.
    """
    launcher = (PROJECT_ROOT / "wifi-connect" / "startup_check.sh").read_text(
        encoding="utf-8"
    )

    assert 'python3 "${SCRIPT_DIR}/portal.py"' in launcher
