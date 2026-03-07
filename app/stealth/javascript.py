"""Anti-detection JavaScript injection scripts."""

from __future__ import annotations

# Individual JS patches
_PATCH_WEBDRIVER = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});
"""

_PATCH_PLUGINS = """
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});
"""

_PATCH_CHROME = """
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {},
};
"""

_PATCH_PERMISSIONS = """
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
"""

_PATCH_WEBGL = """
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, parameter);
};
"""

ALL_PATCHES = [
    _PATCH_WEBDRIVER,
    _PATCH_PLUGINS,
    _PATCH_CHROME,
    _PATCH_PERMISSIONS,
    _PATCH_WEBGL,
]


def get_js_scripts(
    enabled: bool = True,
    fingerprint_config: dict | None = None,
) -> list[str]:
    """Build the list of JS injection scripts.

    Args:
        enabled: Whether to include base anti-detection patches.
        fingerprint_config: Optional dict with fingerprint spoofing flags
            (canvas_spoof, webgl_spoof, audio_spoof, hardware_spoof,
             font_mask, fingerprint_seed).

    Returns:
        List of JS script strings to inject before page load.
    """
    scripts: list[str] = []
    if enabled:
        scripts.extend(ALL_PATCHES)

    if fingerprint_config:
        from .fingerprint import (
            audio_spoof_js,
            canvas_spoof_js,
            font_mask_js,
            generate_fingerprint_seed,
            hardware_spoof_js,
            webgl_spoof_js,
        )

        seed = fingerprint_config.get("fingerprint_seed")
        if seed is None:
            seed = generate_fingerprint_seed()

        if fingerprint_config.get("canvas_spoof", False):
            scripts.append(canvas_spoof_js(seed))
        if fingerprint_config.get("webgl_spoof", False):
            scripts.append(webgl_spoof_js(seed))
        if fingerprint_config.get("audio_spoof", False):
            scripts.append(audio_spoof_js(seed))
        if fingerprint_config.get("hardware_spoof", False):
            scripts.append(hardware_spoof_js())
        if fingerprint_config.get("font_mask", False):
            scripts.append(font_mask_js())

    return scripts


def build_js_injection(enabled: bool = True, fingerprint_config: dict | None = None) -> str | None:
    """Build the combined JS injection script.

    Args:
        enabled: Whether to produce a script. False returns None.
        fingerprint_config: Optional fingerprint spoofing config dict.

    Returns:
        Combined JS string to inject before page load, or None.
    """
    scripts = get_js_scripts(enabled, fingerprint_config)
    if not scripts:
        return None
    return "\n".join(scripts)
