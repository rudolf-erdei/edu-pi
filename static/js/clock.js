/**
 * The live clock in the navbar.
 *
 * The time comes from the server, not from the browser. The <time> element
 * carries the Pi's own clock as numbers — `data-epoch`, the instant, and
 * `data-offset`, its UTC offset in seconds (the `datetime` attribute holds the
 * same reading as ISO 8601, for the reader and for assistive tech) — and
 * everything below adds the time since the page loaded to that baseline and
 * reads the result back in UTC. So the navbar clock, the LCD and the activity
 * timers cannot disagree, and a teacher browsing from a laptop set to another
 * zone still sees the room's clock, which is the one the day is planned on.
 * Reading the browser's own clock would have made this the one place in the
 * app that is not on the Pi's time.
 *
 * The offset is a snapshot taken at render time: a page left open across a
 * daylight-saving change reads an hour out until the next page load.
 */

const clockElement = document.getElementById('nav-clock');

const clockPad = (value) => String(value).padStart(2, '0');

/**
 * The clock reading, always 24-hour, as HH:MM:SS.
 *
 * @param {number} baseMs - The baseline instant, in milliseconds since epoch.
 * @param {number} offsetSeconds - The baseline's UTC offset, in seconds.
 * @param {number} elapsedMs - Milliseconds since the baseline was rendered.
 * @returns {string} The wall-clock reading at that moment.
 */
function clockText(baseMs, offsetSeconds, elapsedMs) {
    const shifted = new Date(baseMs + elapsedMs + offsetSeconds * 1000);
    const hours = clockPad(shifted.getUTCHours());
    const minutes = clockPad(shifted.getUTCMinutes());
    const seconds = clockPad(shifted.getUTCSeconds());
    return `${hours}:${minutes}:${seconds}`;
}

if (clockElement) {
    const epochSeconds = parseInt(clockElement.getAttribute('data-epoch'), 10);
    const offsetSeconds = parseInt(clockElement.getAttribute('data-offset'), 10);
    const baseMs = epochSeconds * 1000;

    // Any of these missing, and the server-rendered reading is left as it is:
    // a clock that is merely stale beats one that shows NaN.
    if (!Number.isNaN(baseMs) && !Number.isNaN(offsetSeconds)) {
        const startedAt = Date.now();
        let shown = clockElement.textContent.trim();

        const tick = () => {
            const text = clockText(baseMs, offsetSeconds, Date.now() - startedAt);
            // Every 200ms, but written only when the second changes: the
            // reading is never a whole second late, and a second that has not
            // changed costs no DOM write.
            if (text !== shown) {
                shown = text;
                clockElement.textContent = text;
            }
        };

        tick();
        setInterval(tick, 200);
    }
}
