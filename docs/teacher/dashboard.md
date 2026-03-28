# Dashboard

The Tinko dashboard is your central hub for accessing all classroom activities.

## Accessing the Dashboard

Navigate to:

```
http://your-pi-ip-address:8000/
```

Or simply:

```
http://your-pi-ip-address:8000
```

## Dashboard Layout

The dashboard displays all installed plugins as interactive cards.

### Header Bar

At the top of the page you'll find:

- **Logo/Title**: Your school name (if configured) or "Tinko"
- **Navigation**: Links to Dashboard, Admin, and Settings
- **Language Selector**: Globe icon to switch between English and Romanian

### App Cards

Each installed plugin appears as a card containing:

| Element | Description |
|---------|-------------|
| Icon | Visual identifier for the plugin |
| Name | The plugin display name |
| Description | Brief explanation of what the plugin does |
| Open Button | Click to launch the plugin interface |

## Apps vs Plugins

Tinko uses two terms interchangeably:

- **Plugins** (technical term): The software modules that extend functionality
- **Apps** (teacher term): What you see and interact with on the dashboard

When we say "App" in the interface, we're referring to a Plugin. They're the same thing - just different terminology for different audiences.

## Using the Dashboard

### Launching an App

1. Find the app card you want to use
2. Click the **Open** button or the card itself
3. The app interface loads in your browser

### Returning to Dashboard

From any app, click:

- The **Tinko** logo/title in the navigation bar
- The **Dashboard** link in the top navigation
- Your browser's back button

!!! note "Background Activities"
    When you navigate away from an app, it continues running in the background. See [Background Activities](background-activities.md) for details.

### Refreshing the Dashboard

Press **F5** or click your browser's refresh button to:

- See newly installed plugins
- Update plugin status
- Refresh after enabling/disabling plugins

## Plugin States

Plugins can be in different states:

| State | Icon | Meaning |
|-------|------|---------|
| Active | None | Plugin is running normally |
| Running | :material-play-circle: | Plugin has an active session |
| Error | :material-alert-circle: | Plugin encountered an error |
| Disabled | :material-block-helper: | Plugin is disabled in admin |

## Admin Panel Access

Click **Admin** in the top navigation to access:

- Plugin management (enable/disable)
- User management
- Database records
- System settings

!!! tip "Admin Credentials"
    Use the superuser account you created during installation. Default: `admin` / `admin123` (change this!)

## Mobile-Friendly

The dashboard works on any device:

- **Desktop**: Full layout with all features
- **Tablet**: Optimized card layout
- **Phone**: Single-column, touch-friendly

## Navigation Tips

### Keyboard Shortcuts

- **F5**: Refresh page
- **Alt+Left Arrow**: Go back
- **Tab**: Navigate between elements

### Bookmarking

Bookmark specific plugin URLs for quick access:

```
http://pi-ip:8000/plugins/edupi/activity_timer/
http://pi-ip:8000/plugins/edupi/noise_monitor/
http://pi-ip:8000/plugins/edupi/routines/
http://pi-ip:8000/plugins/edupi/touch_piano/
```

## Troubleshooting

### Dashboard Not Loading

1. Check that Tinko is running:
   ```bash
   sudo systemctl status tinko
   ```
2. Verify the URL and port
3. Check network connectivity

### Plugins Not Showing

1. Ensure plugins are enabled in Admin Panel
2. Check that migrations are complete:
   ```bash
   uv run python manage.py migrate
   ```
3. Restart Tinko:
   ```bash
   sudo systemctl restart tinko
   ```

### Slow Loading

- Raspberry Pi 3B+ may be slower than Pi 4
- Check system resources: `htop`
- Ensure adequate power supply (2.5A+ for Pi 4)

## Next Steps

- [Settings](settings.md) - Configure your Tinko installation
- [Background Activities](background-activities.md) - Understand how apps run independently
- Plugin guides:
  - [Activity Timer](plugins/activity-timer.md)
  - [Noise Monitor](plugins/noise-monitor.md)
  - [Routines](plugins/routines.md)
  - [Touch Piano](plugins/touch-piano.md)
