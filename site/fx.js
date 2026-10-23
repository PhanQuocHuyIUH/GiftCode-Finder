"use strict";

// Visual effects: 3D tilt cards, the 3D gift box, confetti, page transitions.
// Nothing here knows about giftcodes; app.js hands it elements and data.
const FX = (() => {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
  const clamp = (value, low, high) => Math.min(Math.max(value, low), high);

  // Lean `card` toward the pointer. CSS reads --tx/--ty (-1..1, unitless) for
  // the rotation and shadow, and --mx/--my for the glare position.
  function tilt(card) {
    if (!finePointer.matches) return;
    let frame = 0;
    let point = null;
    const apply = () => {
      frame = 0;
      if (!point) return;
      const box = card.getBoundingClientRect();
      const px = clamp((point.x - box.left) / box.width, 0, 1);
      const py = clamp((point.y - box.top) / box.height, 0, 1);
      card.style.setProperty("--tx", (px * 2 - 1).toFixed(3));
      card.style.setProperty("--ty", (py * 2 - 1).toFixed(3));
      card.style.setProperty("--mx", `${(px * 100).toFixed(1)}%`);
      card.style.setProperty("--my", `${(py * 100).toFixed(1)}%`);
    };
    card.addEventListener("pointermove", (event) => {
      if (reduced.matches) return;
      point = { x: event.clientX, y: event.clientY };
      card.classList.add("is-tilting");
      if (!frame) frame = requestAnimationFrame(apply);
    });
    const reset = () => {
      point = null;
      card.classList.remove("is-tilting");
      for (const [name, value] of [["--tx", "0"], ["--ty", "0"], ["--mx", "50%"], ["--my", "50%"]]) {
        card.style.setProperty(name, value);
      }
    };
    card.addEventListener("pointerleave", reset);
    card.addEventListener("blur", reset);
  }

  // A CSS gift box in `scene` (built by app.js): drag its .box-area to spin
  // it, click it (or Enter on .box-hit) to open it and let its .chip elements
  // out. Wide scenes hang the chips in two columns beside the box, narrow ones
  // line them up under it.
  function giftBox(scene) {
    const area = scene.querySelector(".box-area");
    const box = scene.querySelector(".box");
    const toggle = scene.querySelector(".box-hit");
    const chips = [...scene.querySelectorAll(".chip")];
    const rest = -18; // the tilt the box settles back to
    let rx = rest;
    let ry = 32;
    let spin = 0; // degrees per ms, left over from a flick
    let drag = null;
    let last = performance.now();

    function layoutChips() {
      const reach = box.offsetWidth * 0.78 + 24; // clear of the box, whichever way it faces
      const widest = Math.max(0, ...chips.map((chip) => chip.offsetWidth));
      const orbit = area.clientWidth / 2 >= reach + widest + 8;
      scene.classList.toggle("chips-orbit", orbit);
      scene.classList.toggle("chips-flow", !orbit);
      chips.forEach((chip, i) => chip.style.setProperty("--d", `${i * 70}ms`));
      if (!orbit) return;
      [chips.filter((_, i) => i % 2 === 0), chips.filter((_, i) => i % 2 === 1)].forEach((column, side) => {
        const sign = side === 0 ? -1 : 1;
        column.forEach((chip, row) => {
          const y = (row - (column.length - 1) / 2) * (chip.offsetHeight + 18) - 30;
          chip.style.setProperty("--x", `${sign * (reach + chip.offsetWidth / 2)}px`);
          chip.style.setProperty("--y", `${y}px`);
          chip.style.setProperty("--r", `${sign * (row - 1) * 2.5}deg`);
        });
      });
    }

    function setOpen(open) {
      scene.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      for (const chip of chips) chip.tabIndex = open ? 0 : -1;
      if (open) {
        layoutChips();
        const rect = box.getBoundingClientRect();
        burst(rect.left + rect.width / 2, rect.top, undefined, 34);
      }
    }

    function frame(now) {
      if (!scene.isConnected) return; // the view changed: stop animating
      const dt = Math.min(now - last, 48);
      last = now;
      if (!drag) {
        const idle = reduced.matches ? 0 : 0.012;
        ry += (idle + spin) * dt;
        spin *= Math.pow(0.996, dt);
        rx += (rest - rx) * Math.min(dt * 0.003, 1);
      }
      box.style.transform = `rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`;
      requestAnimationFrame(frame);
    }

    area.addEventListener("pointerdown", (event) => {
      if (event.button > 0) return;
      drag = { x: event.clientX, y: event.clientY, t: event.timeStamp, moved: 0 };
      spin = 0;
      area.setPointerCapture(event.pointerId);
    });
    area.addEventListener("pointermove", (event) => {
      if (!drag) return;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      const dt = Math.max(event.timeStamp - drag.t, 1);
      ry += dx * 0.45;
      rx = clamp(rx - dy * 0.35, -70, 30);
      spin = (dx * 0.45) / dt;
      drag = { x: event.clientX, y: event.clientY, t: event.timeStamp, moved: drag.moved + Math.abs(dx) + Math.abs(dy) };
    });
    const release = (event) => {
      if (!drag) return;
      const tap = drag.moved < 6;
      drag = null;
      if (event.type === "pointerup" && tap) setOpen(!scene.classList.contains("is-open"));
    };
    area.addEventListener("pointerup", release);
    area.addEventListener("pointercancel", release);
    toggle.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      setOpen(!scene.classList.contains("is-open"));
    });
    const relayout = () => {
      if (!scene.isConnected) window.removeEventListener("resize", relayout);
      else layoutChips();
    };
    window.addEventListener("resize", relayout);

    for (const chip of chips) chip.tabIndex = -1;
    layoutChips();
    requestAnimationFrame(frame);
    return { open: () => setOpen(true) };
  }

  const CONFETTI = ["#ff5ea8", "#a78bfa", "#22d3ee", "#fbbf24", "#34d399"];

  // Confetti from a point on screen (client coordinates).
  function burst(x, y, colors = CONFETTI, count = 22) {
    if (reduced.matches || !Element.prototype.animate) return;
    const layer = document.createElement("div");
    layer.className = "burst";
    layer.style.left = `${x}px`;
    layer.style.top = `${y}px`;
    document.body.append(layer);
    for (let i = 0; i < count; i++) {
      const bit = document.createElement("i");
      bit.style.background = colors[i % colors.length];
      if (i % 3 === 0) bit.style.borderRadius = "50%";
      layer.append(bit);
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5;
      const distance = 50 + Math.random() * 80;
      const dx = Math.cos(angle) * distance;
      const dy = Math.sin(angle) * distance;
      bit.animate(
        [
          { transform: "translate(-50%, -50%) rotate(0deg) scale(1)", opacity: 1 },
          { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) rotate(${Math.random() * 360}deg)`, opacity: 1, offset: 0.55 },
          { transform: `translate(calc(-50% + ${dx * 1.15}px), calc(-50% + ${dy + 60}px)) rotate(${Math.random() * 720}deg) scale(.5)`, opacity: 0 },
        ],
        { duration: 900 + Math.random() * 500, easing: "cubic-bezier(.15,.7,.3,1)", fill: "forwards" },
      );
    }
    setTimeout(() => layer.remove(), 1600);
  }

  // Swap views with a shared-element morph where the browser supports it.
  function transition(update) {
    if (!document.startViewTransition || reduced.matches) {
      update();
      return;
    }
    document.startViewTransition(update);
  }

  // The background drifts a little with the pointer.
  function parallax() {
    if (!finePointer.matches) return;
    let frame = 0;
    window.addEventListener("pointermove", (event) => {
      if (reduced.matches || frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const root = document.documentElement.style;
        root.setProperty("--px", ((event.clientX / window.innerWidth) * 2 - 1).toFixed(3));
        root.setProperty("--py", ((event.clientY / window.innerHeight) * 2 - 1).toFixed(3));
      });
    });
  }

  return { tilt, giftBox, burst, transition, parallax, reduced };
})();
