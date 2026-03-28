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

Each plugin can have its own configuration section.

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
