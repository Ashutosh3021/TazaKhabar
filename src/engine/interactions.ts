// Pointer craft. Fine pointers only; never hides the native cursor (accessibility, usability).
//   data-magnetic="0.35"   element leans toward the pointer
//   data-cursor="View"     follower grows and shows a label over this element
import { gsap } from 'gsap';
import { isTouch, prefersReducedMotion } from './env';

export function initMagnetic(root: ParentNode = document) {
  if (isTouch() || prefersReducedMotion()) return;
  root.querySelectorAll<HTMLElement>('[data-magnetic]').forEach((el) => {
    const strength = parseFloat(el.dataset.magnetic || '0.35');
    const x = gsap.quickTo(el, 'x', { duration: 0.6, ease: 'power3.out' });
    const y = gsap.quickTo(el, 'y', { duration: 0.6, ease: 'power3.out' });
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      x((e.clientX - (r.left + r.width / 2)) * strength);
      y((e.clientY - (r.top + r.height / 2)) * strength);
    };
    const leave = () => { x(0); y(0); };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerleave', leave);
  });
}

let follower: HTMLElement | null = null;
export function initCursor() {
  if (follower || isTouch() || prefersReducedMotion()) return;
  follower = document.getElementById('cursor');
  if (!follower) return;
  const label = follower.querySelector<HTMLElement>('[data-cursor-label]');
  const x = gsap.quickTo(follower, 'x', { duration: 0.45, ease: 'power3.out' });
  const y = gsap.quickTo(follower, 'y', { duration: 0.45, ease: 'power3.out' });
  addEventListener('pointermove', (e) => {
    x(e.clientX); y(e.clientY);
    const target = (e.target as HTMLElement).closest<HTMLElement>('[data-cursor]');
    const text = target?.dataset.cursor || '';
    follower!.classList.toggle('is-active', !!text);
    if (label && label.textContent !== text) label.textContent = text;
  }, { passive: true });
  document.addEventListener('pointerleave', () => follower!.classList.remove('is-active'));
  follower.classList.add('is-ready');
}
