/**
 * The sample's brand mark.
 *
 * A logomark rather than a photo logo: inline SVG has no asset to load, scales cleanly, and picks up
 * the theme. The mark is a *waypoint* — a navigation arrow set on a rounded tile — which reads as
 * both travel (a heading) and the product's job (finding the way). The wordmark is the name in a
 * tight sans; the two compose into a lockup used in the sidebar and the sign-in screen.
 */

export function Logomark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="wm-grad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--accent)" />
          <stop offset="1" stopColor="var(--accent-strong)" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#wm-grad)" />
      {/* a heading arrow / paper-plane waypoint, drawn in the on-accent colour */}
      <path
        d="M28.5 12.2 12.6 18.3c-.9.35-.86 1.64.06 1.93l6.1 1.9 1.9 6.1c.29.92 1.58.96 1.93.06l6.1-15.9c.33-.86-.53-1.72-1.39-1.39Z"
        fill="var(--on-accent)"
      />
      <path
        d="m18.8 22.1 4.4-4.4"
        stroke="var(--accent-strong)"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Wordmark({ withMark = true, size = 28 }: { withMark?: boolean; size?: number }) {
  return (
    <span className="wordmark">
      {withMark && <Logomark size={size} />}
      <span className="wordmark-text">Travel Assistant</span>
    </span>
  );
}
