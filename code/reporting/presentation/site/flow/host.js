const $ = (id) => document.getElementById(id);
const chapters = [
  {
    title: "Research aim & background",
    scenes: [
      ["01", "The seven-day question"],
      ["02", "Research region R"],
      ["03", "The original proposal"],
      ["04", "Literature & methods"],
      ["05", "Why destinations matter"],
    ],
  },
  {
    title: "Data audit & research design",
    scenes: [
      ["01", "Candidate regions"],
      ["02", "The original corridor"],
      ["03", "Selecting region R"],
      ["04", "Drifter preprocessing"],
      ["05", "Usable annual support"],
    ],
  },
  {
    title: "Five stages of modelling",
    scenes: [
      ["gallery/b2", "The model collection"],
      ["model/b2", "01 · Empirical transitions"],
      ["model/fixed", "02 · Global blending"],
      ["model/local-endpoint", "03 · Spatial borrowing"],
      ["model/exact-point", "04 · Exact origins"],
      ["model/endpoint-ci", "04 · Endpoint uncertainty"],
      ["model/local-gaussian", "05 · Local densities"],
      ["model/mdn22", "05 · Conditional MDN"],
    ],
  },
  {
    title: "Results, limits & next steps",
    scenes: [
      ["01", "Brier comparisons"],
      ["02", "Energy Score comparisons"],
      ["03", "The horizon limit"],
      ["04", "Conclusions & next steps"],
    ],
  },
];
const defaultHash = (part) => (part === 3 ? "gallery/b2" : "01");
const frames = new Map();
let current = null,
  desired = parseRoute(),
  switching = false;
let playing =
  sessionStorage.getItem("ocean-motion") !== "paused" &&
  !matchMedia("(prefers-reduced-motion: reduce)").matches;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const nextPaint = () =>
  new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)),
  );
function monitorHandoff(incoming, from) {
  let previous = 0,
    early = 0,
    finished = false;
  const intervals = [];
  function sample(now) {
    if (finished) return;
    if (previous) intervals.push(now - previous);
    previous = now;
    const d = incoming.el.contentDocument;
    for (const el of d.querySelectorAll(
      "#copy,#map-labels,#gallery:not([hidden]),#detail:not([hidden]),#content",
    )) {
      const style = d.defaultView.getComputedStyle(el);
      if (style.visibility !== "hidden" && Number(style.opacity) > 0.001) {
        early++;
        break;
      }
    }
    requestAnimationFrame(sample);
  }
  requestAnimationFrame(sample);
  return () => {
    finished = true;
    const sorted = [...intervals].sort((a, b) => a - b);
    const report = {
      from,
      to: incoming.part,
      frames: intervals.length,
      earlyTextFrames: early,
      p95Ms: Math.round(sorted[Math.floor(sorted.length * 0.95)] || 0),
      maxMs: Math.round(sorted.at(-1) || 0),
    };
    const records = JSON.parse($("presentation").dataset.handoffs || "[]");
    records.push(report);
    $("presentation").dataset.handoffs = JSON.stringify(records.slice(-20));
  };
}
function parseRoute() {
  const match = location.hash.match(/^#pt([1-4])\/(.+)$/);
  if (!match) return { part: 1, hash: "01" };
  const part = Number(match[1]);
  let hash = match[2];
  if (part !== 3 && !chapters[part - 1].scenes.some((s) => s[0] === hash))
    hash = "01";
  if (part === 3 && !/^(gallery|model)\/[a-z0-9-]+$/.test(hash))
    hash = "gallery/b2";
  return { part, hash };
}
function post(frame, type, data = {}) {
  frame.el.contentWindow.postMessage(
    { channel: "ocean-presentation", type, ...data },
    location.origin,
  );
}
function setState(frame, active, hold) {
  post(frame, "state", { active, hold, playing });
}
function makeFrame(part, hash) {
  const el = document.createElement("iframe");
  el.className = "chapter-frame prepared";
  el.title = `Part ${part}: ${chapters[part - 1].title}`;
  el.dataset.part = part;
  el.setAttribute("aria-hidden", "true");
  el.inert = true;
  el.src = `./pt${part}.html?embedded=1#${hash}`;
  const frame = { el, part, hash, ready: false, pending: new Set() };
  frames.set(part, frame);
  $("presentation").append(el);
  return frame;
}
async function prepare(part, hash) {
  let frame = frames.get(part);
  if (!frame) frame = makeFrame(part, hash);
  if (frame.ready && frame.hash === hash) return frame;
  if (frame.ready) {
    frame.ready = false;
    frame.hash = hash;
    post(frame, "route", { hash });
  }
  // A requested route can change while its chapter is still compiling.
  await new Promise((resolve, reject) => {
    const listener = () => {
      clearTimeout(timer);
      frame.pending.delete(listener);
      resolve();
    };
    const timer = setTimeout(() => {
      frame.pending.delete(listener);
      reject(Error(`Part ${part} preparation timed out`));
    }, 25000);
    frame.pending.add(listener);
  });
  if (frame.hash !== hash) return prepare(part, hash);
  return frame;
}
function prewarmNext() {
  if (current?.part < 4 && !frames.has(current.part + 1)) {
    makeFrame(current.part + 1, defaultHash(current.part + 1));
  }
}
function highlight() {
  document
    .querySelectorAll(".chapter")
    .forEach((el, i) => (el.dataset.current = String(i + 1 === desired.part)));
  document
    .querySelectorAll(".chapter a")
    .forEach((a) =>
      a.setAttribute(
        "aria-current",
        a.hash === location.hash ? "step" : "false",
      ),
    );
}
function syncURL(part, hash) {
  const target = `#pt${part}/${hash}`;
  if (location.hash !== target) history.pushState(null, "", target);
  highlight();
}
async function switchChapter() {
  if (switching) return;
  switching = true;
  try {
    while (
      !current ||
      current.part !== desired.part ||
      current.hash !== desired.hash
    ) {
      const target = { ...desired };
      if (current?.part === target.part) {
        post(frames.get(target.part), "route", { hash: target.hash });
        current.hash = target.hash;
        break;
      }
      const timer = setTimeout(() => {
        if (current) $("preparing").hidden = false;
      }, 600);
      let incoming;
      try {
        incoming = await prepare(target.part, target.hash);
      } finally {
        clearTimeout(timer);
        $("preparing").hidden = true;
      }
      if (target.part !== desired.part || target.hash !== desired.hash)
        continue;
      const outgoing = current && frames.get(current.part);
      $("presentation").dataset.phase = "travelling";
      const from = current?.part || 0;
      if (outgoing) {
        setState(outgoing, true, true);
        outgoing.el.inert = true;
        if (playing) await sleep(380);
      }
      setState(incoming, true, true);
      incoming.el.classList.add("active");
      incoming.el.style.opacity = "0";
      incoming.el.style.zIndex = "2";
      await nextPaint();
      const finishMonitor = monitorHandoff(incoming, from);
      if (outgoing && playing) {
        const dive = from === 2 && target.part === 3;
        const emerge = from === 3 && target.part === 2;
        const duration = dive || emerge ? 1250 : 950;
        const easing = "cubic-bezier(.45,0,.15,1)";
        const out = outgoing.el.animate(
          [
            { opacity: 1, transform: "none" },
            {
              opacity: 0,
              transform: dive
                ? "translateY(-24%) scale(1.05)"
                : emerge
                  ? "translateY(24%) scale(1.04)"
                  : "scale(1.045)",
            },
          ],
          { duration, easing, fill: "forwards" },
        );
        const into = incoming.el.animate(
          [
            {
              opacity: 0,
              transform: dive
                ? "translateY(16%) scale(1.03)"
                : emerge
                  ? "translateY(-16%) scale(1.03)"
                  : "scale(1.035)",
            },
            { opacity: 1, transform: "none" },
          ],
          { duration, easing, fill: "forwards" },
        );
        await Promise.all([out.finished, into.finished]);
        outgoing.el.classList.remove("active");
        outgoing.el.style.opacity = "0";
        incoming.el.style.opacity = "1";
        out.cancel();
        into.cancel();
      } else incoming.el.style.opacity = "1";
      if (outgoing) {
        outgoing.el.classList.remove("active");
        outgoing.el.style.opacity = "0";
        outgoing.el.setAttribute("aria-hidden", "true");
        setState(outgoing, false, true);
      }
      incoming.el.style.zIndex = "1";
      incoming.el.inert = false;
      incoming.el.removeAttribute("aria-hidden");
      finishMonitor();
      current = target;
      $("loading").hidden = true;
      $("presentation").dataset.part = target.part;
      const stillRequested =
        target.part === desired.part && target.hash === desired.hash;
      $("presentation").dataset.phase = stillRequested
        ? "reading"
        : "travelling";
      setState(incoming, true, !stillRequested);
      document.title = `Part ${target.part} · ${chapters[target.part - 1].title} | Where Things End Up`;
      // Precompile the next chapter while there is time to speak, never at the handoff.
      prewarmNext();
    }
  } catch (error) {
    console.error("Presentation handoff", error);
    $("failure").hidden = false;
  } finally {
    switching = false;
  }
}
function request(part, hash) {
  desired = { part, hash };
  syncURL(part, hash);
  switchChapter();
}
$("chapter-list").innerHTML = chapters
  .map(
    (chapter, i) =>
      `<section class="chapter"><span class="chapter-number">0${i + 1}</span><h2>${chapter.title}</h2><ul>${chapter.scenes.map(([hash, label]) => `<li><a href="#pt${i + 1}/${hash}">${label}</a></li>`).join("")}</ul></section>`,
  )
  .join("");
$("chapter-list").addEventListener("click", (e) => {
  const a = e.target.closest("a");
  if (a) {
    e.preventDefault();
    $("contents").close();
    const [, part, hash] = a.hash.match(/^#pt([1-4])\/(.+)$/);
    request(Number(part), hash);
  }
});
function openContents() {
  highlight();
  $("contents").showModal();
}
$("close-contents").onclick = () => $("contents").close();
$("contents").addEventListener(
  "close",
  () => current && frames.get(current.part).el.contentWindow.focus(),
);
$("retry").onclick = () => {
  const frame = frames.get(desired.part);
  if (frame && frame.part !== current?.part) {
    frame.el.remove();
    frames.delete(frame.part);
  }
  $("failure").hidden = true;
  switchChapter();
};
$("dismiss").onclick = () => {
  $("failure").hidden = true;
  if (current) {
    desired = { ...current };
    syncURL(current.part, current.hash);
  }
};
addEventListener("message", (e) => {
  if (e.origin !== location.origin || e.data?.channel !== "ocean-presentation")
    return;
  const frame = [...frames.values()].find(
    (f) => f.el.contentWindow === e.source,
  );
  if (!frame) return;
  const message = e.data;
  if (message.type === "ready") {
    frame.hash = message.hash;
    frame.ready = true;
    for (const resolve of [...frame.pending]) resolve();
    if (
      !switching &&
      frame.part === current?.part &&
      frame.part === desired.part &&
      message.hash === desired.hash
    ) {
      $("presentation").dataset.phase = "reading";
      setState(frame, true, false);
    }
  } else if (message.type === "route") {
    frame.hash = message.hash;
    frame.ready = false;
    if (frame.part === current?.part && !switching) {
      current.hash = message.hash;
      desired = { ...current };
      syncURL(current.part, current.hash);
    }
  } else if (message.type === "navigate" && frame.part === current?.part) {
    request(message.part, message.hash);
  } else if (message.type === "contents" && frame.part === current?.part)
    openContents();
  else if (message.type === "motion" && frame.part === current?.part) {
    playing = message.playing;
    sessionStorage.setItem("ocean-motion", playing ? "playing" : "paused");
  }
});
addEventListener("hashchange", () => {
  desired = parseRoute();
  highlight();
  switchChapter();
});
addEventListener("keydown", (e) => {
  if (e.key.toLowerCase() === "m" && !$("contents").open) openContents();
});
highlight();
switchChapter();
