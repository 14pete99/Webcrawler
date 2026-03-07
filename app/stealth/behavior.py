"""Behavioral simulation — mouse, scroll, keyboard, and dwell time."""

from __future__ import annotations

from app.models.stealth import StealthConfig


def generate_mouse_js(viewport: tuple[int, int], duration_s: float = 3.0) -> str:
    """Generate JS for mouse movement along Bezier curves with jitter."""
    w, h = viewport
    return f"""
(function() {{
    var w = {w}, h = {h}, dur = {duration_s} * 1000;
    var points = [
        [w * 0.5 + (Math.random() - 0.5) * w * 0.2, h * 0.5 + (Math.random() - 0.5) * h * 0.2],
        [Math.random() * w * 0.8 + w * 0.1, Math.random() * h * 0.8 + h * 0.1],
        [Math.random() * w * 0.8 + w * 0.1, Math.random() * h * 0.8 + h * 0.1],
        [Math.random() * w * 0.8 + w * 0.1, Math.random() * h * 0.8 + h * 0.1],
    ];
    function bezier(t, pts) {{
        var n = pts.length - 1;
        var result = [0, 0];
        for (var i = 0; i <= n; i++) {{
            var c = 1;
            for (var j = 0; j < i; j++) c *= (n - j) / (j + 1);
            var factor = c * Math.pow(1 - t, n - i) * Math.pow(t, i);
            result[0] += pts[i][0] * factor;
            result[1] += pts[i][1] * factor;
        }}
        return result;
    }}
    var steps = Math.floor(dur / 50);
    for (var s = 0; s <= steps; s++) {{
        (function(step) {{
            var delay = 30 + Math.floor(Math.random() * 50);
            setTimeout(function() {{
                var t = step / steps;
                var pos = bezier(t, points);
                var jitterX = (Math.random() - 0.5) * 4;
                var jitterY = (Math.random() - 0.5) * 4;
                var x = Math.max(0, Math.min(w, pos[0] + jitterX));
                var y = Math.max(0, Math.min(h, pos[1] + jitterY));
                document.dispatchEvent(new MouseEvent('mousemove', {{
                    clientX: x, clientY: y, bubbles: true
                }}));
            }}, step * delay);
        }})(s);
    }}
}})();
"""


def generate_scroll_js(scroll_count: int = 3) -> str:
    """Generate JS for scroll simulation with variable speed and direction."""
    return f"""
(function() {{
    var count = {scroll_count};
    var scrolled = 0;
    function doScroll() {{
        if (scrolled >= count) return;
        var isUp = scrolled > 0 && Math.random() < 0.2;
        var deltaY = (isUp ? -1 : 1) * (200 + Math.floor(Math.random() * 300));
        window.scrollBy({{ top: deltaY, behavior: 'smooth' }});
        document.dispatchEvent(new WheelEvent('wheel', {{
            deltaY: deltaY, bubbles: true
        }}));
        scrolled++;
        var pause = 500 + Math.floor(Math.random() * 1500);
        setTimeout(doScroll, pause);
    }}
    setTimeout(doScroll, 300 + Math.floor(Math.random() * 700));
}})();
"""


def generate_keystroke_js(text: str) -> str:
    """Generate JS for keystroke simulation with realistic timing."""
    import json as _json

    text_escaped = _json.dumps(text)
    return f"""
(function() {{
    var text = {text_escaped};
    var idx = 0;
    function typeNext() {{
        if (idx >= text.length) return;
        var ch = text[idx];
        var opts = {{ key: ch, code: 'Key' + ch.toUpperCase(), bubbles: true }};
        document.dispatchEvent(new KeyboardEvent('keydown', opts));
        document.dispatchEvent(new KeyboardEvent('keypress', opts));
        document.dispatchEvent(new KeyboardEvent('keyup', opts));
        idx++;
        var delay = Math.max(50, Math.min(300, 120 + (Math.random() - 0.5) * 80));
        setTimeout(typeNext, delay);
    }}
    typeNext();
}})();
"""


def generate_dwell_js(min_s: float = 2.0, max_s: float = 8.0) -> str:
    """Generate JS that waits for a log-normally distributed duration."""
    return f"""
new Promise(function(resolve) {{
    var minMs = {min_s} * 1000;
    var maxMs = {max_s} * 1000;
    var mu = Math.log((minMs + maxMs) / 2);
    var sigma = 0.5;
    var u1 = Math.random(), u2 = Math.random();
    var z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    var sample = Math.exp(mu + sigma * z);
    var clamped = Math.max(minMs, Math.min(maxMs, sample));
    setTimeout(resolve, clamped);
}});
"""


def build_behavior_script(
    config: StealthConfig,
    viewport: tuple[int, int],
) -> list[str]:
    """Assemble enabled behavior scripts based on config flags.

    Args:
        config: Stealth configuration with behavior flags.
        viewport: (width, height) tuple for mouse bounds.

    Returns:
        List of JS strings for post-load execution.
    """
    scripts: list[str] = []

    if config.mouse_simulation:
        scripts.append(generate_mouse_js(viewport))

    if config.scroll_simulation:
        scripts.append(generate_scroll_js())

    if config.keyboard_simulation:
        # Simulate a short idle typing sequence (e.g. search query)
        scripts.append(generate_keystroke_js("hello"))

    if config.dwell_time:
        scripts.append(generate_dwell_js())

    return scripts
