"""
Django app configuration for the plugin system.
"""

from django.apps import AppConfig
from django.conf import settings


class PluginSystemConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.plugin_system"
    verbose_name = "Plugin System"

    def ready(self):
        """Called when Django starts up. Load all plugins."""
        import logging

        logger = logging.getLogger(__name__)

        from .base import plugin_manager
        from pathlib import Path

        plugin_manager.load_all()

        # Add plugin locale paths to LOCALE_PATHS
        locale_paths = list(settings.LOCALE_PATHS)
        plugins_path = Path(settings.BASE_DIR) / "plugins"

        if plugins_path.exists():
            for author_dir in plugins_path.iterdir():
                if not author_dir.is_dir():
                    continue
                for plugin_dir in author_dir.iterdir():
                    if not plugin_dir.is_dir():
                        continue
                    plugin_locale = plugin_dir / "locale"
                    if plugin_locale.exists():
                        locale_paths.append(plugin_locale)

        # Update settings (need to use this approach since LOCALE_PATHS is a tuple)
        settings.LOCALE_PATHS = tuple(locale_paths)

        # Auto-run migrations on startup
        self._auto_migrate()

    def _auto_migrate(self):
        """Auto-run database migrations on system boot."""
        import logging
        import os
        import sys
        from io import StringIO

        logger = logging.getLogger(__name__)

        # Check if auto-migration is disabled (for development)
        if os.environ.get("EDUPI_DISABLE_AUTO_MIGRATE", "").lower() == "true":
            logger.info("Auto-migration disabled via EDUPI_DISABLE_AUTO_MIGRATE")
            return

        try:
            from django.core.management import call_command
            from django.db import connections
            from django.db.migrations.executor import MigrationExecutor

            # Check each database for pending migrations
            has_pending = False
            for db in connections:
                connection = connections[db]
                try:
                    connection.ensure_connection()
                    executor = MigrationExecutor(connection)
                    targets = executor.loader.graph.leaf_nodes()
                    plan = executor.migration_plan(targets)
                    if plan:
                        has_pending = True
                        break
                except Exception:
                    # Database not ready yet, skip
                    continue

            if has_pending:
                logger.info("Pending migrations detected, auto-applying...")

                # Capture output to avoid cluttering console during startup
                out = StringIO()
                err = StringIO()

                try:
                    call_command(
                        "migrate",
                        interactive=False,
                        verbosity=0,
                        stdout=out,
                        stderr=err,
                    )
                    logger.info("Auto-migration completed successfully")
                except Exception as e:
                    logger.error(f"Auto-migration failed: {e}")
                    logger.error(f"Migration stderr: {err.getvalue()}")
            else:
                logger.debug("No pending migrations")

        except Exception as e:
            logger.warning(f"Could not check migrations: {e}")
