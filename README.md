# MSDS Substation Monitor — Backend

A Node.js backend that acts as a **Modbus TCP client** to an ABB RTU560
(the Modbus TCP **server**), reads substation electrical parameters,
stores them in SQLite, and exposes them over a REST API and a WebSocket
for real-time push — for the MSDS Substation Monitor dashboard.

> **Where this fits:** the dashboard frontend (in `public/`, and also
> published separately as a standalone artifact) currently generates its
> own simulated placeholder data client-side. This backend is a
> self-contained, independently runnable service that does the real job —
> talking Modbus to the RTU560, persisting readings, and serving them over
> HTTP/WebSocket — ready for the frontend to be pointed at it. Wiring the
> frontend's data layer to call this API instead of simulating is the
> natural next step once you're ready to go live; this backend works and
> can be exercised on its own (via `curl`, a WebSocket client, or your own
> frontend) whether or not that rewire has happened yet.

## Architecture

```
┌─────────────┐   Modbus TCP    ┌──────────────────┐
│  ABB RTU560 │◄────(client)────│  modbusClient.js │
│ (TCP server)│  fn code 4      │  (this app is the│
└─────────────┘  read input     │   Modbus CLIENT) │
                  registers     └─────────┬────────┘
                                          │ readFloat()
                                          ▼
                                ┌──────────────────────┐
                                │ telemetryService.js   │  polls every substation/
                                │ (poll loop, in-memory │  parameter on an interval,
                                │  snapshot + history)  │  never blocks on failures
                                └───────┬───────┬───────┘
                                        │       │
                          persists      │       │  emits 'snapshot'
                                        ▼       ▼
                              ┌────────────┐  ┌───────────────┐
                              │  SQLite    │  │  WebSocket     │
                              │ (readings, │  │  server (push  │
                              │ overrides, │  │  live updates) │
                              │ feeder     │  └───────┬───────┘
                              │ flags)     │          │
                              └─────┬──────┘          │
                                    │                 │
                                    ▼                 ▼
                          ┌────────────────────────────────┐
                          │   Express REST API (/api/...)   │
                          │   + static frontend (/public)   │
                          └────────────────────────────────┘
```

Key design point: **the app starts and stays fully functional even if the
RTU560 is unreachable.** `modbusClient.start()` never blocks and never
throws — it retries the TCP connection in the background with a capped
exponential backoff, and every register read returns `{ ok: false }`
rather than throwing when there's no connection, so the poll loop, the
API, and the WebSocket server keep running and simply report substations
as offline / readings as unavailable until the RTU560 answers.

## Folder structure

```
msds-backend/
├── .env.example              # copy to .env and fill in real values
├── .gitignore
├── .vscode/
│   ├── launch.json           # F5 to run/debug in VS Code
│   └── settings.json
├── config/
│   └── registerMap.example.json   # copy to registerMap.json
├── data/                      # SQLite file lives here (created automatically)
├── public/                    # static dashboard frontend (served as-is)
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── src/
│   ├── server.js              # entry point — wires everything together
│   ├── config/
│   │   └── config.js          # loads/validates .env + register map JSON
│   ├── modbus/
│   │   ├── modbusClient.js    # resilient Modbus TCP client (the driver)
│   │   └── registerMap.js     # register-map lookups + saved overrides
│   ├── db/
│   │   ├── database.js        # SQLite connection + schema
│   │   └── telemetryRepository.js  # all SQL lives here
│   ├── services/
│   │   └── telemetryService.js # polling loop, in-memory snapshot/history
│   ├── routes/
│   │   └── api.js             # REST endpoints
│   ├── ws/
│   │   └── wsServer.js        # WebSocket push
│   └── utils/
│       └── logger.js
└── package.json
```

## Prerequisites

- [Node.js](https://nodejs.org) 18 or newer (`node --version`)
- npm (comes with Node.js)
- Network access from wherever this runs to the RTU560's Modbus TCP port
  (default 502) — or just run it with no RTU560 present at all; see below.

## Setup

```bash
# 1. Install dependencies
npm install

# 2. Create your local environment file from the example
cp .env.example .env

# 3. Create your local register map from the example
cp config/registerMap.example.json config/registerMap.json
```

Now open `.env` and replace the placeholder values — **`MODBUS_HOST` in
particular is an example (`192.0.2.10`), not a real address** — with the
real ABB RTU560 IP address, port, and unit ID for your site. Open
`config/registerMap.json` and replace the example register addresses,
per-substation unit IDs, and scaling factors with the real values from the
RTU560's Modbus point-mapping export. Both files are already git-ignored
so your real site configuration never accidentally gets committed.

### Running without an RTU560 at all

You do not need a working Modbus connection to run this project. Leave
`.env` and `registerMap.json` as copied from the examples (or point
`MODBUS_HOST` at any address) and start the server as normal — every
substation will simply report `status: "offline"` and `value: null` for
every parameter until a real RTU560 answers, exactly as it would in the
field if the RTU560 were powered off. Nothing crashes or hangs.

## Running

```bash
npm start
```

You should see log lines similar to:

```
[...] [INFO] [database] SQLite database ready at .../data/telemetry.db
[...] [INFO] [modbusClient] Attempting to connect to Modbus TCP server at 192.0.2.10:502 ...
[...] [INFO] [wsServer] WebSocket server listening on ws://localhost:4001
[...] [INFO] [server] HTTP API + static frontend listening on http://localhost:4000
[...] [INFO] [server] Modbus TCP target: 192.0.2.10:502 (unit 1)
[...] [WARN] [modbusClient] Could not connect to Modbus TCP server at 192.0.2.10:502 (...). Will retry in 2000ms. ...
```

That last warning line is expected and harmless if there's no RTU560 at
that address yet — the server keeps running normally.

Open **http://localhost:4000** to load the static frontend (served from
`public/`), or hit the API directly:

```bash
curl http://localhost:4000/api/health
curl http://localhost:4000/api/substations
curl http://localhost:4000/api/substations/msds1
curl "http://localhost:4000/api/substations/msds1/history?param=voltage&limit=20"
curl http://localhost:4000/api/register-map
```

For live/watch-mode development (auto-restarts on file changes):

```bash
npm run dev
```

### Running in VS Code

1. Open this folder in VS Code (`File → Open Folder...`).
2. Run the two setup/copy commands above in the integrated terminal if you
   haven't already.
3. Press **F5** (or Run and Debug → "Run MSDS backend (src/server.js)").
   This uses the included `.vscode/launch.json`, loads `.env`
   automatically, and lets you set breakpoints anywhere in `src/`.

## REST API reference

| Method | Path                                            | Description                                             |
|--------|--------------------------------------------------|-----------------------------------------------------------|
| GET    | `/api/health`                                    | `{ status, modbusConnected, serverTime }`                  |
| GET    | `/api/substations`                               | Full live snapshot of every substation                     |
| GET    | `/api/substations/:id`                           | Snapshot for one substation                                |
| GET    | `/api/substations/:id/history?param=&limit=`     | Persisted history for one parameter (from SQLite)          |
| PUT    | `/api/substations/:id/feeder-on` `{on:boolean}`   | Toggle a substation's feeder on/off flag (409 if offline)   |
| GET    | `/api/register-map`                              | Effective register map (base config + saved overrides)     |
| PUT    | `/api/register-map/:substationId/:paramKey`      | `{address:number, unitId?:number}` — save an address override |

## WebSocket protocol

Connect to `ws://localhost:4001`. On connect, and again after every poll
cycle, the server sends:

```json
{
  "type": "snapshot",
  "payload": {
    "modbusConnected": false,
    "generatedAt": 1732900000000,
    "substations": [
      {
        "id": "msds1",
        "name": "MSDS-1",
        "status": "offline",
        "feederOn": true,
        "parameters": {
          "voltage": { "value": null, "quality": "bad", "ts": 1732900000000 },
          "power":   { "value": null, "quality": "bad", "ts": 1732900000000 }
        }
      }
    ]
  }
}
```

## Register map format

See `config/registerMap.example.json`. Each substation entry looks like:

```json
{
  "id": "msds1",
  "name": "MSDS-1",
  "unitId": null,
  "baseAddress": 0,
  "parameters": {
    "voltage": { "label": "Volts Ave", "unit": "kV", "address": 42, "registerCount": 2, "scale": 1.0 }
  }
}
```

- `address` is the Modbus **input register** start address (function code
  4) for a 32-bit IEEE-754 float spanning `registerCount` (always 2)
  consecutive registers.
- `unitId: null` means "use `MODBUS_DEFAULT_UNIT_ID` from `.env`"; set an
  explicit number per substation if each one uses a different Modbus
  unit/slave ID on the same RTU560.
- `scale` is a multiplier applied after decoding the float — leave at
  `1.0` if the RTU560 already reports engineering units directly (as the
  IEEE-754 float convention implies), or set a different multiplier if
  your site's registers need scaling.
- Address overrides saved through `PUT /api/register-map/:sub/:param`
  (e.g. from the dashboard's address-book UI) are stored in SQLite and
  layered on top of this file at runtime — the file itself is never
  rewritten by the app.

**Float decoding / word order:** `MODBUS_FLOAT_WORD_ORDER` in `.env`
controls how the two 16-bit registers are assembled into a 32-bit float
(`ABCD`, `BADC`, `CDAB`, or `DCBA`). This varies by device configuration —
confirm the correct value against the RTU560's Modbus point-mapping export
or by cross-checking a known register's value; `BADC` is used as the
default here as a common convention, not a guarantee.

## Error handling summary

- **No Modbus connection at startup or ever:** logged as warnings, HTTP/WS
  keep serving, substations report as offline.
- **Modbus connection drops mid-run:** detected via read failures and/or
  socket close/error events; client marks itself disconnected and begins
  reconnecting with backoff (2s → 4s → 8s ... capped at 30s by default).
- **A single register read times out or errors:** that one
  substation/parameter is recorded with `quality: "bad"` and `value:
  null` for that cycle only; every other substation/parameter in the same
  cycle is unaffected.
- **Invalid register map JSON or missing file (and no example to fall
  back to):** this is the one case that fails fast at startup, since the
  app has nothing to poll — logged clearly with the offending file path.
- **Unhandled promise rejections / exceptions elsewhere:** caught at the
  process level and logged rather than crashing the process.

## Extending

- Add a new substation or parameter: add an entry to
  `config/registerMap.json` (parameter keys should match the frontend's
  `PARAM_DEFS` keys — `voltage`, `power`, `current`, `frequency`, `pf`,
  `energy`, `vab`, `vbc`, `vca`, `vae`, `vbe`, `vce` — if you want the
  existing dashboard to recognize them).
- Change polling frequency: `POLL_INTERVAL_MS` in `.env`.
- Change how much history is kept in memory for sparklines:
  `HISTORY_LENGTH` in `.env` (persisted history in SQLite is unlimited —
  query it with a larger `limit` on the history endpoint as needed).
