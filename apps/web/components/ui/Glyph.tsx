// Hand-drawn glyphs, 24 px grid, 1.5 px stroke, flat caps.
import type { SVGProps } from "react";

export type GlyphName =
  | "import"
  | "layers"
  | "compare"
  | "measure"
  | "fit"
  | "zoom-in"
  | "zoom-out"
  | "actual"
  | "close"
  | "check"
  | "arrow-right"
  | "chevron-down"
  | "chevron-up"
  | "chevron-left"
  | "image"
  | "histogram"
  | "plus"
  | "minus"
  | "trash"
  | "command";

type Props = Omit<SVGProps<SVGSVGElement>, "name"> & {
  name: GlyphName;
  size?: number;
};

const paths: Record<GlyphName, React.ReactNode> = {
  import: (
    <>
      <path d="M12 4.2v9.6" />
      <path d="M8.7 10.5 12 13.9l3.3-3.4" />
      <path d="M4.6 15.4v2.6c0 .8.6 1.4 1.4 1.4h12c.8 0 1.4-.6 1.4-1.4v-2.6" />
    </>
  ),
  layers: (
    <>
      <path d="M4.6 9.2h11.2v10.2H4.6z" />
      <path d="M8.4 5.2h10.9v10.1" />
    </>
  ),
  compare: (
    <>
      <path d="M4.2 6.4h15.6v11.2H4.2z" />
      <path d="M12 3.8v16.4" />
      <path d="M9.7 11.9H6.9M14.3 11.9h2.8" />
    </>
  ),
  measure: (
    <>
      <path d="M5.2 4.4v15.2" />
      <path d="M5.2 4.4h4.2M5.2 19.6h4.2" />
      <path d="M5.2 8.6h2.6M5.2 12.1h3.4M5.2 15.5h2.6" />
      <path d="M12.4 4.4h6.4M12.4 19.6h6.4" />
    </>
  ),
  fit: (
    <>
      <path d="M9.2 4.4H4.4v4.8" />
      <path d="M14.8 4.4h4.8v4.8" />
      <path d="M9.2 19.6H4.4v-4.8" />
      <path d="M14.8 19.6h4.8v-4.8" />
    </>
  ),
  "zoom-in": (
    <>
      <path d="M11 4.9a6.1 6.1 0 1 0 .1 12.2A6.1 6.1 0 0 0 11 4.9Z" />
      <path d="M15.5 15.6 19.8 20" />
      <path d="M8.5 11h5M11 8.5v5" />
    </>
  ),
  "zoom-out": (
    <>
      <path d="M11 4.9a6.1 6.1 0 1 0 .1 12.2A6.1 6.1 0 0 0 11 4.9Z" />
      <path d="M15.5 15.6 19.8 20" />
      <path d="M8.5 11h5" />
    </>
  ),
  actual: (
    <>
      <path d="M4.4 4.4h15.2v15.2H4.4z" />
      <path d="M9.3 9.3h5.4v5.4H9.3z" />
    </>
  ),
  close: (
    <>
      <path d="M6.2 6.2 17.8 17.8M17.8 6.2 6.2 17.8" />
    </>
  ),
  check: (
    <>
      <path d="M4.6 12.4 9.2 17 19.4 6.8" />
    </>
  ),
  "arrow-right": (
    <>
      <path d="M4.4 12h14.8" />
      <path d="M14.2 6.8 19.4 12l-5.2 5.2" />
    </>
  ),
  "chevron-down": (
    <>
      <path d="M6.2 9.6 12 15.2l5.8-5.6" />
    </>
  ),
  "chevron-up": (
    <>
      <path d="M6.2 14.4 12 8.8l5.8 5.6" />
    </>
  ),
  "chevron-left": (
    <>
      <path d="M14.4 6.2 8.8 12l5.6 5.8" />
    </>
  ),
  image: (
    <>
      <path d="M4.4 5.4h15.2v13.2H4.4z" />
      <path d="M4.4 15.2 9 10.6l3.6 3.6 2.9-2.6 4.1 4" />
      <path d="M15.1 8.4a1.1 1.1 0 1 0 .1 2.2 1.1 1.1 0 0 0-.1-2.2Z" />
    </>
  ),
  histogram: (
    <>
      <path d="M4.4 19.4h15.2" />
      <path d="M6.6 19.4v-5.2M10.6 19.4V8.2M14.6 19.4v-3.4M18.4 19.4v-7" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5.2v13.6M5.2 12h13.6" />
    </>
  ),
  minus: (
    <>
      <path d="M5.2 12h13.6" />
    </>
  ),
  trash: (
    <>
      <path d="M5.4 7.4h13.2" />
      <path d="M9.2 7.4V5.2h5.6v2.2" />
      <path d="M6.8 7.4l.9 11.4h9.4l.9-11.4" />
    </>
  ),
  command: (
    <>
      <path d="M9.2 9.2h5.6v5.6H9.2z" />
      <path d="M9.2 9.2V7.1a1.9 1.9 0 1 0-1.9 1.9h1.9Z" />
      <path d="M14.8 9.2h2.1a1.9 1.9 0 1 0-1.9-1.9v1.9Z" />
      <path d="M9.2 14.8H7.1a1.9 1.9 0 1 0 1.9 1.9v-1.9Z" />
      <path d="M14.8 14.8h2.1a1.9 1.9 0 1 1-1.9 1.9v-1.9Z" />
    </>
  ),
};

export function Glyph({ name, size = 18, className, ...rest }: Props) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="butt"
      strokeLinejoin="miter"
      aria-hidden="true"
      focusable="false"
      className={className}
      {...rest}
    >
      {paths[name]}
    </svg>
  );
}
