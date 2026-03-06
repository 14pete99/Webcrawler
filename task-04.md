# Task 04: Behavioral Simulation

## Phase 3 — Mouse, scroll, keyboard, and dwell time simulation for the browser session.

## New File: `app/stealth/behavior.py`

Generators for human-like browser interactions. Functions return JS code strings that replay via `dispatchEvent`/`scrollBy`/`setTimeout`.

### Functions

- `generate_mouse_js(viewport: tuple[int, int], duration_s: float = 3.0) -> str` — Dispatches `mousemove` events along a Bezier curve path with random jitter. Curve starts near center, moves to 2-3 random points within viewport. Inter-event delays follow gaussian distribution (~30-80ms). Uses `setTimeout` chains.

- `generate_scroll_js(scroll_count: int = 3) -> str` — Dispatches `wheel` events with variable `deltaY` (200-500px) and pauses between scrolls (500-2000ms). Includes down-scrolls and occasional up-scrolls.

- `generate_keystroke_js(text: str) -> str` — Dispatches `keydown`/`keypress`/`keyup` events with per-character gaussian timing (mean 120ms, stddev 40ms).

- `generate_dwell_js(min_s: float = 2.0, max_s: float = 8.0) -> str` — Returns JS that waits via `Promise` + `setTimeout` for a log-normally distributed duration.

- `build_behavior_script(config: StealthConfig, viewport: tuple[int, int]) -> list[str]` — Assembles enabled behavior scripts into a list. Called from `pipeline.py`.

## Modify: `app/stealth/pipeline.py`

Add to `StealthContext`:
```python
behavior_scripts: list[str] = field(default_factory=list)
```

In `build_stealth_context()`:
```python
from .behavior import build_behavior_script
behavior_scripts = build_behavior_script(config, viewport)
```

**Important distinction**: `js_scripts` = pre-load (fingerprint evasion). `behavior_scripts` = post-load (human simulation).

## Modify: `app/services/crawl4ai.py`

After the main crawl request, if `stealth.behavior_scripts` is non-empty, send a follow-up request to the same session:

```python
if stealth.behavior_scripts and session_id:
    behavior_payload = {
        "urls": [url],
        "session_id": session_id,
        "browser_config": {"type": "BrowserConfig", "params": browser_params},
        "crawler_config": {"type": "CrawlerRunConfig", "params": {
            "js_code": stealth.behavior_scripts,
            "wait_for_images": False,
        }},
    }
    await client.post(f"{settings.crawl4ai_api}/crawl", json=behavior_payload)
```

**Requirement**: Behavioral simulation only works when `session_id` is provided (browser tab must persist). If no session_id, auto-generate one.

**Fallback**: If crawl4ai doesn't support multi-step session requests, bundle behavior scripts with pre-load scripts using `setTimeout` wrappers to defer execution.

## Modify: `app/models/stealth.py`

Add to `StealthConfig`:
```python
mouse_simulation: bool = Field(default=False, description="Simulate mouse movements post-load")
scroll_simulation: bool = Field(default=False, description="Simulate scroll patterns post-load")
keyboard_simulation: bool = Field(default=False, description="Simulate keyboard input timing")
dwell_time: bool = Field(default=False, description="Add random page dwell time")
```

All default `False` — these add latency and are only needed for sites with advanced bot detection.

## Verification

1. `build_behavior_script()` returns valid JS when simulation flags are enabled
2. Generated mouse paths stay within viewport bounds
3. Scroll sequences include both downward and occasional upward scrolls
4. Keystroke timing follows gaussian distribution within reasonable bounds (50-300ms)
5. Dwell time falls within configured min/max range
6. Behavior scripts don't execute when all flags are False
