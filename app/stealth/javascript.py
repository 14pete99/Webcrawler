"""JavaScript injection snippets for anti-detection evasion."""

from __future__ import annotations

# Patch navigator.webdriver to return undefined
_PATCH_WEBDRIVER = """\
Object.defineProperty(navigator, 'webdriver', {
  get: () => undefined
});
"""

# Add a convincing navigator.plugins array
_PATCH_PLUGINS = """\
Object.defineProperty(navigator, 'plugins', {
  get: () => [
    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
    { name: 'Native Client', filename: 'internal-nacl-plugin' },
  ],
});
"""

# Fake window.chrome object
_PATCH_CHROME = """\
if (!window.chrome) {
  window.chrome = { runtime: {} };
}
"""

# Patch languages to match Accept-Language header
_PATCH_LANGUAGES = """\
Object.defineProperty(navigator, 'languages', {
  get: () => ['en-US', 'en'],
});
"""

_ALL_PATCHES = [_PATCH_WEBDRIVER, _PATCH_PLUGINS, _PATCH_CHROME, _PATCH_LANGUAGES]


def get_js_scripts(enabled: bool = True) -> list[str]:
    """Return a list of JS snippets to inject before page load.

    Returns an empty list when *enabled* is ``False``.
    """
    if not enabled:
        return []
    return list(_ALL_PATCHES)
