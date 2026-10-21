// Global motion for TazaKhabar: runs once on the client, before the first page initializes.
// The concept is a machined measuring instrument, so everything SHUTTERS and DETENTS:
// the curtain is a two-stage shutter (panel drops with a red leading edge, lifts off), and the
// loader is a power-on self-test readout, not a progress bar.
import { gsap } from 'gsap';
import { ease, setLoaderExit, setLoaderFormat, setTransition } from '@/engine';

export function setupMotion() {
  // Counter reads like a machine index: 000 to 100.
  setLoaderFormat((p) => String(Math.round(p)).padStart(3, '0'));

  // Loader -> first panel handoff: the readout ticks up in steps, then the plate lifts off.
  setLoaderExit((root) =>
    gsap.timeline()
      .to(root.querySelectorAll('[data-loader-out]'), {
        yPercent: -120,
        duration: 0.4,
        ease: ease.inOut,
        stagger: 0.04,
      })
      .to(root, { clipPath: 'inset(0% 0% 100% 0%)', duration: 0.6, ease: ease.inOut }, '-=0.22'),
  );

  // Curtain: a machined shutter. A solid ground panel with a 2px accent leading edge drops over
  // the page, then lifts off the next one. Fast: this is an app, not a film.
  setTransition({
    leave: (c) =>
      gsap.timeline()
        .set(c, { autoAlpha: 1 })
        .set(c.querySelector('.curtain__panel'), { yPercent: 0 })
        .fromTo(
          c.querySelector('.curtain__panel'),
          { yPercent: -100 },
          { yPercent: 0, duration: 0.5, ease: ease.inOut },
        ),
    enter: (c) =>
      gsap.timeline()
        .to(c.querySelector('.curtain__panel'), { yPercent: 100, duration: 0.55, ease: ease.inOut })
        .set(c, { autoAlpha: 0 }),
  });
}
