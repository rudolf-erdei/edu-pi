"""Geometry for the noise history chart.

The chart is inline SVG: the shape is worked out here and the template draws
it. No charting library and no CDN, so a dashboard on a Pi with no internet
draws exactly what it draws on a laptop, and nothing about the page can fail
because a remote script did not load.
"""

from typing import List, Optional, Sequence, Tuple

# Viewbox units. The SVG scales to the width of its card; the aspect ratio is
# kept so the labels do not stretch, and the card caps the height.
WIDTH = 720
HEIGHT = 210

# Room for the value labels on the left and the clock times underneath.
PAD_LEFT = 38
PAD_RIGHT = 10
PAD_TOP = 10
PAD_BOTTOM = 24

# Background bands, painted in this order, bottom first. Kept faint so both
# lines stay readable wherever they cross one.
BAND_GREEN = "#22c55e"
BAND_YELLOW = "#eab308"
BAND_RED = "#ef4444"
BAND_OPACITY = 0.14

# Every value label on the axis, top to bottom.
GRID_VALUES = (100, 75, 50, 25, 0)

# Levels are a 0-100 scale. A room louder than that, or a badly set threshold,
# should not push the lines off the top of the chart, so the scale only ever
# grows.
FULL_SCALE = 100


def history_chart(
    readings: Sequence,
    yellow_threshold: int,
    red_threshold: int,
    full_scale: int = FULL_SCALE,
) -> dict:
    """Work out the shape of the history chart.

    The readings are turned into coordinates here rather than in the template,
    which keeps the arithmetic testable and the SVG markup free of conditionals.

    Args:
        readings: Noise readings in chronological order, oldest first. The
            order is what puts time running left to right.
        yellow_threshold: Level the yellow band starts at.
        red_threshold: Level the red band starts at.
        full_scale: Top of the value axis.

    Returns:
        dict: Geometry for the template. ``has_data`` is False when there is
        nothing to draw, and the template shows its own empty message instead.
    """
    readings = list(readings)
    scale = max(full_scale, yellow_threshold, red_threshold)

    left, right = PAD_LEFT, WIDTH - PAD_RIGHT
    top, bottom = PAD_TOP, HEIGHT - PAD_BOTTOM

    def y_of(value: int) -> float:
        clamped = max(0, min(scale, value))
        return bottom - (clamped / scale) * (bottom - top)

    def x_of(index: int) -> float:
        # A single reading has no span to spread across, so it sits in the
        # middle rather than against the left edge.
        if len(readings) <= 1:
            return (left + right) / 2

        return left + index * (right - left) / (len(readings) - 1)

    def plotted(values: List[Optional[int]]) -> List[Tuple[float, float]]:
        """The coordinates of the values that are present, in reading order.

        A missing average is skipped rather than drawn as zero, but the
        readings after it keep their own x, so one gap does not shift the rest
        of the line along.
        """
        return [
            (x_of(i), y_of(value)) for i, value in enumerate(values) if value is not None
        ]

    session_coords = plotted([r.session_average for r in readings])
    instant_coords = plotted([r.instant_average for r in readings])

    def points(coords: List[Tuple[float, float]]) -> str:
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    # The area under the session line, which is the room's verdict over the
    # lesson. Closed along the floor at each end of the line, not at the ends
    # of the window, so a gap at either end does not add a stray triangle.
    session_area = ""
    if session_coords:
        (first_x, first_y), (last_x, last_y) = session_coords[0], session_coords[-1]
        session_area = " ".join(
            [f"M {first_x:.1f},{bottom:.1f}", f"L {first_x:.1f},{first_y:.1f}"]
            + [f"L {x:.1f},{y:.1f}" for x, y in session_coords[1:]]
            + [f"L {last_x:.1f},{bottom:.1f} Z"]
        )

    bands = [
        (y_of(0), y_of(yellow_threshold), BAND_GREEN),
        (y_of(yellow_threshold), y_of(red_threshold), BAND_YELLOW),
        (y_of(red_threshold), y_of(scale), BAND_RED),
    ]

    return {
        "has_data": bool(readings),
        "single_reading": len(readings) == 1,
        "width": WIDTH,
        "height": HEIGHT,
        "plot_left": left,
        "plot_right": right,
        "plot_width": right - left,
        "plot_top": top,
        "plot_bottom": bottom,
        "bands": [
            {
                "y": round(min(y1, y2), 1),
                "height": round(abs(y2 - y1), 1),
                "fill": fill,
                "opacity": BAND_OPACITY,
            }
            for y1, y2, fill in bands
            # A threshold at 0 or at the top of the scale leaves a band of no
            # height, which is nothing to paint.
            if abs(y2 - y1) > 0
        ],
        "gridlines": [
            {"y": round(y_of(value), 1), "label": value}
            for value in GRID_VALUES
            if value <= scale
        ],
        "session_points": points(session_coords),
        "instant_points": points(instant_coords),
        "session_area": session_area,
        # A line needs two points, so a lone reading is drawn as a dot instead.
        "session_dot": _dot(session_coords),
        "instant_dot": _dot(instant_coords),
        "yellow_threshold": yellow_threshold,
        "red_threshold": red_threshold,
        "first_label": _time_label(readings[0]) if readings else "",
        "last_label": _time_label(readings[-1]) if readings else "",
    }


def _dot(coords: List[Tuple[float, float]]) -> Optional[dict]:
    """The single point to draw, when there is only one."""
    if len(coords) != 1:
        return None

    x, y = coords[0]
    return {"x": round(x, 1), "y": round(y, 1)}


def _time_label(reading) -> str:
    """The reading's clock time, in the format the rest of the page uses."""
    return reading.timestamp.strftime("%H:%M")
