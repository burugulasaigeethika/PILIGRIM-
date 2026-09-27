# Phase P.1 — Nearby Places Runtime Fix & Behavioral Certification

**Target Workspace**: `D:\pligrim ai new`  
**Phase**: Phase P.1 — Targeted Bug Fix  
**Date**: September 24, 2026  
**Status**: Certified & Verified

---

## 1. Executive Summary

During real browser testing of the PilgrimAI application (`http://127.0.0.1:8000`), clicking the "Nearby Places" tab or button failed to display nearby hotels, restaurants, or amenities for the selected temple (e.g., Yadagirigutta / Yadadri). Instead of displaying live places or an honest, actionable diagnostic message, the interface previously either displayed misleading zero results (*"No nearby hotels or restaurants found near Sri Lakshmi Narasimha Swamy Temple, Yadadri."*) or failed without explaining the exact cause.

Through comprehensive browser subagent tracing, live diagnostic hooks (`window.getPlacesDiagnostics()`), and mock behavioral testing, the exact root cause was identified:
1. **External Google Cloud Credential Configuration**: The browser Google Maps API key has HTTP referrer restrictions enabled but its **API Restrictions** in Google Cloud Console do not permit the **Places API** (returning `ApiTargetBlockedMapError` / `REQUEST_DENIED`).
2. **Frontend Error Swallowing Bug**: In `app.js`, the result-handling branch evaluated `(results && results.length === 0)` inside the `ZERO_RESULTS` condition, causing any non-OK status (including `REQUEST_DENIED`) that returned empty results to be masked as "No nearby hotels or restaurants found", completely concealing the API denial.
3. **Missing Actionable UX Feedback**: The UI had no distinct error banner for `REQUEST_DENIED`, `OVER_QUERY_LIMIT`, or `INVALID_REQUEST`, leaving users with zero explanation.

Both the frontend handling and diagnostic observability have now been completely resolved. The UI now displays a clear, styled diagnostic warning explaining that `REQUEST_DENIED` occurred and guides the administrator with the exact Google Cloud Console setting needed.

---

## 2. Complete Flow Inspection & Root Cause Analysis

### A. Full Execution Flow Traced:
1. **User Action**: User clicks the "Nearby Places" tab (`#tabPlacesBtn`) or clicks "Find Nearby Places" on an info-window.
2. **Event Dispatch**: Click handler activates `#tabPlacesBtn`, sets button text to `"Finding Places..."`, disables the button during search, and invokes `fetchNearbyPlaces(templeName, lat, lng, callback)`.
3. **Coordinate Verification**: Checks coordinates against valid geographic ranges `[-90, 90]` latitude and `[-180, 180]` longitude. If absent, falls back gracefully to Yadadri coordinates `(17.587714, 78.948325)`.
4. **Google Maps & Places Availability**:
   - `googleLoaded`: `typeof window.google !== "undefined"`
   - `mapsLoaded`: `!!(googleLoaded && window.google.maps)`
   - `placesLibraryLoaded`: `!!(mapsLoaded && window.google.maps.places)`
   - `placesServiceAvailable`: `!!(placesLibraryLoaded && window.google.maps.places.PlacesService)`
5. **PlacesService Creation**:
   - Instantiated as `new google.maps.places.PlacesService(mapContainer)`.
6. **Request Execution**:
   - `service.nearbySearch({ location: new google.maps.LatLng(lat, lng), radius: 5000, keyword: "hotels and restaurants" }, callback)`
7. **Callback Status & Handling**:
   - Google Maps JavaScript API returned `REQUEST_DENIED`.
   - Google API Console reported:
     `Places API error: ApiTargetBlockedMapError`
     `This API key is not authorized to use this service or API. Please check the API restrictions settings of your API key in the Google Cloud Console...`

---

## 3. Exact Root Causes Identified

### Root Cause 1: External Google Cloud Console API Key Restrictions (External Configuration)
- The Google Cloud project's browser key (`GOOGLE_MAPS_API_KEY`) is restricted to the **"Maps JavaScript API"**, but **"Places API"** has not been added to its allowed API list under API Restrictions.
- **Exact Action Required in Google Cloud Console**:
  1. Navigate to: **Google Cloud Console > APIs & Services > Credentials**
  2. Select the API key used for the browser (`GOOGLE_MAPS_API_KEY`).
  3. Under **API restrictions**, ensure **"Places API"** (and/or "Places API (New)") is checked/enabled.
  4. Save changes (changes propagate across Google's edge servers within 1–5 minutes).

### Root Cause 2: Frontend Result & Error Masking Bug (Code)
- `app.js` contained a conditional:
  ```javascript
  else if (status === google.maps.places.PlacesServiceStatus.ZERO_RESULTS || (results && results.length === 0))
  ```
- Because Google returns `results: []` or `results: null` alongside `status === "REQUEST_DENIED"`, this condition evaluated to `true`, swallowing the `REQUEST_DENIED` status and falsely claiming zero places were found!

---

## 4. Exact Files Changed

1. `backend/app/static/app.js`:
   - Added `window.getPlacesDiagnostics()` returning:
     - `googleLoaded` (boolean)
     - `mapsLoaded` (boolean)
     - `placesLibraryLoaded` (boolean)
     - `placesServiceAvailable` (boolean)
     - `selectedTemple` (string)
     - `selectedLatitude` (float)
     - `selectedLongitude` (float)
     - `requestStarted` (boolean)
     - `lastStatus` (string)
     - `lastResultCount` (number)
     - `lastError` (string or null)
   - Fixed `fetchNearbyPlaces` status handling:
     - Separated `OK` (with `results.length > 0`)
     - Separated `ZERO_RESULTS` (clean info notice)
     - Explicit handling for `REQUEST_DENIED` with actionable Google Cloud Console guidance
     - Explicit handling for `OVER_QUERY_LIMIT`, `INVALID_REQUEST`, `UNKNOWN_ERROR`, and `INVALID_COORDINATES`
   - Added button state feedback (`"Finding Places..."`) and enabled callback completion.
   - Smoothly scrolls places container into view when "Nearby Places" tab is clicked.

2. `backend/app/static/style.css`:
   - Added styles for `.places-error-banner`, `.places-error-title`, `.places-error-desc`, `.places-config-hint`, and `.places-zero-results` matching the dark glassmorphic design system.

3. `backend/app/static/index.html`:
   - Updated script tag version to `?v=2.3` to prevent aggressive browser caching.

4. `backend/app/main.py`:
   - Added `Cache-Control: no-cache, no-store, must-revalidate` response header on the root `/` endpoint to ensure browser clients always receive the latest assets.

5. `tests/test_phase_p1_places_runtime.py`:
   - Added dedicated behavioral test suite verifying all 15 Phase P.1 requirements.

6. `tests/harness_places_test.js`:
   - Created headless DOM mock test harness for validating `app.js` Places runtime behavior and callbacks.

---

## 5. Dedicated Phase P.1 Behavioral Tests (15/15 Passing)

| Test # | Test Name | Description | Status |
|:---:|:---|:---|:---:|
| 1 | `test_01_places_tab_click_handler_exists_and_triggers_discovery` | Verifies `#tabPlacesBtn` click attaches active state and starts request | **PASS** |
| 2 | `test_02_places_diagnostics_contract_schema` | Verifies `getPlacesDiagnostics()` exposes all 11 required contract fields | **PASS** |
| 3 | `test_03_google_maps_missing_state` | Verifies diagnostic flags when Google Maps SDK is absent | **PASS** |
| 4 | `test_04_places_library_missing_state` | Verifies diagnostic distinction when maps is loaded but Places library is missing | **PASS** |
| 5 | `test_05_selected_temple_missing_state_fallback` | Verifies fallback to Yadadri coordinates when no temple is explicitly passed | **PASS** |
| 6 | `test_06_invalid_coordinates_handled_safely` | Verifies invalid coordinates halt request and report `INVALID_COORDINATES` | **PASS** |
| 7 | `test_07_successful_nearbysearch_callback_renders_results` | Verifies `OK` callback renders place cards into DOM | **PASS** |
| 8 | `test_08_zero_results_callback_renders_clean_notice` | Verifies `ZERO_RESULTS` renders clean notice without error styling | **PASS** |
| 9 | `test_09_request_denied_callback_renders_actionable_banner` | Verifies `REQUEST_DENIED` renders banner with Google Cloud Console instructions | **PASS** |
| 10 | `test_10_invalid_request_callback_handling` | Verifies `INVALID_REQUEST` updates diagnostics and renders error message | **PASS** |
| 11 | `test_11_unknown_error_callback_handling` | Verifies `UNKNOWN_ERROR` updates diagnostics and renders server retry message | **PASS** |
| 12 | `test_12_results_rendered_with_provenance` | Verifies DOM contains `"Live Google Places Results"` badge | **PASS** |
| 13 | `test_13_no_api_key_leakage_in_frontend` | Verifies zero hardcoded Google API keys (`AIzaSy`) in static files | **PASS** |
| 14 | `test_14_no_server_routes_key_in_frontend` | Verifies `/api/maps/config` never exposes `GOOGLE_ROUTES_API_KEY` | **PASS** |
| 15 | `test_15_temple_json_files_data_integrity` | Verifies all 417 source temple JSON files match SHA-256 hashes | **PASS** |

---

## 6. Dataset Integrity & Hard Boundary Verification

- **417 Source Temple JSON Files**: **417/417 Unchanged** (100% SHA-256 hash match against baseline).
- `qdrant_db/`: **Unchanged**
- `bm25_index/`: **Unchanged**
- `evaluation/`: **Unchanged**
- `backend/app/rag/`: **Unchanged**
- **Credential Isolation**:
  - `GOOGLE_ROUTES_API_KEY`: Server-side only (never sent to client)
  - `GOOGLE_MAPS_API_KEY`: Browser client only
  - Zero raw secrets printed or exposed in diagnostics.
