import { models, stages, art } from "./models.js?v=p3v3";
export function createCarousel(host, onSelect, onOpen) {
  let position = 1,
    target = 1,
    last = 0,
    active = -1,
    drag = null,
    moved = false,
    enabled = true,
    playing = true,
    drawn = NaN;
  const cards = models.map((m, i) => {
    const b = document.createElement("button");
    b.className = "model-card";
    b.dataset.model = m.id;
    b.setAttribute("aria-label", `${m.title}, step ${m.step}`);
    b.innerHTML = `<div class="card-face"><div class="card-top"><span>SEVEN DAYS AT SEA</span><strong>0${m.step}</strong></div><div class="card-art">${art(m.step, i)}</div><div class="card-family">${stages[m.step - 1]}</div><div class="card-name">${m.title}</div><div class="card-tag">${m.step === 5 ? "CONDITIONAL DENSITY" : "HISTORICAL TRANSPORT"} · 07 DAYS</div></div><div class="card-shade"></div>`;
    host.appendChild(b);
    b.onclick = () => {
      if (!enabled || moved) return;
      if (Math.abs(position - i) < 0.12 && Math.abs(target - position) < 0.04)
        onOpen(i);
      else select(i);
    };
    return b;
  });
  function select(i, immediate = false) {
    target = Math.max(0, Math.min(models.length - 1, i));
    if (immediate || !playing) position = target;
  }
  function frame(t) {
    requestAnimationFrame(frame);
    const dt = Math.min((t - last) / 1000 || 0, 0.05);
    last = t;
    if (!enabled) return;
    position += (target - position) * (1 - Math.exp(-(drag ? 20 : 8) * dt));
    if (Math.abs(target - position) < 0.0005) position = target;
    if (position === drawn) return;
    drawn = position;
    const selected = Math.round(position);
    if (selected !== active) {
      active = selected;
      onSelect(active);
    }
    cards.forEach((card, i) => {
      const r = i - position,
        a = Math.abs(r),
        center = Math.max(0, 1 - a),
        open = center * center * (3 - 2 * center);
      const x = r * 280,
        z = -90 * Math.pow(a, 1.35) + open * 70,
        y = a * 12;
      card.style.visibility = a < 6 ? "visible" : "hidden";
      card.style.transform = `translate3d(${x}px,${y}px,${z}px) rotateY(${-Math.sign(r) * Math.min(58, a * 25)}deg)`;
      card.style.zIndex = String(100 - Math.round(a * 10));
      card.querySelector(".card-shade").style.opacity = String(
        Math.min(0.72, a * 0.12),
      );
      card.classList.toggle("active", i === selected);
      card.tabIndex = i === selected ? 0 : -1;
      card.setAttribute("aria-current", i === selected ? "true" : "false");
    });
    host.dataset.active = models[active]?.id;
    host.dataset.settled = String(Math.abs(position - target) < 0.01);
  }
  const shelf = host.parentElement;
  shelf.addEventListener("pointerdown", (e) => {
    if (!enabled || e.button !== 0) return;
    drag = { x: e.clientX, t: target };
    moved = false;
  });
  addEventListener("pointermove", (e) => {
    if (!drag) return;
    const scale =
      document.getElementById("stage").getBoundingClientRect().width / 1920;
    const dx = (e.clientX - drag.x) / scale;
    if (Math.abs(dx) > 7) moved = true;
    if (moved)
      target = Math.max(0, Math.min(models.length - 1, drag.t - dx / 190));
  });
  addEventListener("pointerup", () => {
    if (!drag) return;
    drag = null;
    target = Math.round(target);
    setTimeout(() => (moved = false), 50);
  });
  let wheelTimer;
  shelf.addEventListener(
    "wheel",
    (e) => {
      if (!enabled) return;
      e.preventDefault();
      target = Math.max(
        0,
        Math.min(
          models.length - 1,
          target +
            (Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY) /
              300,
        ),
      );
      clearTimeout(wheelTimer);
      wheelTimer = setTimeout(() => (target = Math.round(target)), 150);
    },
    { passive: false },
  );
  requestAnimationFrame(frame);
  return {
    select,
    step: (d) => select(Math.round(target) + d),
    index: () => Math.round(target),
    setEnabled: (v) => {
      enabled = v;
      drag = null;
    },
    setPlaying: (v) => {
      playing = v;
      if (!v) position = target;
    },
  };
}
