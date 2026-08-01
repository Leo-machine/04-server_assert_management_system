/** 南方电网品牌标志 —— 简化 SVG 版本 */
export default function CSGLogo({ size = 26 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="中国南方电网"
    >
      {/* 外圈 */}
      <circle cx="24" cy="24" r="22" stroke="#ffffff" strokeWidth="2.5" fill="none" />
      {/* 内部电网塔抽象图形 */}
      <line x1="24" y1="6" x2="24" y2="18" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
      <line x1="24" y1="30" x2="24" y2="42" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
      <line x1="6" y1="24" x2="18" y2="24" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
      <line x1="30" y1="24" x2="42" y2="24" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
      {/* 对角线 */}
      <line x1="11.3" y1="11.3" x2="16" y2="16" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="32" y1="32" x2="36.7" y2="36.7" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="11.3" y1="36.7" x2="16" y2="32" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="32" y1="16" x2="36.7" y2="11.3" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" />
      {/* 中心菱形 */}
      <rect
        x="20" y="20" width="8" height="8" rx="1"
        fill="#ffffff" opacity="0.9"
        transform="rotate(45 24 24)"
      />
    </svg>
  )
}
