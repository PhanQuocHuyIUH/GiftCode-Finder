"use strict";

// Visual effects: the 3D backdrop, card tilt, the gift box, the patch carousel,
// count-ups, confetti and page transitions. Built to stay light on phones:
// everything that loops is a CSS transform animation (paused off screen or in a
// background tab); JavaScript only runs while someone drags or scrolls.
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
    pauseAway(scene, area);
    for (const chip of chips) chip.tabIndex = -1;
  }

  // Floating wireframe shapes in the backdrop. Fewer on small screens.
  function scene() {
    const root = document.querySelector(".scene");
    if (!root) return;
    const holder = root.querySelector(".shapes");
    const small = window.matchMedia("(max-width: 640px)").matches;
    const specs = [
      { type: "gyro", x: 86, y: 14, s: 110, c: "#22d3ee", spin: 30, delay: -3 },
      { type: "cube", x: 6, y: 18, s: 70, c: "#ff4fd8", spin: 26, delay: 0 },
      { type: "pyramid", x: 78, y: 62, s: 80, c: "#ffc94d", spin: 24, delay: -5 },
      { type: "cube", x: 14, y: 70, s: 46, c: "#8b5cf6", spin: 20, delay: -2 },
      { type: "gyro", x: 48, y: 8, s: 54, c: "#ff4fd8", spin: 34, delay: -6 },
    ].slice(0, small ? 0 : 5); // phones keep their compositor for the gift box and the hex
    for (const spec of specs) {
      const inner = document.createElement("div");
      inner.className = `shape-in ${spec.type}`;
      const faces = { cube: 6, gyro: 4, pyramid: 4 }[spec.type];
      for (let i = 0; i < faces; i++) inner.append(document.createElement("i"));
      const shape = document.createElement("div");
      shape.className = "shape";
      shape.style.cssText = `left:${spec.x}%;top:${spec.y}%;--s:${small ? spec.s * 0.7 : spec.s}px;--c:${spec.c};--spin:${spec.spin}s;--delay:${spec.delay}s`;
      shape.append(inner);
      holder.append(shape);
    }
    if (!small) {
      // Drifting aurora blobs behind everything (gradients only, moved by transform).
      for (const name of ["b1", "b2", "b3"]) {
        const blob = document.createElement("i");
        blob.className = `blob ${name}`;
        root.querySelector(".sky").after(blob);
      }
    }
    spotlight();
    const still = () => root.classList.toggle("is-still", document.hidden || reduced.matches);
    document.addEventListener("visibilitychange", still);
    reduced.addEventListener?.("change", still);
    still();
  }

  // Patch cards on a carousel: each card turns toward the middle like a
  // cover flow. Only runs on scroll, one frame at a time.
  function coverflow(track, onPick) {
    const cards = [...track.children];
    let frame = 0;
    const apply = () => {
      frame = 0;
      const mid = track.scrollLeft + track.clientWidth / 2;
      for (const card of cards) {
        // Layout boxes, not the turned ones: offsetLeft ignores transforms.
        const offset = (card.offsetLeft + card.offsetWidth / 2 - mid) / (card.offsetWidth + 14);
        const o = clamp(offset, -3, 3);
        card.style.setProperty("--ry", `${(-o * 26).toFixed(1)}deg`);
        card.style.setProperty("--tz", `${(-Math.abs(o) * 70).toFixed(0)}px`);
        card.style.setProperty("--op", (1 - Math.min(Math.abs(o), 3) * 0.16).toFixed(2));
      }
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(apply);
    };
    track.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });
    const center = (card, smooth) => {
      const left = card.offsetLeft - (track.clientWidth - card.offsetWidth) / 2;
      track.scrollTo({ left, behavior: smooth && !reduced.matches ? "smooth" : "auto" });
      schedule();
    };
    const step = (dir) => track.scrollBy({ left: dir * 194, behavior: reduced.matches ? "auto" : "smooth" });
    schedule();
    return { center, step, refresh: schedule, onPick };
  }

  // Count a number up from 0 (stats, tiles). Text is set once when reduced.
  function countUp(node, to, duration = 700) {
    if (reduced.matches || to <= 0) {
      node.textContent = String(to);
      return;
    }
    const start = performance.now();
    const step = (now) => {
      const t = Math.min((now - start) / duration, 1);
      node.textContent = String(Math.round(to * (1 - Math.pow(1 - t, 3))));
      if (t < 1) requestAnimationFrame(step);
    };
    node.textContent = "0";
    requestAnimationFrame(step);
  }

  // Sections fly in (a short 3D swing) the first time they scroll into view.
  function reveal(nodes) {
    if (reduced.matches || !("IntersectionObserver" in window)) return;
    const seen = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-in");
          seen.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    for (const node of nodes) {
      const box = node.getBoundingClientRect();
      if (box.top < window.innerHeight) continue; // already on screen: no flash
      node.classList.add("reveal");
      seen.observe(node);
    }
  }

  // A soft light that follows the mouse (desktop only, one transform per frame).
  function spotlight() {
    if (!finePointer.matches || reduced.matches) return;
    const spot = document.createElement("div");
    spot.className = "spot";
    spot.setAttribute("aria-hidden", "true");
    document.body.append(spot);
    let frame = 0;
    let x = 0;
    let y = 0;
    window.addEventListener(
      "pointermove",
      (event) => {
        x = event.clientX;
        y = event.clientY;
        if (!frame)
          frame = requestAnimationFrame(() => {
            frame = 0;
            spot.style.transform = `translate(${x - 300}px, ${y - 300}px)`;
            spot.classList.add("on");
          });
      },
      { passive: true },
    );
    document.addEventListener("pointerleave", () => spot.classList.remove("on"));
  }

  // Pause looping decorations (gift box, hex prism) while they are off screen.
  function pauseAway(node, target = node) {
    if (!("IntersectionObserver" in window)) return;
    new IntersectionObserver(([entry]) => node.classList.toggle("is-away", !entry.isIntersecting)).observe(target);
  }

  const CONFETTI = ["#ff4fd8", "#b18cff", "#22d3ee", "#ffc94d", "#34d399"];

  // A short confetti pop at a point on screen (client coordinates).
  function burst(x, y, colors = CONFETTI, count = finePointer.matches ? 26 : 14) {
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
      const distance = 50 + Math.random() * 80;
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

  return { tilt, giftBox, burst, transition, scene, coverflow, countUp, pauseAway, reveal, reduced, finePointer };
})();
