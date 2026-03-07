"""Cookie consent handling and localStorage seeding."""

from __future__ import annotations


def cookie_consent_js() -> str:
    """JS that auto-dismisses cookie consent dialogs using MutationObserver."""
    return """
(function() {
    function tryDismiss() {
        // OneTrust
        var btn = document.querySelector('#onetrust-accept-btn-handler');
        if (btn) { btn.click(); return true; }
        // CookieBot
        btn = document.querySelector('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll');
        if (btn) { btn.click(); return true; }
        // Generic cookie accept buttons
        btn = document.querySelector('[class*="cookie"] button[class*="accept"]');
        if (btn) { btn.click(); return true; }
        // Fallback: buttons with accept/agree/ok text in cookie-related containers
        var banners = document.querySelectorAll('[class*="cookie"], [id*="cookie"], [class*="consent"], [id*="consent"], [class*="gdpr"], [id*="gdpr"]');
        for (var i = 0; i < banners.length; i++) {
            var buttons = banners[i].querySelectorAll('button, a[role="button"], [class*="btn"]');
            for (var j = 0; j < buttons.length; j++) {
                var text = (buttons[j].textContent || '').trim().toLowerCase();
                if (/^(accept|agree|ok|got it|i agree|allow|allow all)$/i.test(text)) {
                    buttons[j].click();
                    return true;
                }
            }
        }
        return false;
    }

    // Try immediately
    if (tryDismiss()) return;

    // Watch for late-loading banners
    var observer = new MutationObserver(function(mutations, obs) {
        if (tryDismiss()) {
            obs.disconnect();
        }
    });
    observer.observe(document.body || document.documentElement, {
        childList: true, subtree: true
    });

    // Timeout after 5 seconds
    setTimeout(function() { observer.disconnect(); }, 5000);
})();
"""


def seed_storage_js(
    local_storage: dict[str, str] | None = None,
    session_storage: dict[str, str] | None = None,
) -> str:
    """JS to seed localStorage and sessionStorage with key-value pairs."""
    lines: list[str] = ["(function() {"]
    if local_storage:
        for k, v in local_storage.items():
            k_esc = k.replace("\\", "\\\\").replace("'", "\\'")
            v_esc = v.replace("\\", "\\\\").replace("'", "\\'")
            lines.append(f"    try {{ localStorage.setItem('{k_esc}', '{v_esc}'); }} catch(e) {{}}")
    if session_storage:
        for k, v in session_storage.items():
            k_esc = k.replace("\\", "\\\\").replace("'", "\\'")
            v_esc = v.replace("\\", "\\\\").replace("'", "\\'")
            lines.append(f"    try {{ sessionStorage.setItem('{k_esc}', '{v_esc}'); }} catch(e) {{}}")
    lines.append("})();")
    return "\n".join(lines)
