/**
 * CicadaLogo - Cute Cicada Logo Component
 * Orange-themed cicada icon with customizable size and color
 */

const CicadaLogo = ({ size = 24, color = 'currentColor', className = '' }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 64 64"
    width={size}
    height={size}
    fill="none"
    className={className}
    style={{ color }}
  >
    {/* Wings */}
    <ellipse cx="20" cy="42" rx="6" ry="18" fill="currentColor" fillOpacity="0.4" transform="rotate(8 20 42)"/>
    <ellipse cx="44" cy="42" rx="6" ry="18" fill="currentColor" fillOpacity="0.4" transform="rotate(-8 44 42)"/>
    <ellipse cx="21" cy="44" rx="4" ry="14" fill="currentColor" fillOpacity="0.25" transform="rotate(8 21 44)"/>
    <ellipse cx="43" cy="44" rx="4" ry="14" fill="currentColor" fillOpacity="0.25" transform="rotate(-8 43 44)"/>

    {/* Body */}
    <ellipse cx="32" cy="40" rx="10" ry="16" fill="currentColor"/>
    <ellipse cx="32" cy="38" rx="7" ry="10" fill="currentColor" fillOpacity="0.7"/>

    {/* Body segments */}
    <path d="M25 42 Q32 44 39 42" stroke="currentColor" strokeOpacity="0.8" strokeWidth="1.5" fill="none"/>
    <path d="M26 48 Q32 50 38 48" stroke="currentColor" strokeOpacity="0.8" strokeWidth="1.5" fill="none"/>

    {/* Head */}
    <circle cx="32" cy="18" r="14" fill="currentColor"/>
    <circle cx="32" cy="17" r="12" fill="currentColor" fillOpacity="0.7"/>

    {/* Eyes */}
    <circle cx="26" cy="17" r="6" fill="white"/>
    <circle cx="38" cy="17" r="6" fill="white"/>
    <circle cx="27" cy="16" r="3.5" fill="#431407"/>
    <circle cx="39" cy="16" r="3.5" fill="#431407"/>
    <circle cx="28.5" cy="14.5" r="1.5" fill="white"/>
    <circle cx="40.5" cy="14.5" r="1.5" fill="white"/>

    {/* Smile */}
    <path d="M28 23 Q32 26 36 23" stroke="#431407" strokeWidth="1.5" strokeLinecap="round" fill="none"/>

    {/* Antenna */}
    <path d="M26 6 Q22 2 20 6" stroke="currentColor" strokeOpacity="0.8" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
    <path d="M38 6 Q42 2 44 6" stroke="currentColor" strokeOpacity="0.8" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
    <circle cx="20" cy="6" r="2" fill="currentColor"/>
    <circle cx="44" cy="6" r="2" fill="currentColor"/>
  </svg>
);

export default CicadaLogo;
