const fs = require('fs');
const path = require('path');

function runTest(scenario, callbackMockStatus, callbackMockResults) {
  const appJsPath = path.resolve(__dirname, '..', 'backend', 'app', 'static', 'app.js');
  let code = fs.readFileSync(appJsPath, 'utf8');

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
      // Synchronous callback for reliable testing
      cb(callbackMockResults || [], callbackMockStatus || 'OK');
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

  global.google = global.window.google;

  // Execute app.js in global context
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
    console.error('tabPlacesBtn click listener not attached');
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

  const diag = env.window.getPlacesDiagnostics();
  const placesListHtml = env.elements['placesList'].innerHTML;
  console.log(JSON.stringify({ diag, html: placesListHtml }));
}
