1 — sieve_pixels (clean small patches)
This step works on the raster before polygonization. It looks for small, isolated clumps of pixels and removes any that have fewer pixels than the threshold you set. That’s useful for wiping out tiny speckles or noise that aren’t meaningful objects and would otherwise become thousands of tiny polygons.

Example: with 0.2 m pixels, each pixel covers 0.04 m².
sieve_pixels: 25 → drops any patch smaller than 25 × 0.04 m² = 1 m².
sieve_pixels: 100 → drops patches smaller than 4 m².

2 — simplify_tolerance (smooth polygon edges)
After converting the raster into polygons, boundaries often follow a “stair-step” pattern along pixel edges. simplify_tolerance smooths those jagged edges by generalizing the geometry, which reduces vertex count and file size. The value is in map units (e.g. metres), so with a 0.2 m pixel size you might start with 0.2 – 0.5 m to gently smooth edges, or go up to 1–2 m if you want lighter, simpler polygons. Too-high values (like 5 m) can noticeably change narrow features such as paths or strips of vegetation.


3 — How they work together
Think of sieve_pixels as deciding which small blobs disappear entirely, while simplify_tolerance decides how wiggly the edges of the remaining blobs are. A typical workflow is to first sieve out speckle-noise patches (e.g. under 1 m²), then apply a modest simplification (e.g. 0.5 m) to make the surviving polygons cleaner and the GeoPackage smaller without losing important detail.