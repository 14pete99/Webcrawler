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


def build_js_injection(enabled: bool = True) -> str | None:
    """Build the combined JS injection script.

    Args:
        enabled: Whether to produce a script. False returns None.

    Returns:
        Combined JS string to inject before page load, or None.
    """
    if not enabled:
        return None
    return "\n".join(ALL_PATCHES)
