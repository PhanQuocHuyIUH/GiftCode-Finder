"use strict";

// The little motion the page has: a cross-fade between views and the
// scrolling strip of patch versions.
const FX = (() => {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

  // A horizontal strip of links: bring one into view, or page left/right.
  function strip(track) {
    const behavior = (smooth) => (smooth && !reduced.matches ? "smooth" : "auto");
    return {
      center(item, smooth) {
        track.scrollTo({ left: item.offsetLeft - (track.clientWidth - item.offsetWidth) / 2, behavior: behavior(smooth) });
      },
      step(dir) {
        track.scrollBy({ left: dir * track.clientWidth * 0.8, behavior: behavior(true) });
      },
    };
  }

  // Swap views with a cross-fade where the browser supports it.
  function transition(update) {
    if (!document.startViewTransition || reduced.matches) {
      update();
      return;
    }
    document.startViewTransition(update);
  }

  return { strip, transition };
})();
