# Background Activities

One of Tinko's most powerful features is the ability to run activities independently of the web interface.

## How It Works

When you start an activity (like a timer or noise monitoring) and navigate away to use another plugin, the activity **continues running in the background**.

This is by design - it ensures classroom activities aren't interrupted when teachers switch between tools.

## What Continues Running

When you navigate away from a plugin page:

- ✅ **Timers keep counting down** - The LED continues showing remaining time
- ✅ **Noise monitoring keeps measuring** - LEDs show current noise levels
- ✅ **GPIO pins remain active** - Hardware outputs maintain their state
- ✅ **Database continues logging** - Session data is recorded
- ✅ **Hardware operations work** - Buzzers, LEDs, speakers keep functioning
- ✅ **Background threads run** - Scheduled tasks and monitoring continue

## What Pauses

When you navigate away:

- ❌ **Web browser updates** - No page to display them
- ❌ **WebSocket real-time data streams** - Connection closes
- ❌ **Visual feedback on web interface** - Status indicators freeze

## When You Return

When you navigate back to a plugin:

1. The web interface automatically fetches the **current state** from the running background service
2. Display updates **immediately** to show current status
3. **WebSocket reconnects** (if applicable) for real-time updates
4. Everything appears as if you never left

## Real-World Examples

### Example 1: Timer + Noise Check

**Scenario**: You start a 30-minute activity timer, then want to check classroom noise levels.

1. Start Activity Timer (30 minutes)
2. Navigate to Noise Monitor
3. Check noise levels for 2 minutes
4. Navigate back to Activity Timer
5. **Result**: Timer shows 28 minutes remaining, LED reflects correct color

The timer never stopped counting!

### Example 2: Noise Monitor + Routines

**Scenario**: You're monitoring noise during group work and want to start a routine.

1. Start Noise Monitor
2. Students work in groups (noise levels tracked continuously)
3. Navigate to Routines
4. Play "Deep Breathing" routine
5. **Result**: Noise monitoring continues, LEDs show session average

You can see the noise history when you return!

### Example 3: Multiple Concurrent Activities

**Scenario**: You want a timer running while monitoring noise.

1. Start Activity Timer (10-minute break)
2. Navigate to Noise Monitor
3. Start noise monitoring
4. Both run simultaneously!

**Important**: Each plugin manages its own GPIO pins. Make sure different plugins don't conflict on the same pins.

## Technical Details

### How It Works

Plugins use **singleton background services** with daemon threads:

```python
class ActivityTimerService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._thread = None
        return cls._instance
    
    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
```

The `daemon=True` flag ensures threads continue even when the main web request ends.

### Thread Safety

Background services are designed to be thread-safe:

- Shared state uses locks/mutexes
- Database access is atomic
- GPIO operations are protected

### Resource Management

When a plugin is disabled:

1. Background service receives stop signal
2. Thread completes current operation
3. GPIO pins are cleaned up
4. Resources are released

## Best Practices

### Check Status on Return

Always check the status indicator when returning to a plugin:

- **Running**: Activity is active
- **Paused**: Activity was paused
- **Stopped**: Activity completed while you were away

### Managing Multiple Activities

Be mindful of resource usage:

- Each running activity uses CPU/memory
- GPIO pins can't be shared
- Audio output can only play one thing at a time

### Battery Considerations

If running on battery power:

- Background activities drain battery
- Consider stopping unused activities
- LEDs and audio consume significant power

### Network Considerations

WebSocket connections:

- Reconnect automatically when you return
- Use fallback to HTTP polling if WebSocket fails
- Minimal bandwidth usage

## Troubleshooting

### Activity Shows as Stopped After Return

**Possible causes**:

- Activity completed while you were away
- Plugin was disabled
- Server restarted
- Error occurred

**Solution**: Check logs at `/var/log/tinko/` or `sudo journalctl -u tinko`

### Status Doesn't Update

**Possible causes**:

- WebSocket connection failed
- JavaScript error
- Browser caching

**Solution**: Refresh the page (F5)

### Wrong Status Displayed

**Possible causes**:

- Race condition in state retrieval
- Database lag
- Concurrent modifications

**Solution**: Wait 2-3 seconds for status to sync

### Memory Issues

Running many concurrent activities can consume memory:

```bash
# Check memory usage
htop

# Restart Tinko to clear memory
sudo systemctl restart tinko
```

## Common Questions

**Q: Can I run all four plugins simultaneously?**

A: Yes, but check GPIO pin assignments to avoid conflicts. Each plugin uses different pins by default.

**Q: What happens if I close my browser?**

A: Activities continue running on the Raspberry Pi. They don't depend on your browser being open.

**Q: Can multiple teachers use Tinko at once?**

A: Yes, but be careful - they share the same GPIO pins and state. Coordinate who controls hardware.

**Q: Do activities survive a server restart?**

A: No. Background threads are lost when the server restarts. Save important state to the database if needed.

## Next Steps

- Learn about each plugin:
  - [Activity Timer](plugins/activity-timer.md)
  - [Noise Monitor](plugins/noise-monitor.md)
  - [Routines](plugins/routines.md)
  - [Touch Piano](plugins/touch-piano.md)
- [Dashboard](dashboard.md) - Navigate between activities
- [Settings](settings.md) - Configure plugin behavior
