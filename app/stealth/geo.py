"""Geographic consistency — timezone, locale, and language matching."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.proxy import ProxyEntry


@dataclass
class GeoProfile:
    """Geographic identity matched to a proxy location."""

    country_code: str       # ISO 3166-1 alpha-2
    timezone: str           # IANA timezone
    locale: str             # e.g. "en-US"
    languages: list[str] = field(default_factory=list)


# Map of country codes to geo profiles (~30 common countries)
_GEO_MAP: dict[str, GeoProfile] = {
    "US": GeoProfile("US", "America/New_York", "en-US", ["en-US", "en"]),
    "GB": GeoProfile("GB", "Europe/London", "en-GB", ["en-GB", "en"]),
    "CA": GeoProfile("CA", "America/Toronto", "en-CA", ["en-CA", "en"]),
    "AU": GeoProfile("AU", "Australia/Sydney", "en-AU", ["en-AU", "en"]),
    "DE": GeoProfile("DE", "Europe/Berlin", "de-DE", ["de-DE", "de", "en"]),
    "FR": GeoProfile("FR", "Europe/Paris", "fr-FR", ["fr-FR", "fr", "en"]),
    "ES": GeoProfile("ES", "Europe/Madrid", "es-ES", ["es-ES", "es", "en"]),
    "IT": GeoProfile("IT", "Europe/Rome", "it-IT", ["it-IT", "it", "en"]),
    "NL": GeoProfile("NL", "Europe/Amsterdam", "nl-NL", ["nl-NL", "nl", "en"]),
    "BE": GeoProfile("BE", "Europe/Brussels", "nl-BE", ["nl-BE", "fr-BE", "en"]),
    "CH": GeoProfile("CH", "Europe/Zurich", "de-CH", ["de-CH", "fr-CH", "en"]),
    "AT": GeoProfile("AT", "Europe/Vienna", "de-AT", ["de-AT", "de", "en"]),
    "SE": GeoProfile("SE", "Europe/Stockholm", "sv-SE", ["sv-SE", "sv", "en"]),
    "NO": GeoProfile("NO", "Europe/Oslo", "nb-NO", ["nb-NO", "no", "en"]),
    "DK": GeoProfile("DK", "Europe/Copenhagen", "da-DK", ["da-DK", "da", "en"]),
    "FI": GeoProfile("FI", "Europe/Helsinki", "fi-FI", ["fi-FI", "fi", "en"]),
    "PL": GeoProfile("PL", "Europe/Warsaw", "pl-PL", ["pl-PL", "pl", "en"]),
    "CZ": GeoProfile("CZ", "Europe/Prague", "cs-CZ", ["cs-CZ", "cs", "en"]),
    "PT": GeoProfile("PT", "Europe/Lisbon", "pt-PT", ["pt-PT", "pt", "en"]),
    "BR": GeoProfile("BR", "America/Sao_Paulo", "pt-BR", ["pt-BR", "pt", "en"]),
    "MX": GeoProfile("MX", "America/Mexico_City", "es-MX", ["es-MX", "es", "en"]),
    "AR": GeoProfile("AR", "America/Argentina/Buenos_Aires", "es-AR", ["es-AR", "es", "en"]),
    "JP": GeoProfile("JP", "Asia/Tokyo", "ja-JP", ["ja-JP", "ja", "en"]),
    "KR": GeoProfile("KR", "Asia/Seoul", "ko-KR", ["ko-KR", "ko", "en"]),
    "CN": GeoProfile("CN", "Asia/Shanghai", "zh-CN", ["zh-CN", "zh", "en"]),
    "TW": GeoProfile("TW", "Asia/Taipei", "zh-TW", ["zh-TW", "zh", "en"]),
    "IN": GeoProfile("IN", "Asia/Kolkata", "en-IN", ["en-IN", "hi", "en"]),
    "RU": GeoProfile("RU", "Europe/Moscow", "ru-RU", ["ru-RU", "ru", "en"]),
    "UA": GeoProfile("UA", "Europe/Kyiv", "uk-UA", ["uk-UA", "uk", "en"]),
    "TR": GeoProfile("TR", "Europe/Istanbul", "tr-TR", ["tr-TR", "tr", "en"]),
    "IL": GeoProfile("IL", "Asia/Jerusalem", "he-IL", ["he-IL", "he", "en"]),
    "SG": GeoProfile("SG", "Asia/Singapore", "en-SG", ["en-SG", "en"]),
}


def match_geo_to_proxy(proxy_entry: ProxyEntry) -> GeoProfile | None:
    """Look up a GeoProfile for the proxy's country."""
    if not proxy_entry.country:
        return None
    return _GEO_MAP.get(proxy_entry.country.upper())


def geo_override_js(geo: GeoProfile) -> str:
    """JS overrides for timezone, language, and locale to match geo profile."""
    languages_js = ", ".join(f"'{lang}'" for lang in geo.languages)

    # Calculate timezone offset in minutes for the given timezone
    # This is an approximation — real offsets vary by DST
    _TIMEZONE_OFFSETS: dict[str, int] = {
        "America/New_York": 300, "America/Toronto": 300,
        "America/Chicago": 360, "America/Denver": 420,
        "America/Los_Angeles": 480, "America/Sao_Paulo": 180,
        "America/Mexico_City": 360,
        "America/Argentina/Buenos_Aires": 180,
        "Europe/London": 0, "Europe/Paris": -60, "Europe/Berlin": -60,
        "Europe/Madrid": -60, "Europe/Rome": -60, "Europe/Amsterdam": -60,
        "Europe/Brussels": -60, "Europe/Zurich": -60, "Europe/Vienna": -60,
        "Europe/Stockholm": -60, "Europe/Oslo": -60, "Europe/Copenhagen": -60,
        "Europe/Helsinki": -120, "Europe/Warsaw": -60, "Europe/Prague": -60,
        "Europe/Lisbon": 0, "Europe/Moscow": -180, "Europe/Kyiv": -120,
        "Europe/Istanbul": -180,
        "Asia/Tokyo": -540, "Asia/Seoul": -540, "Asia/Shanghai": -480,
        "Asia/Taipei": -480, "Asia/Kolkata": -330, "Asia/Jerusalem": -120,
        "Asia/Singapore": -480,
        "Australia/Sydney": -660,
    }
    offset = _TIMEZONE_OFFSETS.get(geo.timezone, 0)

    return f"""
(function() {{
    // Override navigator.language and navigator.languages
    Object.defineProperty(navigator, 'language', {{
        get: function() {{ return '{geo.locale}'; }}
    }});
    Object.defineProperty(navigator, 'languages', {{
        get: function() {{ return [{languages_js}]; }}
    }});

    // Override Intl.DateTimeFormat to return correct timezone
    var OrigDTF = Intl.DateTimeFormat;
    Intl.DateTimeFormat = function(locale, options) {{
        options = options || {{}};
        if (!options.timeZone) {{
            options.timeZone = '{geo.timezone}';
        }}
        return new OrigDTF(locale, options);
    }};
    Intl.DateTimeFormat.prototype = OrigDTF.prototype;
    Intl.DateTimeFormat.supportedLocalesOf = OrigDTF.supportedLocalesOf;

    // Override Date.prototype.getTimezoneOffset
    Date.prototype.getTimezoneOffset = function() {{
        return {offset};
    }};
}})();
"""
