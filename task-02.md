# Task 02: Browser Fingerprint Hardening

## Phase 1 — Lowest risk, highest immediate value. No new dependencies.

## New File: `app/stealth/fingerprint.py`

JS patch generators using a deterministic per-session seed (consistent within a session, varies across sessions).

### Functions

- `generate_fingerprint_seed() -> int` — `random.randint(0, 2**32 - 1)`
- `canvas_spoof_js(seed: int) -> str` — Wraps `HTMLCanvasElement.prototype.toDataURL` and `CanvasRenderingContext2D.prototype.getImageData`. Applies deterministic per-channel noise (+/- 1) using a seeded JS PRNG (xorshift/mulberry32). Imperceptible visually, changes the hash.
- `webgl_spoof_js(seed: int) -> str` — Overrides `WebGLRenderingContext.prototype.getParameter` for `RENDERER` (0x1F01) and `VENDOR` (0x1F00). Returns altered strings from a curated GPU pool selected by `seed % len(pool)`. Also wraps `getExtension`/`getSupportedExtensions` to shuffle/filter extensions.
- `audio_spoof_js(seed: int) -> str` — Wraps `AnalyserNode.prototype.getFloatFrequencyData` and `AudioBuffer.prototype.getChannelData` to add sub-LSB noise using seeded PRNG.
- `hardware_spoof_js(cores: int | None, memory: int | None) -> str` — Overrides `navigator.hardwareConcurrency` and `navigator.deviceMemory`. If None, picks from pools: cores `[2, 4, 8, 12, 16]`, memory `[4, 8, 16, 32]`.
- `font_mask_js() -> str` — Overrides `document.fonts.check()` to return `true` only for a baseline set (~20 common fonts: Arial, Times New Roman, Courier New, Verdana, Georgia, etc.). Patches `FontFaceSet.prototype.check`.

## Modify: `app/stealth/javascript.py`

Change `get_js_scripts` signature:

```python
def get_js_scripts(
    enabled: bool = True,
    fingerprint_config: dict | None = None,
) -> list[str]:
```

When `enabled` is True, include existing `_ALL_PATCHES`. Then conditionally append fingerprint patches based on `fingerprint_config` keys (`canvas_spoof`, `webgl_spoof`, `audio_spoof`, `hardware_spoof`, `font_mask`, `fingerprint_seed`).

Backward compatible: existing callers passing only `enabled=True` get same behavior.

## Modify: `app/models/stealth.py`

Add to `StealthConfig`:

```python
canvas_spoof: bool = Field(default=True, description="Spoof canvas fingerprint")
webgl_spoof: bool = Field(default=True, description="Spoof WebGL fingerprint")
audio_spoof: bool = Field(default=True, description="Spoof AudioContext fingerprint")
hardware_spoof: bool = Field(default=True, description="Spoof hardwareConcurrency/deviceMemory")
font_mask: bool = Field(default=True, description="Mask font enumeration")
fingerprint_seed: int | None = Field(default=None, description="Seed for fingerprint noise; None = random per session")
```

All default `True` so existing requests automatically get protection.

## Modify: `app/stealth/pipeline.py`

Build `fingerprint_config` dict from `StealthConfig` fields and pass to `get_js_scripts()`:

```python
fingerprint_config = {
    "canvas_spoof": config.canvas_spoof,
    "webgl_spoof": config.webgl_spoof,
    "audio_spoof": config.audio_spoof,
    "hardware_spoof": config.hardware_spoof,
    "font_mask": config.font_mask,
    "fingerprint_seed": config.fingerprint_seed,
}
js_scripts = get_js_scripts(config.js_injection, fingerprint_config=fingerprint_config)
```

No new `StealthContext` fields needed — patches go into existing `js_scripts` list.

## Update: `data/profiles/default.json`

Add the new fields with defaults.

## Verification

1. Import `fingerprint.py` functions — no errors
2. Each JS snippet is syntactically valid (test with `node --check` if available)
3. `build_stealth_context()` returns a context with fingerprint patches in `js_scripts`
4. Existing API requests without explicit fingerprint config still work (backward compat)
