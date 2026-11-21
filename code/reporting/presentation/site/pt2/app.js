import { connectFlow, goPart, setSceneHash } from "../flow/bridge.js?v=flow1";
import { createStage } from "./scene.js?v=p2v1";
import { content, labels, names, focusContent } from "./content.js?v=p2p3";
const $ = (id) => document.getElementById(id);
let world,
  data,
  displayed = 0,
  desired = 1,
  busy = false,
  queued = null,
  focus = 0,
  focusBusy = false,
  focusVersion = 0;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
function fit() {
  const scale = Math.min(innerWidth / 1920, innerHeight / 1080);
  $("stage").style.transform = `scale(${scale})`;
  $("stage").style.left = `${(innerWidth - 1920 * scale) / 2}px`;
  $("stage").style.top = `${(innerHeight - 1080 * scale) / 2}px`;
}
function navigation(n) {
  $("count").textContent = `0${n} / 05`;
  $("prev").disabled = false;
  $("next").disabled = false;
  document
    .querySelectorAll("#scene-nav a")
    .forEach((a, i) =>
      i + 1 === n
        ? a.setAttribute("aria-current", "step")
        : a.removeAttribute("aria-current"),
    );
}
function status() {
  const p = world.isPlaying();
  $("motion").textContent = p ? "Ⅱ Pause" : "▷ Play";
  $("motion-status").textContent = p ? "LIVE OCEAN" : "MOTION PAUSED";
  $("motion").setAttribute("aria-label", p ? "Pause motion" : "Play motion");
  document.body.classList.toggle("motion-paused", !p);
}
function mount(n) {
  focusVersion++;
  focusBusy = false;
  displayed = n;
  focus = 0;
  $("stage").dataset.focus = "0";
  if (n === 4) world.setFocus(0);
  document.body.dataset.scene = n;
  $("copy").innerHTML = content(n, data);
  $("map-labels").innerHTML = labels(n);
  document.title = `Part 2 · ${names[n - 1]} | Where Things End Up`;
  document
    .querySelectorAll("[data-focus]")
    .forEach((b) => (b.onclick = () => setFocus(Number(b.dataset.focus))));
}
async function render(immediate = false) {
  const requested = Number(location.hash.slice(1));
  desired =
    Number.isInteger(requested) && requested >= 1 && requested <= 5
      ? requested
      : 1;
  navigation(desired);
  if (busy) {
    queued = desired;
    return;
  }
  if (desired === displayed && !immediate) return;
  busy = true;
  focusVersion++;
  focusBusy = false;
  queued = null;
  const target = desired;
  const stage = $("stage");
  stage.dataset.phase = "leaving";
  if (displayed && world.isPlaying()) {
    await Promise.all(
      ["copy", "map-labels"].map(async (id) => {
        const el = $(id),
          a = el.animate(
            [{ opacity: getComputedStyle(el).opacity }, { opacity: 0 }],
            { duration: 240, fill: "forwards" },
          );
        await a.finished;
        el.style.transition = "none";
        el.style.opacity = "0";
        a.cancel();
      }),
    );
  }
  stage.classList.remove("is-settled");
  $("copy").style.opacity = "0";
  $("map-labels").style.opacity = "0";
  const destination = queued ?? target;
  queued = null;
  mount(destination);
  stage.dataset.phase = "travelling";
  if (immediate && destination === 1 && world.isPlaying())
    world.startOverview();
  else world.setScene(destination, immediate);
  status();
}
async function settled(n) {
  if (displayed !== n) return;
  $("stage").dataset.phase = "arriving";
  if (world.isPlaying()) await wait(100);
  if (queued !== null && queued !== displayed) {
    busy = false;
    render();
    return;
  }
  queued = null;
  $("stage").classList.add("is-settled");
  $("copy").style.transition = "";
  $("map-labels").style.transition = "";
  $("copy").style.opacity = "1";
  $("map-labels").style.opacity = "1";
  $("stage").dataset.phase = "reading";
  busy = false;
}
async function setFocus(n) {
  if (displayed !== 4 || busy || focusBusy || n === focus) return;
  focusBusy = true;
  const version = ++focusVersion;
  const panel = $("cleaning-panel"),
    line = $("callout-line");
  panel.style.opacity = "0";
  if (line) line.style.opacity = "0";
  if (world.isPlaying()) await wait(170);
  if (version !== focusVersion || displayed !== 4 || !panel.isConnected) return;
  focus = n;
  world.setFocus(n);
  panel.innerHTML = focusContent(n);
  document
    .querySelectorAll("[data-focus]")
    .forEach((b) =>
      b.setAttribute("aria-selected", String(Number(b.dataset.focus) === n)),
    );
  panel.style.opacity = "1";
  if (line) line.style.opacity = "1";
  $("stage").dataset.focus = n;
  focusBusy = false;
}
function sync({ scene, progress, anchors, chartBlend }) {
  $("chart-veil").style.opacity = String(chartBlend);
  if (progress < 1) {
    const el = $("copy"),
      shown = getComputedStyle(el);
    if (shown.visibility !== "hidden" && Number(shown.opacity) > 0.001)
      $("stage").dataset.earlyTextFrames = String(
        Number($("stage").dataset.earlyTextFrames || 0) + 1,
      );
  }
  if (scene !== displayed || progress < 1) return;
  if (scene === 1) {
    const shifts = {
      kuroshio: [-210, 20],
      california: [-175, -70],
      central: [50, -95],
      sargasso: [90, 65],
      florida: [-180, 78],
      gulfstream: [40, -20],
    };
    for (const [id, p] of Object.entries(anchors)) {
      const el = $(`label-${id}`);
      if (el) {
        const [dx, dy] = shifts[id] || [0, 0];
        el.style.left = `${p.x}px`;
        el.style.top = `${p.y}px`;
        el.querySelector("span").style.transform = `translate(${dx}px,${dy}px)`;
      }
    }
    $("world-lines").innerHTML = Object.entries(anchors)
      .map(([id, p]) => {
        const [dx, dy] = shifts[id] || [0, 0];
        return `<path d="M${p.x} ${p.y} L${p.x + dx + 25} ${p.y + dy + 24}"/>`;
      })
      .join("");
  } else if (scene === 2 || scene === 3) {
    const ids =
      scene === 2
        ? ["gulf", "bahamas", "stream"]
        : ["north", "hatteras", "south"];
    const markup = ids
      .map((id, i) => {
        const p = anchors[id];
        if (!p) return "";
        const row = document.querySelector(`[data-region="${id}"]`);
        const y =
          row.offsetTop + row.offsetHeight / 2 + row.parentElement.offsetTop;
        return `<path d="M598 ${y} L${Math.max(660, p.x - 75)} ${y} L${p.x} ${p.y}"/><circle cx="${p.x}" cy="${p.y}" r="6"/>`;
      })
      .join("");
    if ($("map-lines").dataset.markup !== markup) {
      $("map-lines").innerHTML = markup;
      $("map-lines").dataset.markup = markup;
    }
  } else if (scene === 4) {
    const p = anchors[["drogue", "sst", "motion", "lifecycle"][focus]];
    if (p) {
      const line = $("callout-line");
      line
        .querySelector("path")
        .setAttribute("d", `M668 546 L${p.x - 95} 546 L${p.x} ${p.y}`);
      line.querySelector("circle").setAttribute("cx", p.x);
      line.querySelector("circle").setAttribute("cy", p.y);
    }
    for (const key of ["east", "north"]) {
      const el = $(`axis-${key}`),
        p = anchors[key];
      el.style.display = focus === 2 ? "block" : "none";
      if (p) {
        el.style.left = `${p.x + 8}px`;
        el.style.top = `${p.y - 12}px`;
      }
    }
  }
}
function go(n) {
  if (n === 0) return goPart(1, "05");
  if (n >= 1 && n <= 5) setSceneHash(String(n).padStart(2, "0"));
}
function next() {
  if (!busy && displayed === 4 && focus < 3) {
    setFocus(focus + 1);
    return;
  }
  if (displayed === 5) {
    enterPart3();
    return;
  }
  go(desired + 1);
}
function prev() {
  if (!busy && displayed === 4 && focus > 0) {
    setFocus(focus - 1);
    return;
  }
  go(desired - 1);
}
fit();
addEventListener("resize", fit);
$("scene-nav").innerHTML = names
  .map((n, i) => `<a href="#0${i + 1}"><span>0${i + 1}</span>${n}</a>`)
  .join("");
$("prev").onclick = prev;
$("next").onclick = next;
$("notes-open").onclick = () => $("notes").showModal();
$("notes-close").onclick = () => $("notes").close();
$("motion").onclick = () => {
  world.toggle();
  status();
};
addEventListener("keydown", (e) => {
  if ($("notes").open || e.ctrlKey || e.metaKey || e.altKey || !world) return;
  if (["ArrowRight", "PageDown"].includes(e.key)) {
    e.preventDefault();
    next();
  } else if (["ArrowLeft", "PageUp"].includes(e.key)) {
    e.preventDefault();
    prev();
  } else if (e.key === "Home") {
    e.preventDefault();
    go(1);
  } else if (e.key === "End") {
    e.preventDefault();
    go(5);
  } else if (
    e.code === "Space" &&
    !["BUTTON", "A"].includes(document.activeElement.tagName)
  ) {
    e.preventDefault();
    world.toggle();
    status();
  }
});
try {
  const response = await fetch("./assets/pt2/data.json");
  if (!response.ok) throw Error("Data could not load");
  data = await response.json();
  world = await createStage($("scene"), data, sync, settled);
  connectFlow(2, world, status);
  await render(true);
  $("loading").hidden = true;
  addEventListener("hashchange", () => render());
} catch (e) {
  $("loading").hidden = true;
  $("error").hidden = false;
  $("error-text").textContent =
    "Please refresh, or open the existing presentation.";
  console.error("Part 2 initialization", e);
}

function enterPart3() {
  if (!busy) goPart(3, "gallery/b2");
}
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-part3]")) {
    e.preventDefault();
    enterPart3();
  }
});
