# Settings

The Settings page provides centralized configuration for Tinko and all plugins.

## Accessing Settings

Click the **Settings** link in the top navigation bar, or navigate to:

```
http://your-pi-ip-address:8000/settings/
```

## Settings Structure

Settings are organized into tabs:

1. **Global Settings** - System-wide configuration
2. **Plugin Settings** - Individual plugin configurations
3. **Updates** - Check for and apply system updates

## Global Settings

Personalize Tinko for your school:

### School Name

Enter your school's name. This appears:

- In the browser tab title
- On the dashboard header
- In emails (if email is configured)

### School Logo

Upload your school logo:

- Supported formats: PNG, JPG, JPEG
- Recommended size: 400x400 pixels or less
- Auto-resized to max 400x400px with 200x200px thumbnail
- Transparent backgrounds supported (PNG)

To upload:

1. Click **Choose File**
2. Select your logo image
3. Click **Save**

The logo will appear on the dashboard and in the header.

### Robot Name

Customize what students call the system:

- Default: "Tinko"
- Examples: "Robo-Teacher", "Classroom Bot", "Sparky"

This name appears in:
- Status messages
- Plugin interfaces
- Voice announcements (if TTS is enabled)

## Plugin Settings

!!! warning "Per-plugin tabs are not available in this version"
    The Settings page currently shows **Global** and **Updates** only. The
    plugin sections below describe how plugin settings are meant to work and how
    their values are stored, but the tabs do not render yet — the settings
    registry they are built from is never populated at startup. It is a known
    issue, tracked in
    [`ISSUES.md`](https://github.com/rudolf-erdei/edu-pi/blob/master/ISSUES.md).

In the meantime, everything a plugin needs to run is configured on the plugin's
own page (for example the Noise Monitor's profile picker and the Activity
Timer's duration presets), and school-wide values live under **Global**.

### Accessing Plugin Settings

1. Click the **Settings** tab for the plugin you want to configure
2. Modify the settings
3. Click **Save**

### Common Setting Types

| Setting Type | Description | Example |
|--------------|-------------|---------|
| Text | Single-line text input | School name |
| Number | Numeric value with min/max | LED brightness (10-100) |
| Select | Dropdown menu | TTS engine selection |
| Boolean | Checkbox (on/off) | Enable/disable feature |
| File | File upload | Audio file, logo image |

### Setting Namespaces

Settings use dot notation for organization:

- **Global**: `tinko.global.school_name`
- **Plugin**: `edupi.activity_timer.default_duration`

## Updates

The Updates tab lets you check for and apply system updates directly from the web interface.

### Checking for Updates

1. Click the **Updates** tab
2. Click **Check for Updates**
3. The system checks the git repository for new commits

If updates are available:
- Number of commits ahead is displayed
- Recent changes are listed
- **Update Now** button becomes active

### Applying Updates

1. Click **Update Now**
2. Confirm the update in the dialog
3. The system performs the update in stages:

| Stage | Description |
|-------|-------------|
| Check git repository | Verify git is clean |
| Stop service | Stop tinko.service |
| Pull latest changes | Git pull from origin |
| Update dependencies | `uv sync` |
| Run migrations | Database schema updates |
| Collect static files | Gather static assets |
| Compile translations | Build language files |
| Update wifi-connect files | Copy captive portal files |
| Restart service | Start tinko.service |

4. Real-time progress is shown with:
   - Stage checkmarks (completed/in-progress/pending)
   - Progress counter (e.g., 3/9)
   - Live log output

### During Update

When the service restarts, the connection drops briefly. The page automatically:
- Shows "Reconnecting..." indicator
- Polls the server every 2 seconds
- Reconnects when the service is back

### After Update

On success:
- "Update Complete!" message appears
- Page auto-refreshes after 10 seconds
- Click **Refresh Now** to reload immediately

On failure:
- Error details displayed in the log area
- **Retry Update** button available
- **Cancel** returns to idle state

### Rate Limiting

Updates can only be triggered every 5 minutes to prevent abuse.

If a previous attempt stopped without finishing — the Pi was switched off
while it was updating, for instance — the page says an update is already
running even though nothing is. That clears by itself at the next check, about
two minutes later, and the update can then be started again; see
[Update Now says an update is already running](../reference/troubleshooting.md#update-now-says-an-update-is-already-running)
if it does not.

### When the Update Changes the Updater

Some updates modify the update script itself. Because a running script cannot
change its own code part-way through, the update restarts once with the new
version and runs the remaining stages again. The progress list may appear to
reset partway through — this is expected, not a failed update. Wait for the
**Update Complete!** message.

Without that restart, changes the script makes to its own logic would only
take effect on the *next* update, which is how a fix could appear to install
successfully and still not be in force.

### Your Data Is Never Overwritten by an Update

The database is written constantly while Tinko runs, so an update always finds
it different from the stored copy. Rather than trying to merge the two, the
update sets the database aside while it fetches new code and puts it back
afterwards, on both the success and the failure path. Timers, routines,
readings and settings survive every update.

Uploaded files are treated the same way. The school logo you chose in
[Global Settings](#school-logo) lives in `media/`, and the update moves whatever
the app wrote there out of the way of the new code and puts it back afterwards.
The logo you uploaded stays the logo after an update.

The one thing that does not survive is a factory-style reinstall that wipes
the database outright — back it up first if that is what you want to do (see
[Configuration Backup](#configuration-backup)).

## Plugin-Specific Settings

### Activity Timer Settings

- **Default Duration**: Default timer length in minutes (1-120)
- **LED Brightness**: LED intensity percentage (10-100)
- **Warning Threshold**: When LED changes color (5-50% remaining)

### Noise Monitor Settings

- **Instant Window**: Seconds for instant average calculation (5-60)
- **Session Window**: Minutes for session average calculation (1-30)
- **LED Brightness**: LED intensity percentage (10-100)
- **Enable Monitoring**: Turn monitoring on/off

### Routines Settings

- **Default TTS Engine**: pyttsx3, edge-tts, or gTTS
- **Default TTS Speed**: Speech rate (0.5x - 2.0x)
- **Presenter Mappings**: Configure USB presenter buttons

### Touch Piano Settings

- **Volume**: Audio output level (0-100%)
- **Audio Device**: ALSA device selection
- **Sensitivity**: Touch detection sensitivity (1-10)

## Settings Hierarchy

Settings are stored with priorities:

1. **User Settings** (if implemented)
2. **Plugin Settings** (plugin-specific)
3. **Global Settings** (system-wide defaults)

When a setting is not defined at a higher level, it falls back to the next level.

## Best Practices

### Naming Conventions

- Use clear, descriptive names
- Avoid special characters
- Keep school names under 50 characters

### Image Uploads

- Use high-quality logos (at least 200x200px)
- Optimize file size (< 500KB)
- Use PNG for transparency support

### Configuration Backup

Settings are stored in the database. Back up regularly:

```bash
# Backup SQLite database
cp db.sqlite3 db.sqlite3.backup

# Or use Django's dumpdata
uv run python manage.py dumpdata core.plugin_system > settings_backup.json
```

## Troubleshooting

### Settings Not Saving

1. Check database migrations:
   ```bash
   uv run python manage.py migrate
   ```
2. Verify file permissions on the database
3. Check disk space

### Logo Not Displaying

1. Ensure migrations are complete
2. Check that `MEDIA_ROOT` is configured
3. Verify the image format (PNG/JPG only)

### Settings Changes Not Applied

Some settings require a restart:

```bash
sudo systemctl restart tinko
```

### Image Upload Fails

- Check file size (max usually 5-10MB)
- Verify image dimensions
- Ensure write permissions on media directory

## Advanced Configuration

### Environment Variables

Some settings can be overridden via environment variables:

```env
DEBUG=False
SECRET_KEY=your-secret-key
TIME_ZONE=Europe/Bucharest
```

See [Configuration Reference](../reference/configuration.md) for details.

### Database Settings

Settings are stored in:

- **SQLite** (default): `db.sqlite3` file
- **PostgreSQL** (production): Requires configuration in `config/settings.py`

## Next Steps

- [Dashboard](dashboard.md) - Return to the main interface
- Plugin guides - Configure individual plugins
- [Background Activities](background-activities.md) - Understand independent operation
