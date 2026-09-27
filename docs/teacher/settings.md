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
2. **Updates** - Check for and apply system updates
3. **System** - How full the card is, who else is connected, a backup download,
   and the two maintenance buttons (see [System](#system) below)
4. **Plugin Settings** - Individual plugin configurations (these tabs do not
   render yet — see [Plugin Settings](#plugin-settings))

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

## System

The System tab is about the machine the classroom runs on rather than about a
lesson: how full the card is, who else has the page open, a copy of the school's
data, and two buttons for trimming history.

!!! warning "The System tab has no login, like the rest of the site"
    Nothing in this interface asks anyone to sign in, and the parts of the
    System tab with consequences are no exception. Anyone who can reach the Pi
    on the school network can open this tab, so:

    - **the backup link hands over the whole database** to anyone who opens it —
      a URL that starts a full download is a URL a browser will also follow from
      a link preview or a crawl;
    - **Delete old history** permanently deletes rows, with no undo and no
      password;
    - **Compact the database** rewrites the database file;
    - the Global tab next door changes the school name and logo, and the Updates
      tab installs code.

    Tinko is meant to sit on a school's own network, not on the open internet —
    see [Security](https://github.com/rudolf-erdei/edu-pi/blob/master/REQUIREMENTS.md)
    in `REQUIREMENTS.md`. A login for the settings area is a requirement, not a
    built feature; it is tracked in
    [`ISSUES.md`](https://github.com/rudolf-erdei/edu-pi/blob/master/ISSUES.md).
    Until then, treat the port as trusted-network only.

### Storage

Two tables, both measured while the page is being rendered — the tab says when,
and reloading the page takes a fresh reading.

**Filesystems** lists the space on the card, and on `/var/log` and `/var/tmp`
*when they are separate mounts*. On a Pi they are: `/var/log` is log2ram (a
128 MB slice of RAM the logs live in) and `/var/tmp` is RAM as well. Those two
rows are exactly what
[SD Card and Long-Term Wear](../reference/sd-card.md) is about, and they are
absent on a machine that does not have them, which is why a developer's copy of
the page shows a single row.

**What Tinko stores** lists the sizes of the things the app writes: the database
(the file, plus its `-wal` and `-shm` companions, because in WAL mode the newest
committed rows are in the `-wal` and the file alone is not the whole database),
the uploaded files in `media/`, and the logs.

Warnings appear above the tables when something is nearly full: under 10% free
on any filesystem, or over 80% on `/var/log` or `/var/tmp`. The `/var/log`
warning is the one that matters most — when that slice of RAM fills, logging
stops, and the record of what happened on the Pi stops with it.

### Connected Clients

A count of the browsers that asked for a page in the last two minutes, with the
address, the page, and how long since that browser was last seen.

"Asked for a page" is literal: a browser sitting on a page nobody is looking at
stops counting after two minutes, and a browser that only fetched a stylesheet
or an image never counts at all.

The count is kept in the app's memory. It writes no database row and no file, so
watching it costs the SD card nothing. The list refreshes itself every minute
while this tab is open.

### Backup

**Download backup** produces a `.zip` holding:

| Member | What it is |
|---|---|
| `db.sqlite3` | The database, taken with SQLite's own snapshot command |
| `media/` | Everything uploaded — the school logo, and anything else a plugin saved |
| `manifest.json` | What the archive is: when it was made, the hostname, the versions, the database's integrity check and row counts per table, the media file count, and the site settings (minus anything whose name looks like a credential) |

Two details worth knowing:

- **The snapshot is taken with SQLite's own command, not by copying the file.**
  The app runs the database in WAL mode, so a plain copy of `db.sqlite3` is a
  database missing its most recent writes. The snapshot includes the rows
  committed moments before it was taken, and comes out as one self-contained
  file with no `-wal` beside it.
- **The archive is built in memory.** The temporary folder on the Pi is RAM, so
  taking a backup writes nothing to the SD card. The price is that a database
  too large to fit in memory is *refused* with a message rather than attempted —
  a Pi that runs out of memory does not recover neatly.

Log files are deliberately left out: they are not school data, and they would
multiply the size of the download.

**There is no restore.** This is the download half only, and the page says so
where the button is. Putting an archive back is a job for someone at the
keyboard with a copy of the file, not something this page can do.

### Maintenance

Two buttons, and a table of what each kind of history is kept for:

| History | Kept for | Never deleted |
|---|---|---|
| Noise readings | 24 hours | — |
| Timer sessions | 30 days | a session that is pending, running or paused |
| Routine sessions | 30 days | a session that is pending, playing or paused |
| Piano sessions | 30 days | a session that is still active |
| Display sessions | 30 days | a session that is still active |
| Update records | 30 days | an update that is in progress |

The last column is not politeness. A running timer is held in the app's memory
and written back as it changes, so deleting its row underneath would have Django
insert it again; and an update that is in progress is the record that stops a
second update being started. Live things stay.

**Delete old history** removes only rows older than the window above, and only
in the states the table allows. It then says what it deleted, per kind, or that
nothing was old enough to delete — which is the usual answer, and not a broken
button. The timer page shows the ten most recent sessions, and this cannot
shorten that list: anything young enough to be on screen is younger than 30
days.

**Compact the database** rewrites the database file, returning the space left
behind by deleted rows.

!!! note "Deleting rows does not make the file smaller"
    SQLite keeps the freed space inside the file for reuse, so the size on the
    Storage table barely moves when history is deleted. That is normal. Only
    **Compact** returns the space to the card — and because it rewrites the
    whole file, the Pi should not lose power in the middle of it. It is a
    now-and-then action, not a weekly habit.

The plugin event log is left alone entirely: nothing writes to it, it holds no
school data, and deleting an audit log to save nothing sets the wrong
precedent. It is visible in the Django admin only.

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

Settings are stored in the database, so backing up the settings means backing up
the database. Use **Download backup** on the [System](#backup) tab — it is the
supported way, and it takes the database, the uploaded files and a manifest in
one archive.

!!! warning "Do not copy `db.sqlite3` by hand"
    Tinko runs the database in WAL mode, so a plain copy is not the database:
    the most recent committed rows are in the `db.sqlite3-wal` file beside it,
    and a copy of the main file alone loses them. It is also a copy taken while
    the app is writing, which is how a backup ends up corrupt.

    If a copy has to be taken from the command line, ask SQLite for a snapshot
    rather than copying the file:

    ```bash
    # One consistent file, WAL already folded in. Refuses to overwrite.
    sqlite3 db.sqlite3 "VACUUM INTO '/tmp/db-snapshot.sqlite3'"
    ```

    Remember that `-wal` and `-shm` files beside the database are part of it,
    and that moving the database without them is how a school loses a morning.
    `uv run python manage.py dumpdata` still works for a single app's rows in
    JSON, but it is a developer's tool: it does not carry the uploaded files.

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
