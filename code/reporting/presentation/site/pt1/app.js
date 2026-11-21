import { connectFlow, goPart, setSceneHash } from "../flow/bridge.js?v=flow1";
import { createStage } from "./scene.js?v=transitions3";
import { content, sceneNames } from "./content.js?v=transitions3";
const $ = (id) => document.getElementById(id);
let current = 1,
  world,
  data,
  displayed = 1,
  busy = false,
  queued = null;
function fit() {
  const s = Math.min(innerWidth / 1920, innerHeight / 1080),
    stage = $("stage");
  stage.style.transform = `scale(${s})`;
  stage.style.left = `${(innerWidth - 1920 * s) / 2}px`;
  stage.style.top = `${(innerHeight - 1080 * s) / 2}px`;
}
// Project editable DOM text onto the actual four corners of each book page.
function pageTransform(corners) {
  const [p0, p1, p2, p3] = corners,
    dx1 = p1.x - p2.x,
    dx2 = p3.x - p2.x,
    dy1 = p1.y - p2.y,
    dy2 = p3.y - p2.y;
  const dx3 = p0.x - p1.x + p2.x - p3.x,
    dy3 = p0.y - p1.y + p2.y - p3.y,
    den = dx1 * dy2 - dx2 * dy1;
  const g = (dx3 * dy2 - dx2 * dy3) / den,
    h = (dx1 * dy3 - dx3 * dy1) / den;
  const a = p1.x - p0.x + g * p1.x,
    b = p3.x - p0.x + h * p3.x,
    d = p1.y - p0.y + g * p1.y,
    e = p3.y - p0.y + h * p3.y;
  return `matrix3d(${a / 720},${d / 720},0,${g / 720},${b / 760},${e / 760},0,${h / 760},0,0,1,0,${p0.x},${p0.y},0,1)`;
}
function syncFrame({ anchors, pages, progress }) {
  if (
    progress < 1 &&
    !document.documentElement.classList.contains("flow-hold")
  ) {
    const copyStyle = getComputedStyle($("copy"));
    if (copyStyle.visibility !== "hidden" && Number(copyStyle.opacity) > 0.001)
      $("stage").dataset.earlyTextFrames = String(
        Number($("stage").dataset.earlyTextFrames || 0) + 1,
      );
  }
  if (displayed === 2)
    anchors.forEach((a) => {
      const el = $(`label-${a.name}`);
      if (el) {
        el.style.left = `${a.name === "Atlantic" ? Math.min(a.x, 1680) : a.x}px`;
        el.style.top = `${a.y}px`;
      }
    });
  if (displayed === 4)
    pages.forEach((corners, i) => {
      const page = $(i ? "right-page" : "left-page");
      if (page) page.style.transform = pageTransform(corners);
    });
}
function motionStatus() {
  const playing = world.isPlaying();
  $("motion").textContent = playing ? "Ⅱ Pause" : "▷ Play";
  $("motion").setAttribute(
    "aria-label",
    playing ? "Pause motion" : "Play motion",
  );
  document.body.classList.toggle("motion-paused", !playing);
  if (!playing) finishReveals();
  $("motion-status").textContent = playing ? "LIVE OCEAN" : "MOTION PAUSED";
}
function finishReveals() {
  $("copy")
    .getAnimations({ subtree: true })
    .forEach((animation) => {
      if (Number.isFinite(animation.effect.getComputedTiming().iterations))
        animation.finish();
    });
}
function mount(n) {
  displayed = n;
  document.body.dataset.scene = String(n);
  $("copy").innerHTML = content(n, data);
  $("map-labels").innerHTML =
    n === 2
      ? '<span class="map-label" id="label-Florida">Florida</span><span class="map-label region" id="label-R">Research region R</span><span class="map-label atlantic" id="label-Atlantic">ATLANTIC OCEAN</span>'
      : "";
  document.title = `PT1 · ${sceneNames[n - 1]} | Where Things End Up`;
}
function navigation(n) {
  $("count").textContent = `0${n} / 05`;
  $("prev").disabled = n === 1;
  $("next").disabled = false;
  document
    .querySelectorAll("#scene-nav a")
    .forEach((a, i) =>
      i + 1 === n
        ? a.setAttribute("aria-current", "step")
        : a.removeAttribute("aria-current"),
    );
}
async function render(immediate = false) {
  current = Math.max(1, Math.min(5, Number(location.hash.slice(1)) || 1));
  navigation(current);
  // Finish the current camera flight; rapid input only updates the next destination.
  if (busy) {
    queued = current;
    return;
  }
  if (!immediate && current === displayed) return;
  busy = true;
  queued = null;
  const target = current;
  const stage = $("stage");
  stage.dataset.phase = "leaving";
  if (!immediate && world.isPlaying()) {
    // Keep the outgoing DOM intact until it is completely invisible.
    await Promise.all(
      [$("copy"), $("map-labels")].map(async (el) => {
        const fade = el.animate(
          [{ opacity: getComputedStyle(el).opacity }, { opacity: 0 }],
          { duration: 240, easing: "ease-out", fill: "forwards" },
        );
        await fade.finished;
        el.style.opacity = "0";
        fade.cancel();
      }),
    );
  }
  stage.classList.remove("is-settled");
  stage.classList.add("is-travelling");
  stage.dataset.phase = "travelling";
  const destination = queued ?? target;
  queued = null;
  mount(destination);
  // The new page remains hidden until the camera supplies its final projection.
  $("copy").style.opacity = "0";
  $("map-labels").style.opacity = "0";
  world.setScene(destination, immediate);
  motionStatus();
}
async function settle(n) {
  if (n !== displayed) return;
  const stage = $("stage");
  stage.dataset.phase = "arriving";
  // A short empty-book beat precedes the readable reference reveal.
  if (world.isPlaying())
    await new Promise((resolve) => setTimeout(resolve, n === 4 ? 180 : 80));
  if (queued !== null && queued !== displayed) {
    busy = false;
    render(false);
    return;
  }
  queued = null;
  stage.classList.remove("is-travelling");
  stage.classList.add("is-settled");
  if (!world.isPlaying()) finishReveals();
  $("copy").style.opacity = "1";
  $("map-labels").style.opacity = "1";
  stage.dataset.phase = "reading";
  busy = false;
}
function go(n) {
  if (n === 6) {
    goPart(2, "01");
    return;
  }
  if (n >= 1 && n <= 5) setSceneHash(String(n).padStart(2, "0"));
}
fit();
addEventListener("resize", fit);
$("scene-nav").innerHTML = sceneNames
  .map(
    (name, i) =>
      `<a href="#0${i + 1}" aria-label="Scene ${i + 1}: ${name}"><span>0${i + 1}</span>${name}</a>`,
  )
  .join("");
$("prev").onclick = () => go(current - 1);
$("next").onclick = () => go(current + 1);
$("notes-open").onclick = () => $("notes").showModal();
$("notes-close").onclick = () => $("notes").close();
$("motion").onclick = () => {
  world.toggle();
  motionStatus();
};
$("replay").onclick = () => {
  world.replay();
  $("copy")
    .getAnimations({ subtree: true })
    .forEach((animation) => {
      animation.currentTime = 0;
    });
};
addEventListener("keydown", (event) => {
  if ($("notes").open || event.metaKey || event.ctrlKey || event.altKey) return;
  if (
    event.code === "Space" &&
    !["BUTTON", "A"].includes(document.activeElement.tagName)
  ) {
    event.preventDefault();
    world.toggle();
    motionStatus();
    return;
  }
  const n = {
    ArrowRight: current + 1,
    PageDown: current + 1,
    ArrowLeft: current - 1,
    PageUp: current - 1,
    Home: 1,
    End: 5,
  }[event.key];
  if (n !== undefined) {
    event.preventDefault();
    go(n);
  }
});
try {
  const response = await fetch("./assets/pt1/geography-wide.json");
  if (!response.ok) throw Error("Geography could not load");
  data = await response.json();
  world = await createStage($("scene"), data, syncFrame, settle);
  connectFlow(1, world, motionStatus);
  render(true);
  $("loading").hidden = true;
  addEventListener("hashchange", () => render(false));
} catch (error) {
  $("loading").hidden = true;
  $("error").hidden = false;
  $("error-text").textContent =
    "Please refresh, or open the existing presentation.";
  console.error("PT1 load", error);
}
