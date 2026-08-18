/* Platform Pulse - frontend
 *
 * The server refreshes MTA data every 30s. The browser ticks countdowns down
 * every second in between, so numbers slide rather than jump - the same trick
 * train_widget.py used with its QTimer.
 *
 * Arrival times come back as absolute epoch seconds plus the server's own
 * clock, so a browser whose clock is off by a few minutes still counts down
 * correctly.
 */

(function () {
  'use strict';

  var FETCH_MS = 30000;
  var TICK_MS = 1000;
  var TRACK_WINDOW_S = 1200;  // 20 minutes of visible approach, per the widget
  var GLOW_S = 120;           // glow under 2 minutes, per the widget
  var STALE_MS = 90000;

  var el = {
    body: document.body,
    statusLabel: document.getElementById('status-label'),
    clock: document.getElementById('clock'),
    heroBody: document.getElementById('hero-body'),
    stations: document.getElementById('stations'),
    notice: document.getElementById('notice'),
    refreshNote: document.getElementById('refresh-note')
  };

  var state = {
    stations: [],
    skew: 0,            // server clock minus browser clock, in seconds
    lastFetchOk: 0,
    failures: 0,
    rows: [],           // live DOM handles, updated in place each tick
    hero: null,
    heroKey: null
  };

  // ------------------------------------------------------------- helpers

  function now() {
    return Date.now() / 1000 + state.skew;
  }

  function secondsAway(arrival) {
    return arrival.arrival_epoch - now();
  }

  function pad(n) {
    return n < 10 ? '0' + n : String(n);
  }

  /** Hero reads like a platform clock: 6:04, counting every second. */
  function clockFormat(seconds) {
    if (seconds <= 0) return { value: 'Now', word: true };
    if (seconds < 60) return { value: '0:' + pad(Math.floor(seconds)), word: false };
    var m = Math.floor(seconds / 60);
    var s = Math.floor(seconds % 60);
    if (m >= 60) return { value: Math.floor(m / 60) + 'h ' + (m % 60) + 'm', word: true };
    return { value: m + ':' + pad(s), word: false };
  }

  /** Rows read like the original board: "6 min". */
  function minutesFormat(seconds) {
    if (seconds <= 0) return { value: 'Now', unit: '' };
    if (seconds < 60) return { value: '<1', unit: 'min' };
    return { value: String(Math.floor(seconds / 60)), unit: 'min' };
  }

  /** Same thresholds train_board.py used for its urgency colours. */
  function urgency(seconds) {
    if (seconds <= 60) return 'is-now';
    if (seconds <= 300) return 'is-soon';
    return 'is-ok';
  }

  function bullet(arrival, size) {
    var b = document.createElement('span');
    b.className = 'bullet' + (size ? ' ' + size : '') + (arrival.dark_text ? ' is-dark-text' : '');
    b.style.background = arrival.color;
    b.style.color = arrival.dark_text ? '#0A0B0D' : '#fff';
    b.textContent = arrival.route;
    b.setAttribute('aria-label', arrival.route + ' train');
    return b;
  }

  function lineBullet(route, color, darkText) {
    var b = document.createElement('span');
    b.className = 'bullet' + (darkText ? ' is-dark-text' : '');
    b.style.background = color;
    b.textContent = route;
    return b;
  }

  // ------------------------------------------------------------- render

  function allArrivals() {
    var out = [];
    state.stations.forEach(function (station) {
      (station.arrivals || []).forEach(function (a) {
        out.push({ arrival: a, station: station });
      });
    });
    out.sort(function (x, y) {
      return x.arrival.arrival_epoch - y.arrival.arrival_epoch;
    });
    return out;
  }

  function renderHero() {
    var soonest = allArrivals()[0];
    el.heroBody.innerHTML = '';
    state.hero = null;

    if (!soonest) {
      state.heroKey = null;
      var blank = document.createElement('div');
      blank.className = 'hero-skeleton';
      blank.textContent = 'No trains reported at either station right now.';
      el.heroBody.appendChild(blank);
      return;
    }

    var a = soonest.arrival;
    state.heroKey = a.train_id + a.arrival_epoch;

    var main = document.createElement('div');
    main.className = 'hero-main';

    var bul = bullet(a, 'bullet-lg');

    var dest = document.createElement('div');
    dest.className = 'hero-dest';
    var dir = document.createElement('div');
    dir.className = 'hero-dir';
    dir.textContent = a.direction_label;
    var head = document.createElement('div');
    head.className = 'hero-headsign';
    head.textContent = a.headsign
      ? a.headsign + '  \u00b7  ' + soonest.station.name
      : soonest.station.name;
    dest.appendChild(dir);
    dest.appendChild(head);

    var count = document.createElement('div');
    count.className = 'hero-count';

    main.appendChild(bul);
    main.appendChild(dest);
    main.appendChild(count);

    var track = document.createElement('div');
    track.className = 'track';
    var rail = document.createElement('div');
    rail.className = 'track-rail';
    var progress = document.createElement('div');
    progress.className = 'track-progress';
    var train = document.createElement('div');
    train.className = 'track-train';
    rail.appendChild(progress);
    rail.appendChild(train);

    var ends = document.createElement('div');
    ends.className = 'track-ends';
    var left = document.createElement('span');
    left.textContent = a.direction_label + ' ' + a.route;
    var right = document.createElement('span');
    right.textContent = soonest.station.name;
    ends.appendChild(left);
    ends.appendChild(right);

    track.appendChild(rail);
    track.appendChild(ends);

    el.heroBody.appendChild(main);
    el.heroBody.appendChild(track);

    state.hero = {
      arrival: a,
      count: count,
      bullet: bul,
      progress: progress,
      train: train
    };
  }

  function renderStations() {
    el.stations.innerHTML = '';
    state.rows = [];

    state.stations.forEach(function (station) {
      var section = document.createElement('section');
      section.className = 'station';

      var head = document.createElement('div');
      head.className = 'station-head';

      var name = document.createElement('h2');
      name.className = 'station-name';
      name.textContent = station.name;

      var lines = document.createElement('div');
      lines.className = 'station-lines';
      (station.lines || []).forEach(function (route) {
        var sample = (station.arrivals || []).filter(function (a) {
          return a.route === route;
        })[0];
        lines.appendChild(lineBullet(
          route,
          sample ? sample.color : '#6E7681',
          sample ? sample.dark_text : false
        ));
      });

      head.appendChild(name);
      head.appendChild(lines);
      section.appendChild(head);

      if (!station.arrivals || !station.arrivals.length) {
        var empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = 'No trains reported here right now.';
        section.appendChild(empty);
      } else {
        var list = document.createElement('ul');
        list.className = 'arrivals';

        station.arrivals.forEach(function (a) {
          var li = document.createElement('li');
          li.className = 'arrival';

          var bul = bullet(a);

          var dest = document.createElement('div');
          dest.className = 'arrival-dest';
          var dir = document.createElement('div');
          dir.className = 'arrival-dir';
          dir.textContent = a.direction_label;
          var head2 = document.createElement('div');
          head2.className = 'arrival-headsign';
          head2.textContent = a.headsign || '\u2014';
          dest.appendChild(dir);
          dest.appendChild(head2);

          var count = document.createElement('div');
          count.className = 'arrival-count';

          li.appendChild(bul);
          li.appendChild(dest);
          li.appendChild(count);
          list.appendChild(li);

          state.rows.push({ arrival: a, node: li, count: count, bullet: bul });
        });

        section.appendChild(list);
      }

      el.stations.appendChild(section);
    });
  }

  // ------------------------------------------------------------- tick

  function tick() {
    var t = new Date();
    el.clock.textContent = t.toLocaleTimeString([], {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    el.clock.setAttribute('datetime', t.toISOString());

    var expired = false;

    // hero
    if (state.hero) {
      var hs = secondsAway(state.hero.arrival);
      var f = clockFormat(hs);
      state.hero.count.textContent = f.value;
      state.hero.count.className = 'hero-count ' + urgency(hs) + (f.word ? ' is-word' : '');

      var frac = Math.max(0, Math.min(1, 1 - hs / TRACK_WINDOW_S));
      state.hero.progress.style.width = (frac * 100) + '%';
      state.hero.train.style.left = (frac * 100) + '%';
      state.hero.train.classList.toggle('is-close', hs <= GLOW_S);
      state.hero.bullet.classList.toggle('is-imminent', hs <= GLOW_S);

      document.title = (hs <= 0 ? 'Now' : f.value) + ' \u00b7 ' +
        state.hero.arrival.route + ' \u00b7 Platform Pulse';

      if (hs < -60) expired = true;
    } else {
      document.title = 'Platform Pulse';
    }

    // rows
    state.rows.forEach(function (row) {
      var s = secondsAway(row.arrival);
      var f = minutesFormat(s);
      row.count.textContent = '';
      row.count.appendChild(document.createTextNode(f.value));
      if (f.unit) {
        var u = document.createElement('span');
        u.className = 'unit';
        u.textContent = f.unit;
        row.count.appendChild(u);
      }
      row.count.className = 'arrival-count ' + urgency(s);
      row.bullet.classList.toggle('is-imminent', s <= GLOW_S);
      if (s < -60) expired = true;
    });

    // a departed train should leave the board without waiting for the next fetch
    if (expired) prune();

    if (state.lastFetchOk && Date.now() - state.lastFetchOk > STALE_MS) {
      el.body.classList.add('is-stale');
      el.body.classList.remove('is-live');
      el.statusLabel.textContent = 'Reconnecting';
    }
  }

  function prune() {
    state.stations.forEach(function (station) {
      station.arrivals = (station.arrivals || []).filter(function (a) {
        return secondsAway(a) >= -60;
      });
    });
    renderHero();
    renderStations();
  }

  // ------------------------------------------------------------- fetch

  function setNotice(message, kind) {
    if (!message) {
      el.notice.hidden = true;
      return;
    }
    el.notice.hidden = false;
    el.notice.textContent = message;
    el.notice.className = 'notice' + (kind === 'info' ? ' is-info' : '');
  }

  function load() {
    fetch('/api/arrivals', { cache: 'no-store' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (data.server_now) state.skew = data.server_now - Date.now() / 1000;
        if (data.refresh_seconds) el.refreshNote.textContent = data.refresh_seconds;

        state.stations = data.stations || [];
        state.lastFetchOk = Date.now();
        state.failures = 0;

        el.body.classList.add('is-live');
        el.body.classList.remove('is-down', 'is-stale');
        el.statusLabel.textContent = data.demo ? 'Demo data' : 'Live';

        if (data.error) {
          setNotice('The MTA feed returned an error. Showing the last data received.', 'info');
        } else if (data.demo) {
          setNotice('Demo mode - these trains are made up.', 'info');
        } else {
          setNotice(null);
        }

        renderHero();
        renderStations();
      })
      .catch(function () {
        state.failures += 1;
        el.body.classList.add('is-down');
        el.body.classList.remove('is-live');
        el.statusLabel.textContent = 'Offline';
        setNotice(
          'Couldn\u2019t reach the arrivals feed. Trying again in ' +
          (FETCH_MS / 1000) + ' seconds.'
        );
      });
  }

  // ------------------------------------------------------------- boot

  load();
  tick();
  setInterval(tick, TICK_MS);
  setInterval(load, FETCH_MS);

  // a phone waking from sleep should show fresh numbers immediately
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) load();
  });
})();
