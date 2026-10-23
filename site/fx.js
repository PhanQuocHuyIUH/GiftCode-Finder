"use strict";

// Visual effects: card tilt, the 3D gift box, confetti, page transitions.
// Built to stay light on phones: the box spins with a CSS animation (paused
// off screen) and JavaScript only runs while someone drags it.
const FX = (() => {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
  const clamp = (value, low, high) => Math.min(Math.max(value, low), high);

  // Lean `card` toward a mouse pointer. CSS reads --tx/--ty (-1..1) for the
  // rotation and --mx/--my for the highlight.
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
      if (!frame) frame = requestAnimationFrame(apply);
    });
    card.addEventListener("pointerleave", () => {
      point = null;
      for (const name of ["--tx", "--ty"]) card.style.removeProperty(name);
    });
  }

  // The gift box built by app.js: drag .gift-area to turn it, click it (or
  // Enter on .box-hit) to open it and let the .chip elements out.
  function giftBox(scene) {
    const area = scene.querySelector(".gift-area");
    const turn = scene.querySelector(".box-turn");
    const toggle = scene.querySelector(".box-hit");
    const chips = [...scene.querySelectorAll(".chip")];
    const rest = -16; // the tilt the box settles back to
    let rx = rest;
    let ry = 0;
    let speed = 0; // degrees per ms left over from a flick
    let drag = null;
    let frame = 0;

    const apply = () => {
      turn.style.setProperty("--rx", `${rx.toFixed(2)}deg`);
      turn.style.setProperty("--ry", `${ry.toFixed(2)}deg`);
    };

    function setOpen(open) {
      scene.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      chips.forEach((chip, i) => {
        chip.tabIndex = open ? 0 : -1;
        chip.style.setProperty("--d", `${120 + i * 45}ms`);
      });
      if (open) {
        const box = area.getBoundingClientRect();
        burst(box.left + box.width / 2, box.top + box.height * 0.4);
      }
    }

    // After a flick: coast to a stop, then the CSS idle spin carries on.
    function coast() {
      let last = performance.now();
      const step = (now) => {
        const dt = Math.min(now - last, 48);
        last = now;
        ry += speed * dt;
        speed *= Math.pow(0.994, dt);
        rx += (rest - rx) * Math.min(dt * 0.004, 1);
        apply();
        frame = Math.abs(speed) > 0.005 || Math.abs(rx - rest) > 0.2 ? requestAnimationFrame(step) : 0;
      };
      frame = requestAnimationFrame(step);
    }

    area.addEventListener("pointerdown", (event) => {
      if (event.button > 0) return;
      cancelAnimationFrame(frame);
      drag = { x: event.clientX, y: event.clientY, t: event.timeStamp, moved: 0 };
      speed = 0;
      area.setPointerCapture(event.pointerId);
    });
    area.addEventListener("pointermove", (event) => {
      if (!drag) return;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      const moved = drag.moved + Math.abs(dx) + Math.abs(dy);
      if (moved > 6) scene.classList.add("is-dragging");
      ry += dx * 0.5;
      rx = clamp(rx - dy * 0.4, -60, 20);
      speed = (dx * 0.5) / Math.max(event.timeStamp - drag.t, 1);
      drag = { x: event.clientX, y: event.clientY, t: event.timeStamp, moved };
      apply();
    });
    const release = (event) => {
      if (!drag) return;
      const tap = drag.moved <= 6;
      drag = null;
      scene.classList.remove("is-dragging");
      if (tap && event.type === "pointerup") setOpen(!scene.classList.contains("is-open"));
      else if (!reduced.matches) coast();
    };
    area.addEventListener("pointerup", release);
    area.addEventListener("pointercancel", release);
    toggle.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      setOpen(!scene.classList.contains("is-open"));
    });

    // No spinning while the box is scrolled out of view.
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(([entry]) => scene.classList.toggle("is-away", !entry.isIntersecting)).observe(area);
    }
    for (const chip of chips) chip.tabIndex = -1;
  }

  const CONFETTI = ["#ff6fae", "#a594ff", "#38d9f0", "#ffc24b", "#4ade80"];

  // A short confetti pop at a point on screen (client coordinates).
  function burst(x, y, colors = CONFETTI, count = finePointer.matches ? 20 : 12) {
    if (reduced.matches || !Element.prototype.animate) return;
    const layer = document.createElement("div");
    layer.className = "burst";
    layer.style.left = `${x}px`;
    layer.style.top = `${y}px`;
    document.body.append(layer);
    for (let i = 0; i < count; i++) {
      const bit = document.createElement("i");
      bit.style.background = colors[i % colors.length];
      layer.append(bit);
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5;
      const distance = 40 + Math.random() * 60;
      const dx = Math.cos(angle) * distance;
      const dy = Math.sin(angle) * distance;
      bit.animate(
        [
          { transform: "translate(-50%, -50%) scale(1)", opacity: 1 },
          { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy + 40}px)) rotate(${Math.random() * 540}deg) scale(.6)`, opacity: 0 },
        ],
        { duration: 700 + Math.random() * 300, easing: "cubic-bezier(.2,.7,.3,1)", fill: "forwards" },
      );
    }
    setTimeout(() => layer.remove(), 1100);
  }

  // Swap views with a cross-fade where the browser supports it.
  function transition(update) {
    if (!document.startViewTransition || reduced.matches) {
      update();
      return;
    }
    document.startViewTransition(update);
  }

  return { tilt, giftBox, burst, transition, reduced };
})();
