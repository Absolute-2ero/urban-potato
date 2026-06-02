// frontend/src/components/mascot/MacMascot.tsx
import React from 'react'

const C = {
  green:      '#2D9B5A',
  greenMid:   '#3AB669',
  greenLight: '#52C27A',
  stem:       '#6DBF8A',
  dark:       '#1E2A2A',
  white:      '#FFFFFF',
  sweat:      '#74C8F5',
  amber:      '#F5A623',
  blush:      '#F4A0A0',
}

const CSS = `
  @keyframes mac-bob    { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-3px)} }
  @keyframes mac-jump   { 0%,100%{transform:translateY(0)} 40%{transform:translateY(-11px)} 60%{transform:translateY(-9px)} }
  @keyframes mac-wiggle { 0%,100%{transform:rotate(0deg)} 25%{transform:rotate(-8deg)} 75%{transform:rotate(8deg)} }
  @keyframes mac-zup    { 0%{opacity:1;transform:translateY(0)} 100%{opacity:0;transform:translateY(-14px)} }
  @keyframes mac-pulse  { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.4;transform:scale(0.6)} }
  @keyframes mac-pop    { 0%,100%{opacity:0.3;transform:scale(0.85)} 50%{opacity:1;transform:scale(1.1)} }
  .mac-idle     { animation: mac-bob    2.5s ease-in-out infinite }
  .mac-happy    { animation: mac-bob    1.8s ease-in-out infinite }
  .mac-sweat    { animation: mac-bob    1.0s ease-in-out infinite }
  .mac-excited  { animation: mac-jump   0.75s ease-in-out infinite }
  .mac-sleep    { animation: mac-bob    4.0s ease-in-out infinite }
  .mac-cool     { animation: mac-bob    3.0s ease-in-out infinite }
  .mac-thinking { animation: mac-bob    2.0s ease-in-out infinite }
  .mac-cheer    { animation: mac-wiggle 0.65s ease-in-out infinite }
  .mac-z1  { animation: mac-zup   2.0s ease-in-out infinite }
  .mac-z2  { animation: mac-zup   2.0s ease-in-out infinite 0.85s }
  .mac-sp1 { animation: mac-pulse 0.9s ease-in-out infinite }
  .mac-sp2 { animation: mac-pulse 0.9s ease-in-out infinite 0.35s }
  .mac-sp3 { animation: mac-pulse 0.9s ease-in-out infinite 0.65s }
  .mac-tb1 { animation: mac-pop   1.6s ease-in-out infinite }
  .mac-tb2 { animation: mac-pop   1.6s ease-in-out infinite 0.4s }
  .mac-tb3 { animation: mac-pop   1.6s ease-in-out infinite 0.8s }
`

// Inject once into <head> — avoids React 18.3 <style> hoisting / removeChild crash
if (typeof document !== 'undefined' && !document.getElementById('mac-mascot-css')) {
  const _s = document.createElement('style')
  _s.id = 'mac-mascot-css'
  _s.textContent = CSS
  document.head.appendChild(_s)
}

export type MacEmotion =
  | 'idle'
  | 'happy'
  | 'sweat'
  | 'excited'
  | 'sleep'
  | 'cool'
  | 'thinking'
  | 'cheer'

interface MacMascotProps {
  emotion?: MacEmotion
  size?: number
  className?: string
}

const NORMAL_EYE_EMOTIONS: MacEmotion[] = ['idle', 'sweat', 'excited']

export const MacMascot: React.FC<MacMascotProps> = ({
  emotion = 'idle',
  size = 80,
  className,
}) => {
  const raisedArms = emotion === 'excited' || emotion === 'cheer'
  const thinkArm   = emotion === 'thinking'
  const normalEyes = NORMAL_EYE_EMOTIONS.includes(emotion)

  return (
    <svg
      width={size}
      height={Math.round(size * 1.25)}
      viewBox="0 0 80 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label={`Mac the mascot — ${emotion}`}
      className={className}
    >
      <g className={`mac-${emotion}`} style={{ transformOrigin: '40px 80px' }}>

        {/* ── BROCCOLI HEAD ──────────────────────────────────────── */}
        {/* Main floret body */}
        <circle cx="40" cy="46" r="27" fill={C.green} />
        {/* Top bumps */}
        <circle cx="40" cy="18" r="14" fill={C.green} />
        <circle cx="22" cy="25" r="13" fill={C.green} />
        <circle cx="58" cy="25" r="13" fill={C.green} />
        {/* Highlight sheen on bumps */}
        <circle cx="37" cy="12" r="5"  fill={C.greenMid} opacity="0.5" />
        <circle cx="18" cy="21" r="4"  fill={C.greenMid} opacity="0.5" />
        <circle cx="54" cy="20" r="4"  fill={C.greenMid} opacity="0.5" />

        {/* ── STEM / BODY ─────────────────────────────────────────── */}
        <rect x="27" y="65" width="26" height="26" rx="10" fill={C.stem} />
        <rect x="30" y="67" width="9"  height="11" rx="4"  fill={C.white} opacity="0.22" />

        {/* ── ARMS ────────────────────────────────────────────────── */}
        {raisedArms ? (
          <>
            <rect x="3"  y="54" width="21" height="10" rx="5" fill={C.stem} transform="rotate(-45 13 59)" />
            <rect x="56" y="54" width="21" height="10" rx="5" fill={C.stem} transform="rotate(45  67 59)" />
          </>
        ) : thinkArm ? (
          <>
            <rect x="7"  y="68" width="19" height="10" rx="5" fill={C.stem} />
            <rect x="55" y="54" width="19" height="10" rx="5" fill={C.stem} transform="rotate(-40 64 59)" />
          </>
        ) : (
          <>
            <rect x="7"  y="68" width="19" height="10" rx="5" fill={C.stem} />
            <rect x="54" y="68" width="19" height="10" rx="5" fill={C.stem} />
          </>
        )}

        {/* ── EYES ────────────────────────────────────────────────── */}

        {/* SLEEP — closed curved lines */}
        {emotion === 'sleep' && (
          <>
            <path d="M23 47 Q29 43 35 47" stroke={C.dark} strokeWidth="2.5" strokeLinecap="round" />
            <path d="M45 47 Q51 43 57 47" stroke={C.dark} strokeWidth="2.5" strokeLinecap="round" />
          </>
        )}

        {/* HAPPY / CHEER — upward arc squints */}
        {(emotion === 'happy' || emotion === 'cheer') && (
          <>
            <path d="M23 49 Q29 43 35 49" stroke={C.dark} strokeWidth="2.5" strokeLinecap="round" />
            <path d="M45 49 Q51 43 57 49" stroke={C.dark} strokeWidth="2.5" strokeLinecap="round" />
            <ellipse cx="22" cy="52" rx="5" ry="2.5" fill={C.blush} opacity="0.55" />
            <ellipse cx="58" cy="52" rx="5" ry="2.5" fill={C.blush} opacity="0.55" />
          </>
        )}

        {/* COOL — sunglasses */}
        {emotion === 'cool' && (
          <>
            <rect x="18" y="41" width="17" height="11" rx="6"  fill={C.dark} />
            <rect x="45" y="41" width="17" height="11" rx="6"  fill={C.dark} />
            <line x1="35" y1="46.5" x2="45" y2="46.5" stroke={C.dark} strokeWidth="2.5" />
            <line x1="18" y1="44"   x2="13" y2="42"   stroke={C.dark} strokeWidth="2" />
            <line x1="62" y1="44"   x2="67" y2="42"   stroke={C.dark} strokeWidth="2" />
            <rect x="20" y="43" width="7" height="4" rx="2" fill={C.white} opacity="0.18" />
            <rect x="47" y="43" width="7" height="4" rx="2" fill={C.white} opacity="0.18" />
          </>
        )}

        {/* THINKING — one normal eye + one squint */}
        {emotion === 'thinking' && (
          <>
            <circle cx="29" cy="46" r="7.5" fill={C.white} stroke={C.dark} strokeWidth="1.5" />
            <circle cx="30" cy="47" r="3.5"  fill={C.dark} />
            <circle cx="28" cy="44.5" r="1.3" fill={C.white} />
            <path d="M44 49 Q51 43 58 49" stroke={C.dark} strokeWidth="2.5" strokeLinecap="round" />
            <path d="M44 47 Q51 50 58 47" stroke={C.dark} strokeWidth="1.2" strokeLinecap="round" opacity="0.3" />
          </>
        )}

        {/* IDLE / SWEAT / EXCITED — standard white circle eyes */}
        {normalEyes && (
          <>
            <circle cx="29" cy="46" r="7.5" fill={C.white} stroke={C.dark} strokeWidth="1.5" />
            <circle cx="51" cy="46" r="7.5" fill={C.white} stroke={C.dark} strokeWidth="1.5" />
            {emotion === 'sweat' ? (
              <>
                {/* Wide pupils for anxiety */}
                <circle cx="30" cy="47" r="5.2" fill={C.dark} />
                <circle cx="52" cy="47" r="5.2" fill={C.dark} />
                <circle cx="27.5" cy="44" r="1.5" fill={C.white} />
                <circle cx="49.5" cy="44" r="1.5" fill={C.white} />
              </>
            ) : emotion === 'excited' ? (
              <>
                {/* Bigger bright pupils */}
                <circle cx="30" cy="47" r="4.2" fill={C.dark} />
                <circle cx="52" cy="47" r="4.2" fill={C.dark} />
                <circle cx="27.5" cy="44" r="1.5" fill={C.white} />
                <circle cx="49.5" cy="44" r="1.5" fill={C.white} />
              </>
            ) : (
              <>
                <circle cx="30" cy="47" r="3.5" fill={C.dark} />
                <circle cx="52" cy="47" r="3.5" fill={C.dark} />
                <circle cx="28"  cy="44.5" r="1.2" fill={C.white} />
                <circle cx="50"  cy="44.5" r="1.2" fill={C.white} />
              </>
            )}
          </>
        )}

        {/* ── MOUTH ───────────────────────────────────────────────── */}
        {emotion === 'idle'     && <path d="M34 57 Q40 62 46 57" stroke={C.dark} strokeWidth="2"   strokeLinecap="round" fill="none" />}
        {emotion === 'happy'    && <path d="M31 56 Q40 63 49 56" stroke={C.dark} strokeWidth="2.5" strokeLinecap="round" fill="none" />}
        {emotion === 'sweat'    && <path d="M34 58 Q40 55 46 58" stroke={C.dark} strokeWidth="2"   strokeLinecap="round" fill="none" />}
        {emotion === 'excited'  && <ellipse cx="40" cy="58" rx="6"  ry="5.5" fill={C.dark} />}
        {emotion === 'sleep'    && <path d="M35 58 Q40 60 45 58" stroke={C.dark} strokeWidth="2"   strokeLinecap="round" fill="none" />}
        {emotion === 'cool'     && <path d="M34 56 Q42 60 48 55" stroke={C.dark} strokeWidth="2"   strokeLinecap="round" fill="none" />}
        {emotion === 'thinking' && <path d="M33 58 Q38 61 43 57" stroke={C.dark} strokeWidth="2"   strokeLinecap="round" fill="none" />}
        {emotion === 'cheer'    && (
          <>
            <path d="M30 55 Q40 65 50 55" stroke={C.dark} strokeWidth="2.5" strokeLinecap="round" fill="none" />
            <path d="M30 55 Q40 65 50 55 L40 59 Z"         fill={C.dark} opacity="0.1" />
          </>
        )}

        {/* ── SPECIAL EFFECTS ─────────────────────────────────────── */}

        {/* Sweat drop — tilted teardrop on forehead */}
        {emotion === 'sweat' && (
          <g transform="translate(55 24) rotate(12)">
            <path d="M0,9 C-3.5,4 -3.5,-1 0,-3.5 C3.5,-1 3.5,4 0,9 Z" fill={C.sweat} />
          </g>
        )}

        {/* Sleep Z's — path-based letters so no font needed */}
        {emotion === 'sleep' && (
          <>
            <g className="mac-z1">
              <path d="M57,31 L64,31 L57,40 L64,40" stroke={C.stem}       strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </g>
            <g className="mac-z2">
              <path d="M65,18 L74,18 L65,29 L74,29" stroke={C.greenLight} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </g>
          </>
        )}

        {/* Excited / Cheer sparkles — plus-star shapes */}
        {(emotion === 'excited' || emotion === 'cheer') && (
          <>
            <g className="mac-sp1">
              <path d="M11,26 L11,20 M8,23 L14,23" stroke={C.amber} strokeWidth="2.5" strokeLinecap="round" />
            </g>
            <g className="mac-sp2">
              <path d="M68,18 L68,12 M65,15 L71,15" stroke={C.amber} strokeWidth="2.5" strokeLinecap="round" />
            </g>
            <g className="mac-sp3">
              <path d="M73,38 L73,33 M70,35.5 L76,35.5" stroke={C.amber} strokeWidth="2"   strokeLinecap="round" />
            </g>
            <circle cx="6" cy="44" r="3.5" fill={C.amber} className="mac-sp2" />
          </>
        )}

        {/* Thinking bubbles — three ascending circles */}
        {emotion === 'thinking' && (
          <>
            <circle cx="58" cy="28" r="2.5" fill={C.white} stroke={C.dark} strokeWidth="1.2" className="mac-tb1" />
            <circle cx="65" cy="20" r="4"   fill={C.white} stroke={C.dark} strokeWidth="1.2" className="mac-tb2" />
            <circle cx="72" cy="11" r="6"   fill={C.white} stroke={C.dark} strokeWidth="1.2" className="mac-tb3" />
            {/* "..." inside largest bubble */}
            <circle cx="69" cy="11" r="1"   fill={C.dark} opacity="0.5" />
            <circle cx="72" cy="11" r="1"   fill={C.dark} opacity="0.5" />
            <circle cx="75" cy="11" r="1"   fill={C.dark} opacity="0.5" />
          </>
        )}

      </g>
    </svg>
  )
}
