"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";

const CX = 160;
const CY = 164;
const R = 128;

/** value 0..100 -> SVG angle in degrees (180 = left, 360 = right, top at 270) */
function theta(v: number) {
  return 180 + 1.8 * v;
}

function pt(v: number, radius: number) {
  const t = (theta(v) * Math.PI) / 180;
  return { x: CX + radius * Math.cos(t), y: CY + radius * Math.sin(t) };
}

function arcPath(v0: number, v1: number, radius: number) {
  const a = pt(v0, radius);
  const b = pt(v1, radius);
  const large = theta(v1) - theta(v0) > 180 ? 1 : 0;
  return `M ${a.x.toFixed(2)} ${a.y.toFixed(2)} A ${radius} ${radius} 0 ${large} 1 ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
}

const MAJORS = Array.from({ length: 11 }, (_, i) => i * 10);
const MINORS = Array.from({ length: 51 }, (_, i) => i * 2).filter((v) => v % 10 !== 0);

/**
 * Signature instrument: Market Mood gauge.
 * Machined dial with major/minor ticks, zoned arc and a detented needle
 * that swings to the reading with a damped settle + idle micro-drift.
 */
export default function MoodGauge({
  score,
  label,
  status,
}: {
  score: number;
  label: string;
  status: "up" | "flat" | "down";
}) {
  const outerRef = useRef<SVGGElement | null>(null);
  const innerRef = useRef<SVGGElement | null>(null);

  useEffect(() => {
    const outer = outerRef.current;
    const inner = innerRef.current;
    if (!outer || !inner) return;

    const clamped = Math.max(0, Math.min(100, score));
    const target = 1.8 * clamped - 90;
    const origin = `${CX} ${CY}`;
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let driftTween: gsap.core.Tween | null = null;
    let timer = 0;

    if (reduce) {
      gsap.set(outer, { rotation: target, svgOrigin: origin });
      gsap.set(inner, { rotation: 0, svgOrigin: origin });
      return () => {
        driftTween?.kill();
        window.clearTimeout(timer);
      };
    }

    gsap.set(outer, { rotation: -90, svgOrigin: origin });
    gsap.set(inner, { rotation: 0, svgOrigin: origin });
    const swing = gsap.to(outer, {
      rotation: target,
      duration: 0.9,
      ease: "expo.out",
      svgOrigin: origin,
      overwrite: "auto",
    });

    // Idle micro-drift around the settled reading
    timer = window.setTimeout(() => {
      driftTween = gsap.to(inner, {
        rotation: 1.4,
        duration: 2.2,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
        svgOrigin: origin,
      });
    }, 1700);

    return () => {
      swing.kill();
      driftTween?.kill();
      window.clearTimeout(timer);
    };
  }, [score]);

  const statusColor =
    status === "up" ? "#00ff41" : status === "down" ? "#ff2d00" : "#8c8c8c";

  return (
    <div className="panel relative overflow-hidden p-6 md:p-8" data-reveal="up">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="mono-label text-primary">Market mood index</p>
          <p className="mono-label mt-2 text-dim-text">Analog reading · 0 to 100</p>
        </div>
        <span
          className="lamp"
          aria-hidden
          style={{ background: statusColor, boxShadow: `0 0 7px ${statusColor}` }}
        />
      </div>

      <div className="mt-4 flex flex-col items-center">
        <svg
          viewBox="0 0 320 196"
          className="w-full max-w-[440px]"
          role="img"
          aria-label={`Market mood gauge reading ${score} out of 100. ${label}`}
        >
          {/* Zoned arc: at risk / balanced / strong */}
          <path d={arcPath(0, 40, R)} fill="none" stroke="#3a1c17" strokeWidth="8" />
          <path d={arcPath(40, 70, R)} fill="none" stroke="#2a2d2b" strokeWidth="8" />
          <path d={arcPath(70, 100, R)} fill="none" stroke="#12331f" strokeWidth="8" />

          {/* Minor ticks */}
          {MINORS.map((v) => {
            const a = pt(v, R - 8);
            const b = pt(v, R - 15);
            return (
              <line
                key={`m${v}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="#4a4d4b"
                strokeWidth="1"
              />
            );
          })}

          {/* Major ticks + numerals */}
          {MAJORS.map((v) => {
            const a = pt(v, R - 8);
            const b = pt(v, R - 22);
            const n = pt(v, R - 38);
            return (
              <g key={`M${v}`}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={v >= 70 ? "#00ff41" : v <= 40 ? "#ff2d00" : "#8c8c8c"}
                  strokeWidth="1.5"
                />
                <text
                  x={n.x}
                  y={n.y + 3}
                  textAnchor="middle"
                  fontSize="10"
                  fill="#8c8c8c"
                  style={{ fontFamily: "var(--font-plex-mono)" }}
                >
                  {v}
                </text>
              </g>
            );
          })}

          {/* Needle assembly: outer = detent swing, inner = idle drift */}
          <g ref={outerRef}>
            <g ref={innerRef}>
              <line
                x1={CX}
                y1={CY}
                x2={CX}
                y2={CY - (R - 30)}
                stroke="#ff2d00"
                strokeWidth="2"
              />
              <polygon
                points={`${CX - 4},${CY - (R - 30)} ${CX + 4},${CY - (R - 30)} ${CX},${CY - (R - 18)}`}
                fill="#ff2d00"
              />
            </g>
          </g>

          {/* Hub */}
          <rect
            x={CX - 7}
            y={CY - 7}
            width="14"
            height="14"
            fill="#141614"
            stroke="#2a2d2b"
            strokeWidth="2"
          />
          <rect x={CX - 2} y={CY - 2} width="4" height="4" fill="#ff2d00" />

          {/* Scale terminals */}
          <text
            x={pt(0, R).x}
            y={pt(0, R).y + 18}
            textAnchor="middle"
            fontSize="9"
            fill="#8c8c8c"
            style={{ fontFamily: "var(--font-plex-mono)" }}
          >
            TIGHT
          </text>
          <text
            x={pt(100, R).x}
            y={pt(100, R).y + 18}
            textAnchor="middle"
            fontSize="9"
            fill="#8c8c8c"
            style={{ fontFamily: "var(--font-plex-mono)" }}
          >
            LOOSE
          </text>
        </svg>

        <div className="-mt-6 text-center">
          <p className="display text-[clamp(3.5rem,2.5rem+4vw,5.5rem)] leading-none text-primary">
            {String(score).padStart(2, "0")}
          </p>
          <p className="mono-label mt-3 text-neutral-beige">{label}</p>
        </div>
      </div>
    </div>
  );
}
