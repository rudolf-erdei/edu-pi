# First Steps

Now that Tinko is installed, let's get you set up and familiar with the basics.

## Accessing the Dashboard

Open a web browser and navigate to:

```
http://your-pi-ip-address:8000/
```

Replace `your-pi-ip-address` with your Raspberry Pi's IP address.

!!! tip "Finding Your Pi's IP Address"
    On the Raspberry Pi, run:
    ```bash
    hostname -I
    ```
    This will display the IP address(es) of your Pi.

## Logging In

If you haven't created an admin user yet, run:

```bash
uv run python manage.py createsuperuser
```

Follow the prompts to create your account.

Then log in at:

```
http://your-pi-ip-address:8000/admin/
```

## Understanding the Dashboard

The main dashboard (`/`) shows all your installed apps. You'll see cards for:

- Activity Timer
- Noise Monitor
- Routines
- Touch Piano

Each card shows:

- Plugin name
- Icon
- Brief description
- Link to open the app

## Changing the Language

Tinko supports English and Romanian:

1. Look for the globe icon :material-earth: in the top navigation bar
2. Click it to open the language selector
3. Choose your preferred language

The interface will update immediately with translated text.

## Configuring Global Settings

Personalize Tinko for your school:

1. Click **Settings** in the top navigation
2. You'll see tabs for:
   - **Global Settings**: School name, logo, robot name
   - **Plugin Settings**: Individual plugin configurations

### Setting Your School Name and Logo

1. Go to the **Global Settings** tab
2. Enter your school name
3. Upload your school logo (max 400x400px, will be auto-resized)
4. Set your robot's name (default: "Tinko")
5. Click **Save**

Your school name and logo will appear on the dashboard.

## Enabling Plugins

All plugins are installed by default, but you can enable/disable them:

1. Go to **Admin Panel** (`/admin/`)
2. Navigate to **Plugins**
3. Toggle plugins on/off as needed

Disabled plugins won't show on the dashboard.

## Your First Activity

Let's try the Activity Timer:

1. From the dashboard, click **Activity Timer**
2. You'll see preset buttons:
   - **Minute of Silence**: 60 seconds, calming blue
   - **Break Time**: 10 minutes, green theme
   - **Activity**: 30 minutes, amber theme
3. Click **Minute of Silence** to test
4. Click the **Start** button

Watch the RGB LED change colors as time counts down!

!!! note "Hardware Required"
    For the LED to light up, you need an RGB LED connected to pins 17 (red), 27 (green), and 22 (blue).

## Testing Other Plugins

### Noise Monitor

1. Click **Noise Monitor** on the dashboard
2. Click **Start Monitoring**
3. Make some noise - watch the LEDs change color

### Touch Piano

1. Click **Touch Piano**
2. Click keys on screen or use keyboard (A, S, D, F, G, H)
3. Connect conductive materials to GPIO pins to play physically

### Routines

1. Click **Routines**
2. Try a pre-built routine like **Hand Warming Exercise**
3. Click **Play** to start text-to-speech

## Understanding Background Activities

When you start an activity and navigate away:

- ✅ **Continues running**: Timer counts down, noise monitoring, GPIO outputs
- ❌ **Pauses**: Web interface updates, WebSocket data streams
- 🔄 **Resumes**: When you return, the page shows current status

This means you can:

1. Start a 30-minute activity timer
2. Switch to Noise Monitor to check classroom levels
3. Return to timer to see remaining time
4. All physical LED feedback continues throughout

Learn more: [Background Activities](background-activities.md)

## Next Steps

- [Dashboard](dashboard.md) - Detailed interface guide
- [Settings](settings.md) - Complete settings documentation
- Plugin guides:
  - [Activity Timer](plugins/activity-timer.md)
  - [Noise Monitor](plugins/noise-monitor.md)
  - [Routines](plugins/routines.md)
  - [Touch Piano](plugins/touch-piano.md)

## Getting Help

- Check the [Troubleshooting](../reference/troubleshooting.md) guide
- Review plugin-specific documentation
- Open an issue on [GitHub](https://github.com/rudolf-erdei/edu-pi)

**You're ready to use Tinko in your classroom!** 🎓
