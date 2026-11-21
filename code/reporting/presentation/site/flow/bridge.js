const embedded =
  parent !== window && new URLSearchParams(location.search).has("embedded");
const send = (type, data = {}) =>
  embedded &&
  parent.postMessage(
    { channel: "ocean-presentation", type, ...data },
    location.origin,
  );
let world,
  updateMotion,
  chapterPart,
  active = !embedded,
  holding = embedded;

// The host owns browser history. A chapter updates only its current entry.
export function setSceneHash(hash, notify = true) {
  if (location.hash.slice(1) === hash) return;
  const oldURL = location.href;
  history.replaceState(null, "", `#${hash}`);
  dispatchEvent(
    new HashChangeEvent("hashchange", { oldURL, newURL: location.href }),
  );
  if (notify) send("route", { part: chapterPart, hash });
}

export function goPart(part, hash) {
  if (embedded) send("navigate", { part, hash });
  else location.assign(`./present.html#pt${part}/${hash}`);
}

export function connectFlow(part, scene, onMotion) {
  chapterPart = part;
  world = scene;
  updateMotion = onMotion;
  // Warm renderers without running four independent oceans in the background.
  if (embedded && world.isPlaying()) world.toggle();
  updateMotion();
  const stage = document.getElementById("stage");
  const header =
    document.querySelector(".mast-right") ||
    document.querySelector(".masthead");
  const button = document.createElement("button");
  button.id = "contents-open";
  button.textContent = "Contents · 4 parts";
  button.setAttribute("aria-label", "Open presentation contents");
  button.onclick = () =>
    embedded
      ? send("contents")
      : location.assign(`./present.html#pt${part}/${location.hash.slice(1)}`);
  header.append(button);
  let readyVersion = 0;
  const ready = () => {
    if (stage.dataset.phase !== "reading") return;
    const version = ++readyVersion;
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        if (version !== readyVersion || stage.dataset.phase !== "reading")
          return;
        send("ready", { part, hash: location.hash.slice(1) });
      }),
    );
  };
  new MutationObserver(ready).observe(stage, {
    attributes: true,
    attributeFilter: ["data-phase"],
  });
  ready();
  document.getElementById("motion").addEventListener("click", () =>
    queueMicrotask(() => {
      if (active) send("motion", { playing: world.isPlaying() });
    }),
  );
  // Also capture the presentation's space-key pause control after its handler.
  addEventListener("keyup", (e) => {
    if (e.code === "Space" && active && !document.querySelector("dialog[open]"))
      send("motion", { playing: world.isPlaying() });
  });
  addEventListener("message", (e) => {
    if (
      e.source !== parent ||
      e.origin !== location.origin ||
      e.data?.channel !== "ocean-presentation"
    )
      return;
    const message = e.data;
    if (message.type === "state") {
      active = message.active;
      holding = message.hold;
      document.documentElement.classList.toggle("flow-hold", holding);
      document.documentElement.classList.toggle("flow-inactive", !active);
      const play = active && message.playing;
      if (world.isPlaying() !== play) world.toggle();
      updateMotion();
      if (active && !holding) window.focus();
    } else if (message.type === "route") {
      if (location.hash.slice(1) === message.hash) ready();
      else setSceneHash(message.hash, false);
    }
  });
}

document.addEventListener(
  "click",
  (e) => {
    const link = e.target.closest("a[href]");
    if (
      !link ||
      link.target === "_blank" ||
      e.ctrlKey ||
      e.metaKey ||
      e.shiftKey ||
      e.altKey
    )
      return;
    const url = new URL(link.href, location.href);
    const match = url.pathname.match(/pt([1-4])(?:\.html)?$/);
    if (url.origin !== location.origin || !match) return;
    if (
      url.pathname === location.pathname &&
      link.getAttribute("href").startsWith("#")
    ) {
      e.preventDefault();
      setSceneHash(url.hash.slice(1));
      return;
    }
    e.preventDefault();
    goPart(
      Number(match[1]),
      url.hash.slice(1) || (match[1] === "3" ? "gallery/b2" : "01"),
    );
  },
  true,
);

addEventListener(
  "keydown",
  (e) => {
    if (
      e.key.toLowerCase() === "m" &&
      !e.ctrlKey &&
      !e.metaKey &&
      !e.altKey &&
      !document.querySelector("dialog[open]")
    ) {
      e.preventDefault();
      e.stopImmediatePropagation();
      send("contents");
    }
    if (
      embedded &&
      holding &&
      !e.ctrlKey &&
      !e.metaKey &&
      ["ArrowRight", "ArrowLeft", "PageDown", "PageUp", "Space"].includes(
        e.code,
      )
    ) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  },
  true,
);
