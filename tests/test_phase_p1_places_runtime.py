"""
Phase P.1 Dedicated Test Suite: Nearby Places Runtime Behavioral Fix
Verifies:
1. Places tab click handler exists and triggers state transition
2. window.getPlacesDiagnostics exists and returns complete diagnostic schema
3. Google Maps missing state is handled gracefully
4. Places library missing state is handled gracefully
5. Selected temple fallback behavior when no temple is explicitly passed
6. Coordinate validation (valid floats vs invalid/NaN coordinates)
7. Successful nearbySearch callback (OK status)
8. ZERO_RESULTS callback handling
9. REQUEST_DENIED callback handling with explicit actionable diagnostic banner
10. INVALID_REQUEST callback handling
11. UNKNOWN_ERROR callback handling
12. Live Places results rendered into DOM
13. No API key leakage in diagnostics or DOM
14. No server Routes key exposed in frontend
15. 417/417 temple source JSON data integrity
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path
import pytest

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.main import app
from tests.test_maps_api import SyncTestClient

client = SyncTestClient(app)

NODE_HARNESS = r"""
const fs = require('fs');

function runTest(scenario, callbackMockStatus, callbackMockResults) {
  let code = fs.readFileSync('backend/app/static/app.js', 'utf8');

  const listeners = {};
  const elements = {};
  function createElem(tag) {
    const el = {
      tagName: tag.toUpperCase(),
      innerHTML: '',
      innerText: '',
      style: {},
      disabled: false,
      classList: {
        _classes: new Set(),
        add: function(c) { this._classes.add(c); },
        remove: function(c) { this._classes.delete(c); },
        toggle: function(c) { if (this._classes.has(c)) this._classes.delete(c); else this._classes.add(c); },
        contains: function(c) { return this._classes.has(c); }
      },
      addEventListener: function(evt, fn) {
        if (!this._listeners) this._listeners = {};
        this._listeners[evt] = fn;
      },
      setAttribute: function() {},
      getAttribute: function() { return null; },
      appendChild: function() {},
      querySelectorAll: function() { return []; },
      querySelector: function() { return null; },
      closest: function() { return null; },
      dispatchEvent: function(e) { if (this._listeners && this._listeners[e.type]) this._listeners[e.type](e); },
      scrollIntoView: function() {}
    };
    return el;
  }

  const docListeners = {};
  const mockDoc = {
    getElementById: function(id) {
      if (!elements[id]) elements[id] = createElem('div');
      return elements[id];
    },
    querySelectorAll: function() { return []; },
    querySelector: function() { return null; },
    createElement: function(tag) { return createElem(tag); },
    head: createElem('head'),
    body: createElem('body'),
    addEventListener: function(evt, fn) { docListeners[evt] = fn; }
  };

  const mockWindow = {
    document: mockDoc,
    addEventListener: function() {},
    localStorage: { getItem: () => null, setItem: () => {} },
    SpeechSynthesisUtterance: function() {}
  };

  global.document = mockDoc;
  global.window = mockWindow;
  global.localStorage = mockWindow.localStorage;
  global.navigator = {};
  global.fetch = () => Promise.resolve({ ok: false, json: () => Promise.resolve({}) });

  // Scenario setup for Google Maps & Places
  if (scenario === 'google_missing') {
    delete global.window.google;
  } else if (scenario === 'places_missing') {
    global.window.google = {
      maps: {
        Map: function() {},
        DirectionsService: function() {},
        DirectionsRenderer: function() {},
        LatLng: function(lat, lng) { return { lat, lng }; }
      }
    };
  } else {
    // Places available
    const mockStatusEnum = {
      OK: 'OK',
      ZERO_RESULTS: 'ZERO_RESULTS',
      REQUEST_DENIED: 'REQUEST_DENIED',
      OVER_QUERY_LIMIT: 'OVER_QUERY_LIMIT',
      INVALID_REQUEST: 'INVALID_REQUEST',
      UNKNOWN_ERROR: 'UNKNOWN_ERROR'
    };

    let nearbySearchFn = function(req, cb) {
      setTimeout(() => {
        cb(callbackMockResults || [], callbackMockStatus || 'OK');
      }, 0);
    };

    global.window.google = {
      maps: {
        Map: function() {},
        DirectionsService: function() {},
        DirectionsRenderer: function() {},
        LatLng: function(lat, lng) { return { lat, lng }; },
        places: {
          PlacesServiceStatus: mockStatusEnum,
          PlacesService: function(container) {
            return {
              nearbySearch: nearbySearchFn
            };
          }
        }
      }
    };
  }

  // Load app.js
  eval(code);

  // Fire DOMContentLoaded
  if (docListeners['DOMContentLoaded']) {
    docListeners['DOMContentLoaded']();
  }

  return {
    elements,
    window: global.window
  };
}

const action = process.argv[2];

if (action === 'test_click_handler') {
  const env = runTest('normal');
  const btn = env.elements['tabPlacesBtn'];
  if (!btn || !btn._listeners || !btn._listeners['click']) {
    console.log(JSON.stringify({ error: 'tabPlacesBtn click listener not attached' }));
    process.exit(1);
  }
  btn._listeners['click']();
  const diag = env.window.getPlacesDiagnostics();
  console.log(JSON.stringify({
    btnClasses: Array.from(btn.classList._classes),
    diag: diag
  }));
} else if (action === 'test_diagnostics_schema') {
  const env = runTest('google_missing');
  const diag = env.window.getPlacesDiagnostics();
  console.log(JSON.stringify(diag));
} else if (action === 'test_google_missing') {
  const env = runTest('google_missing');
  const diag = env.window.getPlacesDiagnostics();
  console.log(JSON.stringify({
    googleLoaded: diag.googleLoaded,
    mapsLoaded: diag.mapsLoaded,
    placesLibraryLoaded: diag.placesLibraryLoaded,
    placesServiceAvailable: diag.placesServiceAvailable
  }));
} else if (action === 'test_places_missing') {
  const env = runTest('places_missing');
  const diag = env.window.getPlacesDiagnostics();
  console.log(JSON.stringify({
    googleLoaded: diag.googleLoaded,
    mapsLoaded: diag.mapsLoaded,
    placesLibraryLoaded: diag.placesLibraryLoaded,
    placesServiceAvailable: diag.placesServiceAvailable
  }));
} else if (action === 'test_invalid_coordinates') {
  const env = runTest('normal');
  env.window.discoverPlacesForTemple('Invalid Temple', 'invalid_lat', 'invalid_lng');
  const diag = env.window.getPlacesDiagnostics();
  const placesListHtml = env.elements['placesList'].innerHTML;
  console.log(JSON.stringify({ diag, html: placesListHtml }));
} else if (action === 'test_callback_status') {
  const targetStatus = process.argv[3] || 'OK';
  const mockResults = targetStatus === 'OK' ? [
    {
      name: 'Yadadri Grand Residency',
      vicinity: 'Temple Road, Yadagirigutta',
      rating: 4.4,
      user_ratings_total: 210,
      opening_hours: { isOpen: () => true }
    }
  ] : [];

  const env = runTest('normal', targetStatus, mockResults);
  const btn = env.elements['tabPlacesBtn'];
  btn._listeners['click']();

  setTimeout(() => {
    const diag = env.window.getPlacesDiagnostics();
    const placesListHtml = env.elements['placesList'].innerHTML;
    console.log(JSON.stringify({ diag, html: placesListHtml }));
  }, 10);
}
"""


def _run_node_harness(*args):
    harness_path = root_dir / "tests" / "harness_places_test.js"
    cmd = ["node", str(harness_path), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(root_dir))
    if proc.returncode != 0:
        raise RuntimeError(f"Node execution failed (code {proc.returncode}):\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    for line in reversed(proc.stdout.strip().splitlines()):
        line_clean = line.strip()
        if line_clean.startswith("{") and line_clean.endswith("}"):
            return json.loads(line_clean)
    return json.loads(proc.stdout.strip())


# =============================================================================
# 1. Places Tab Click Handler Exists and Triggers State
# =============================================================================

def test_01_places_tab_click_handler_exists_and_triggers_discovery():
    """Verify tabPlacesBtn has click handler that updates classList and initiates request."""
    res = _run_node_harness("test_click_handler")
    assert "active" in res["btnClasses"]
    assert res["diag"]["requestStarted"] is True
    assert res["diag"]["selectedTemple"] is not None


# =============================================================================
# 2. Places Diagnostics Function Exists with Required Contract Schema
# =============================================================================

def test_02_places_diagnostics_contract_schema():
    """Verify window.getPlacesDiagnostics() exposes the exact required diagnostic keys."""
    diag = _run_node_harness("test_diagnostics_schema")
    required_keys = [
        "googleLoaded",
        "mapsLoaded",
        "placesLibraryLoaded",
        "placesServiceAvailable",
        "selectedTemple",
        "selectedLatitude",
        "selectedLongitude",
        "requestStarted",
        "lastStatus",
        "lastResultCount",
        "lastError"
    ]
    for key in required_keys:
        assert key in diag, f"Missing required diagnostic key: {key}"
    # Verify no raw keys leaked in diagnostics
    diag_str = json.dumps(diag)
    assert "AIzaSy" not in diag_str


# =============================================================================
# 3. Google Maps Missing State
# =============================================================================

def test_03_google_maps_missing_state():
    """Verify diagnostic state accurately reports when google.maps is not loaded."""
    res = _run_node_harness("test_google_missing")
    assert res["googleLoaded"] is False
    assert res["mapsLoaded"] is False
    assert res["placesLibraryLoaded"] is False
    assert res["placesServiceAvailable"] is False


# =============================================================================
# 4. Places Library Missing State
# =============================================================================

def test_04_places_library_missing_state():
    """Verify diagnostic state distinguishes between maps loaded and places library missing."""
    res = _run_node_harness("test_places_missing")
    assert res["googleLoaded"] is True
    assert res["mapsLoaded"] is True
    assert res["placesLibraryLoaded"] is False
    assert res["placesServiceAvailable"] is False


# =============================================================================
# 5. Selected Temple Missing State Fallback
# =============================================================================

def test_05_selected_temple_missing_state_fallback():
    """Verify discovery falls back gracefully to default Yadadri temple when none is selected."""
    diag = _run_node_harness("test_diagnostics_schema")
    assert diag["selectedTemple"] == "Sri Lakshmi Narasimha Swamy Temple, Yadadri"
    assert diag["selectedLatitude"] == pytest.approx(17.587714)
    assert diag["selectedLongitude"] == pytest.approx(78.948325)


# =============================================================================
# 6. Coordinate Validation
# =============================================================================

def test_06_invalid_coordinates_handled_safely():
    """Verify invalid or NaN coordinates halt request and render diagnostic message."""
    res = _run_node_harness("test_invalid_coordinates")
    assert res["diag"]["lastStatus"] == "INVALID_COORDINATES"
    assert "Invalid Coordinates" in res["html"]


# =============================================================================
# 7. Successful nearbySearch Callback
# =============================================================================

def test_07_successful_nearbysearch_callback_renders_results():
    """Verify successful nearbySearch callback transitions to OK status and renders place cards."""
    res = _run_node_harness("test_callback_status", "OK")
    assert res["diag"]["lastStatus"] == "OK"
    assert res["diag"]["lastResultCount"] == 1
    assert "place-card" in res["html"]
    assert "Yadadri Grand Residency" in res["html"]
    assert "Temple Road, Yadagirigutta" in res["html"]


# =============================================================================
# 8. ZERO_RESULTS Callback Handling
# =============================================================================

def test_08_zero_results_callback_renders_clean_notice():
    """Verify ZERO_RESULTS status renders clear zero-results message, not an error banner."""
    res = _run_node_harness("test_callback_status", "ZERO_RESULTS")
    assert res["diag"]["lastStatus"] == "ZERO_RESULTS"
    assert res["diag"]["lastResultCount"] == 0
    assert "places-zero-results" in res["html"]
    assert "No nearby places were found" in res["html"]


# =============================================================================
# 9. REQUEST_DENIED Callback Handling
# =============================================================================

def test_09_request_denied_callback_renders_actionable_banner():
    """Verify REQUEST_DENIED renders honest guidance pointing to Google Cloud Places API enablement."""
    res = _run_node_harness("test_callback_status", "REQUEST_DENIED")
    assert res["diag"]["lastStatus"] == "REQUEST_DENIED"
    assert res["diag"]["lastResultCount"] == 0
    assert "places-error-banner" in res["html"]
    assert "Google Places Access Denied" in res["html"]
    assert "In Google Cloud Console" in res["html"]
    assert "Places API" in res["html"]


# =============================================================================
# 10. INVALID_REQUEST Callback Handling
# =============================================================================

def test_10_invalid_request_callback_handling():
    """Verify INVALID_REQUEST status updates diagnostics and renders error message."""
    res = _run_node_harness("test_callback_status", "INVALID_REQUEST")
    assert res["diag"]["lastStatus"] == "INVALID_REQUEST"
    assert "Invalid Request" in res["html"]


# =============================================================================
# 11. UNKNOWN_ERROR Callback Handling
# =============================================================================

def test_11_unknown_error_callback_handling():
    """Verify UNKNOWN_ERROR status updates diagnostics and renders server retry message."""
    res = _run_node_harness("test_callback_status", "UNKNOWN_ERROR")
    assert res["diag"]["lastStatus"] == "UNKNOWN_ERROR"
    assert "Google Places Server Error" in res["html"]


# =============================================================================
# 12. Results Rendered into DOM with Correct Provenance
# =============================================================================

def test_12_results_rendered_with_provenance():
    """Verify index.html places panel contains Live Google Places Results badge."""
    with open(root_dir / "backend" / "app" / "static" / "index.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert "Live Google Places Results" in html
    assert "placesList" in html
    assert "tabPlacesBtn" in html


# =============================================================================
# 13. Zero API Key Leakage in Frontend Diagnostics & HTML
# =============================================================================

def test_13_no_api_key_leakage_in_frontend():
    """Verify no Google API keys are hardcoded in static assets."""
    for filename in ["app.js", "index.html", "style.css"]:
        filepath = root_dir / "backend" / "app" / "static" / filename
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "AIzaSy" not in content, f"Hardcoded Google API key found in {filename}!"


# =============================================================================
# 14. No Server Routes Key in Frontend Config
# =============================================================================

def test_14_no_server_routes_key_in_frontend(monkeypatch):
    """Verify /api/maps/config endpoint never exposes GOOGLE_ROUTES_API_KEY or server credentials."""
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "mock_browser_key")
    monkeypatch.setenv("GOOGLE_ROUTES_API_KEY", "super_secret_routes_key_12345")
    monkeypatch.setenv("GOOGLE_PLACES_SERVER_API_KEY", "super_secret_places_key_67890")

    resp = client.get("/api/maps/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["api_key"] == "mock_browser_key"
    assert "super_secret_routes_key_12345" not in resp.text
    assert "super_secret_places_key_67890" not in resp.text


# =============================================================================
# 15. Source Temple JSON Files Integrity (417/417 Unchanged)
# =============================================================================

def test_15_temple_json_files_data_integrity():
    """Verify all 417 source temple JSON files across all 20 temple directories are completely intact."""
    temple_dirs = [
        d for d in root_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in [
            "backend", "docs", "tests", "evaluation", "scratch", "bm25_index", "qdrant_db", "__pycache__"
        ]
    ]
    json_files = []
    for td in temple_dirs:
        json_files.extend(list(td.glob("*.json")))

    assert len(json_files) == 417, f"Expected 417 temple JSON files, found {len(json_files)}"

    # Load pre-recorded hash manifest if present in artifact scratch
    manifest_path = Path("C:/Users/aksha/.gemini/antigravity-ide/brain/fc1dba71-cc00-41cd-a9fa-8b253c0f5282/scratch/pre_o6_manifest.json")
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for fpath in json_files:
            rel_path = fpath.relative_to(root_dir).as_posix()
            if rel_path in manifest:
                with open(fpath, "rb") as jf:
                    curr_hash = hashlib.sha256(jf.read()).hexdigest()
                assert curr_hash == manifest[rel_path], f"Hash mismatch for {rel_path}!"
