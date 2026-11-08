"""Plugin tabs on the Settings page.

A plugin owns its own configuration page — the noise monitor's profile and
timing form, the timer's and piano's configuration lists. The Settings page
offers one tab per plugin that declares such a page, and the tab is a card
that links to it rather than a second editor for the same records. One write
path is the point: a settings form here that wrote the same model the plugin
page writes would drift from it the moment either changed.

The old ``plugin_settings.py`` files and the ``PluginSettings`` registry they
were written for are gone: nothing ever instantiated one, so the tabs never
rendered and none of those forms was ever reachable.
"""

import pytest
from django.test import Client

from core.plugin_system.base import PluginBase, PluginManager
from tests.helpers import login_settings


class FakePlugin(PluginBase):
    """A plugin that declares one settings page."""

    def __init__(self, path="plugins.acme.demo", name="Demo", enabled=True):
        super().__init__(path, enabled)
        self.name = name


def test_a_plugin_registers_where_its_settings_live():
    plugin = FakePlugin()

    plugin.register_settings_tab(
        "Demo Settings",
        "/plugins/acme/demo/config/",
        description="Configure the demo",
    )

    assert plugin.get_settings_tabs() == [
        {
            "label": "Demo Settings",
            "url": "/plugins/acme/demo/config/",
            "description": "Configure the demo",
            "icon": "cog",
        }
    ]


def _settings_page(monkeypatch, plugins):
    manager = PluginManager()
    for plugin in plugins:
        manager._plugins[plugin.plugin_path] = plugin
    monkeypatch.setattr("core.edupi_core.views.plugin_manager", manager)
    return login_settings(Client())


@pytest.mark.django_db
def test_the_settings_page_offers_a_tab_for_a_plugin_that_declared_one(monkeypatch):
    plugin = FakePlugin()
    plugin.register_settings_tab("Demo Settings", "/plugins/acme/demo/config/")
    client = _settings_page(monkeypatch, [plugin])

    resp = client.get("/settings/")

    ids = [tab["id"] for tab in resp.context["tabs"]]
    assert "acme_demo" in ids
    # Plugin tabs belong to the settings themselves, before the fixed tabs.
    assert ids.index("acme_demo") < ids.index("updates")


@pytest.mark.django_db
def test_the_plugin_tab_is_a_card_linking_to_the_plugin_page(monkeypatch):
    plugin = FakePlugin()
    plugin.register_settings_tab(
        "Demo Settings",
        "/plugins/acme/demo/config/",
        description="Configure the demo",
    )
    client = _settings_page(monkeypatch, [plugin])

    resp = client.get("/settings/", {"tab": "acme_demo"})
    body = resp.content.decode()

    assert resp.status_code == 200
    assert resp.context["is_plugin"] is True
    assert "Demo Settings" in body
    assert "Configure the demo" in body
    assert "/plugins/acme/demo/config/" in body


@pytest.mark.django_db
def test_a_disabled_plugin_is_not_offered(monkeypatch):
    plugin = FakePlugin(enabled=False)
    plugin.register_settings_tab("Demo Settings", "/plugins/acme/demo/config/")
    client = _settings_page(monkeypatch, [plugin])

    resp = client.get("/settings/")

    assert "acme_demo" not in [tab["id"] for tab in resp.context["tabs"]]


@pytest.mark.django_db
def test_a_plugin_without_a_settings_page_gets_no_tab(monkeypatch):
    client = _settings_page(monkeypatch, [FakePlugin()])

    resp = client.get("/settings/")

    assert [tab["id"] for tab in resp.context["tabs"]] == [
        "global",
        "updates",
        "system",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "import_path, url",
    [
        ("plugins.edupi.activity_timer", "/plugins/edupi/activity_timer/configs/"),
        ("plugins.edupi.noise_monitor", "/plugins/edupi/noise_monitor/config/"),
        ("plugins.edupi.touch_piano", "/plugins/edupi/touch_piano/configs/"),
    ],
)
def test_builtin_plugins_point_at_their_own_configuration_page(import_path, url):
    from core.plugin_system.base import plugin_manager

    plugin_manager.load_all()
    plugin = plugin_manager.get_plugin(import_path)

    assert plugin is not None
    assert url in [tab["url"] for tab in plugin.get_settings_tabs()]
