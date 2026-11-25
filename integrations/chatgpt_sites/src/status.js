import { BUILD, PROFILE, PROTOCOL, SELECTOR_TTL_MS } from "./contract.js";

export const SYNTHETIC_LOCAL = "SYNTHETIC_LOCAL";
export const UNAVAILABLE = "UNAVAILABLE";

export function resolveMode(env) {
  const mode = env.PAS_CONTEXT_MODE ?? SYNTHETIC_LOCAL;
  return mode === SYNTHETIC_LOCAL ? SYNTHETIC_LOCAL : UNAVAILABLE;
}

export function statusPage(mode) {
  const synthetic = mode === SYNTHETIC_LOCAL;
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>PAS Personal Context</title>
  <style>
    :root { font: 100% / 1.5 system-ui, sans-serif; color: #152d2b; background: #edf4f2; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    main { width: min(100% - 2rem, 43rem); margin: clamp(2.5rem, 9vw, 6rem) auto; }
    header { padding: 0 .15rem; margin-bottom: 2rem; }
    h1 { margin: 0; font-size: clamp(2.1rem, 7vw, 3.5rem); line-height: 1.05; letter-spacing: -.045em; }
    p { margin: .65rem 0 0; }
    .lede, dd, footer { color: #415e5a; }
    section { padding: clamp(1.1rem, 5vw, 2rem); background: #fff; border: 1px solid #cddeda; border-radius: 1rem; }
    h2 { font-size: 1.2rem; margin: 0 0 1rem; }
    dl { margin: 0; }
    .row { display: grid; grid-template-columns: minmax(8rem, 1fr) 2fr; gap: .6rem 1.1rem; padding: .8rem 0; border-top: 1px solid #e1ebe9; }
    dt { font-weight: 620; }
    dd { margin: 0; overflow-wrap: anywhere; }
    .mode { display: inline-block; color: #075744; background: #dff3eb; padding: .1rem .45rem; border-radius: .28rem; font-size: .875rem; }
    .unavailable { color: #76361a; background: #f8e9df; }
    code { font-size: .9em; }
    .note { font-size: .9rem; margin-top: 1rem; color: #415e5a; }
    details { margin: 1.3rem .15rem 0; }
    summary { cursor: pointer; width: fit-content; font-weight: 620; }
    summary:focus-visible { outline: 2px solid #086853; outline-offset: .2rem; }
    details dl { margin-top: .65rem; }
    @media (max-width: 34rem) { .row { grid-template-columns: 1fr; gap: .25rem; } }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>PAS Personal Context</h1>
      <p class="lede">Connection status for the read-only ChatGPT plugin.</p>
    </header>
    <section aria-labelledby="connection">
      <h2 id="connection">Connection status</h2>
      <dl>
        <div class="row"><dt>Mode</dt><dd><code class="mode ${synthetic ? "" : "unavailable"}">${mode}</code></dd></div>
        <div class="row"><dt>PAS</dt><dd>Disconnected</dd></div>
        <div class="row"><dt>Source policy</dt><dd>${synthetic ? "Fabricated Travel itinerary only" : "No sources available"}</dd></div>
        <div class="row"><dt>MCP tools</dt><dd><code>search</code> and <code>fetch</code> · read-only</dd></div>
      </dl>
      <p class="note">${synthetic ? "The demo serves sample data and does not check plugin installation." : "Tool reads are disabled. PAS staging connectivity is unavailable in this build."}</p>
    </section>
    <details>
      <summary>Diagnostics</summary>
      <dl>
        <div class="row"><dt>Build</dt><dd><code>${BUILD}</code></dd></div>
        <div class="row"><dt>MCP profile</dt><dd><code>${PROFILE}</code> · <code>${PROTOCOL}</code></dd></div>
        <div class="row"><dt>Demo selector lifetime</dt><dd>${SELECTOR_TTL_MS / 1000} seconds within one worker isolate</dd></div>
      </dl>
    </details>
  </main>
</body>
</html>`;
}
