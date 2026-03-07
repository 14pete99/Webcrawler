"""Browser fingerprint spoofing — canvas, WebGL, audio, hardware, fonts."""

from __future__ import annotations

import random


def generate_fingerprint_seed() -> int:
    """Generate a random seed for deterministic fingerprint noise."""
    return random.randint(0, 2**32 - 1)


def canvas_spoof_js(seed: int) -> str:
    """JS to spoof canvas fingerprint with deterministic per-channel noise."""
    return f"""
(function() {{
    // Seeded PRNG (mulberry32)
    function mulberry32(a) {{
        return function() {{
            a |= 0; a = a + 0x6D2B79F5 | 0;
            var t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        }};
    }}
    var rng = mulberry32({seed});

    var origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {{
        var ctx = this.getContext('2d');
        if (ctx) {{
            var imageData = ctx.getImageData(0, 0, this.width, this.height);
            var data = imageData.data;
            for (var i = 0; i < data.length; i += 4) {{
                data[i]     = data[i]     + Math.floor((rng() - 0.5) * 2) | 0;
                data[i + 1] = data[i + 1] + Math.floor((rng() - 0.5) * 2) | 0;
                data[i + 2] = data[i + 2] + Math.floor((rng() - 0.5) * 2) | 0;
            }}
            ctx.putImageData(imageData, 0, 0);
        }}
        return origToDataURL.apply(this, arguments);
    }};

    var origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function() {{
        var imageData = origGetImageData.apply(this, arguments);
        var data = imageData.data;
        for (var i = 0; i < data.length; i += 4) {{
            data[i]     = data[i]     + Math.floor((rng() - 0.5) * 2) | 0;
            data[i + 1] = data[i + 1] + Math.floor((rng() - 0.5) * 2) | 0;
            data[i + 2] = data[i + 2] + Math.floor((rng() - 0.5) * 2) | 0;
        }}
        return imageData;
    }};
}})();
"""


_GPU_POOL = [
    ("Intel Inc.", "Intel Iris OpenGL Engine"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA GeForce GTX 1060)"),
    ("Google Inc. (AMD)", "ANGLE (AMD Radeon RX 580)"),
    ("Google Inc. (Intel)", "ANGLE (Intel UHD Graphics 630)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA GeForce RTX 3060)"),
    ("Google Inc. (AMD)", "ANGLE (AMD Radeon Pro 5500M)"),
]


def webgl_spoof_js(seed: int) -> str:
    """JS to spoof WebGL renderer/vendor with seed-based GPU selection."""
    idx = seed % len(_GPU_POOL)
    vendor, renderer = _GPU_POOL[idx]
    return f"""
(function() {{
    var origGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {{
        if (param === 0x1F00) return '{vendor}';
        if (param === 0x1F01) return '{renderer}';
        return origGetParameter.call(this, param);
    }};
    if (typeof WebGL2RenderingContext !== 'undefined') {{
        var origGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(param) {{
            if (param === 0x1F00) return '{vendor}';
            if (param === 0x1F01) return '{renderer}';
            return origGetParameter2.call(this, param);
        }};
    }}

    // Shuffle extensions based on seed
    function mulberry32(a) {{
        return function() {{
            a |= 0; a = a + 0x6D2B79F5 | 0;
            var t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        }};
    }}
    var rng = mulberry32({seed});

    var origGetExtensions = WebGLRenderingContext.prototype.getSupportedExtensions;
    WebGLRenderingContext.prototype.getSupportedExtensions = function() {{
        var exts = origGetExtensions.call(this);
        if (!exts) return exts;
        exts = exts.slice();
        for (var i = exts.length - 1; i > 0; i--) {{
            var j = Math.floor(rng() * (i + 1));
            var tmp = exts[i]; exts[i] = exts[j]; exts[j] = tmp;
        }}
        return exts;
    }};
}})();
"""


def audio_spoof_js(seed: int) -> str:
    """JS to spoof AudioContext fingerprint with sub-LSB noise."""
    return f"""
(function() {{
    function mulberry32(a) {{
        return function() {{
            a |= 0; a = a + 0x6D2B79F5 | 0;
            var t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        }};
    }}
    var rng = mulberry32({seed});

    if (typeof AnalyserNode !== 'undefined') {{
        var origGetFloat = AnalyserNode.prototype.getFloatFrequencyData;
        AnalyserNode.prototype.getFloatFrequencyData = function(array) {{
            origGetFloat.call(this, array);
            for (var i = 0; i < array.length; i++) {{
                array[i] = array[i] + (rng() - 0.5) * 0.0001;
            }}
        }};
    }}

    if (typeof AudioBuffer !== 'undefined') {{
        var origGetChannel = AudioBuffer.prototype.getChannelData;
        AudioBuffer.prototype.getChannelData = function(channel) {{
            var data = origGetChannel.call(this, channel);
            for (var i = 0; i < data.length; i++) {{
                data[i] = data[i] + (rng() - 0.5) * 0.0001;
            }}
            return data;
        }};
    }}
}})();
"""


_CORES_POOL = [2, 4, 8, 12, 16]
_MEMORY_POOL = [4, 8, 16, 32]


def hardware_spoof_js(cores: int | None = None, memory: int | None = None) -> str:
    """JS to spoof navigator.hardwareConcurrency and navigator.deviceMemory."""
    if cores is None:
        cores = random.choice(_CORES_POOL)
    if memory is None:
        memory = random.choice(_MEMORY_POOL)
    return f"""
(function() {{
    Object.defineProperty(navigator, 'hardwareConcurrency', {{
        get: function() {{ return {cores}; }}
    }});
    Object.defineProperty(navigator, 'deviceMemory', {{
        get: function() {{ return {memory}; }}
    }});
}})();
"""


_BASELINE_FONTS = [
    "Arial", "Arial Black", "Comic Sans MS", "Courier New", "Georgia",
    "Impact", "Lucida Console", "Lucida Sans Unicode", "Palatino Linotype",
    "Tahoma", "Times New Roman", "Trebuchet MS", "Verdana",
    "Segoe UI", "Helvetica", "Helvetica Neue", "Microsoft Sans Serif",
    "Gill Sans", "Calibri", "Cambria",
]


def font_mask_js() -> str:
    """JS to mask font enumeration to a baseline set of common fonts."""
    fonts_js = ", ".join(f"'{f}'" for f in _BASELINE_FONTS)
    return f"""
(function() {{
    var allowedFonts = new Set([{fonts_js}]);
    if (typeof FontFaceSet !== 'undefined' && FontFaceSet.prototype.check) {{
        var origCheck = FontFaceSet.prototype.check;
        FontFaceSet.prototype.check = function(font, text) {{
            var match = font.match(/[\\d.]+(?:px|pt|em|rem)\\s+(.*)/);
            if (match) {{
                var family = match[1].replace(/['"]/g, '').trim();
                if (!allowedFonts.has(family)) {{
                    return false;
                }}
            }}
            return origCheck.call(this, font, text);
        }};
    }}
}})();
"""
