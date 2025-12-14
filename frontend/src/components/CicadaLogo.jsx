/**
 * CicadaLogo - 知了 Logo 组件
 * 清新科技风的知了图标，支持自定义大小和颜色
 */

const CicadaLogo = ({ size = 24, color = 'currentColor', className = '' }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 64 64"
    width={size}
    height={size}
    fill="none"
    stroke={color}
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    {/* Wings */}
    <path d="M22 25 L12 29 C8 31 6 57 18 63 C24 65 26 43 26 43" />
    <path d="M42 25 L52 29 C56 31 58 57 46 63 C40 65 38 43 38 43" />
    {/* Collar */}
    <path d="M24 22 L32 28 L40 22" strokeLinecap="butt" />
    {/* Body */}
    <path d="M27 28 L37 28 L32 54 Z" fill={color} stroke="none" />
    <path d="M27 28 L37 28 L32 54 Z" fill="none" />
    {/* Head */}
    <rect x="22" y="8" width="20" height="14" rx="7" fill="white" stroke={color} />
    {/* Eyes */}
    <circle cx="27" cy="15" r="4.5" fill="white" stroke={color} />
    <circle cx="37" cy="15" r="4.5" fill="white" stroke={color} />
    {/* Pupils */}
    <circle cx="27" cy="15" r="2" fill={color} stroke="none" />
    <circle cx="37" cy="15" r="2" fill={color} stroke="none" />
  </svg>
);

export default CicadaLogo;
