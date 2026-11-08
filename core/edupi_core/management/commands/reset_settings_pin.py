"""Forget the Settings PIN so the device returns to first-run setup."""

from django.core.management.base import BaseCommand

from core.edupi_core.settings_auth import clear_pin, pin_is_configured


class Command(BaseCommand):
    help = "Forget the Settings PIN and return the device to first-run setup."

    def handle(self, *args, **options):
        if not pin_is_configured():
            self.stdout.write("No settings PIN is configured.")
            return

        clear_pin()
        self.stdout.write(
            self.style.SUCCESS(
                "Settings PIN cleared. The next visit to Settings will ask "
                "for a new PIN."
            )
        )
