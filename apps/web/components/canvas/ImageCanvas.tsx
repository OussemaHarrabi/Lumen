"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

export type PixelInfo = {
  x: number;
  y: number;
  r: number;
  g: number;
  b: number;
  gray: number;
};

export type CanvasLayers = {
  maskVisible: boolean;
  contourVisible: boolean;
  seriesIndex: number;
  opacity: number;
  contourWeight: number;
};

export type CanvasStatus = {
  scale: number;
  fitScale: number;
  width: number;
  height: number;
  loaded: boolean;
  failed: boolean;
  pixel: PixelInfo | null;
};

export type CanvasHandle = {
  fit: () => void;
  zoomBy: (factor: number) => void;
  actualSize: () => void;
};

export type CanvasLabels = {
  stage: string;
  loading: string;
  failed: string;
  hint: string;
  percent: string;
};

type Props = {
  imageUrl: string;
  maskUrl: string | null;
  layers: CanvasLayers;
  compare: boolean;
  onStatus?: (status: CanvasStatus) => void;
  onHistogram?: (bins: number[]) => void;
  labels: CanvasLabels;
};

const MIN_SCALE = 0.02;
const MAX_SCALE = 24;

function cssVar(el: HTMLElement, name: string, fallback: string): string {
  const value = getComputedStyle(el).getPropertyValue(name).trim();
  return value || fallback;
}

// Canvas view: zoom at cursor, drag to pan, mask and contour layers, pixel probe.
export const ImageCanvas = forwardRef<CanvasHandle, Props>(function ImageCanvas(
  { imageUrl, maskUrl, layers, compare, onStatus, onHistogram, labels },
  ref,
) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const baseRef = useRef<HTMLImageElement | null>(null);
  const maskRef = useRef<HTMLCanvasElement | null>(null);
  const contourBaseRef = useRef<HTMLCanvasElement | null>(null);
  const pixelsRef = useRef<ImageData | null>(null);
  const tintRef = useRef<{ key: string; canvas: HTMLCanvasElement } | null>(null);
  const contourTintRef = useRef<{ key: string; canvas: HTMLCanvasElement } | null>(null);
  const viewRef = useRef({ scale: 1, x: 0, y: 0 });
  const sizeRef = useRef({ width: 0, height: 0, dpr: 1 });
  const fitRef = useRef(1);
  const fittedRef = useRef(false);
  const spaceRef = useRef(false);
  const dragRef = useRef<{ mode: "pan" | "split"; startX: number; startY: number; x: number; y: number } | null>(
    null,
  );
  const splitRef = useRef(0.5);
  const frameRef = useRef(0);
  const pixelRef = useRef<PixelInfo | null>(null);

  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [split, setSplit] = useState(0.5);

  const layersRef = useRef(layers);
  layersRef.current = layers;
  const compareRef = useRef(compare);
  compareRef.current = compare;
  const statusCbRef = useRef(onStatus);
  statusCbRef.current = onStatus;

  useEffect(() => {
    splitRef.current = compare ? split : 1;
  }, [split, compare]);

  const reportStatus = useCallback(() => {
    const view = viewRef.current;
    const status: CanvasStatus = {
      scale: view.scale,
      fitScale: fitRef.current,
      width: baseRef.current?.naturalWidth ?? 0,
      height: baseRef.current?.naturalHeight ?? 0,
      loaded: ready,
      failed,
      pixel: pixelRef.current,
    };
    statusCbRef.current?.(status);
  }, [ready, failed]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    const base = baseRef.current;
    if (!canvas || !wrap) return;

    const dpr = window.devicePixelRatio || 1;
    const width = wrap.clientWidth;
    const height = wrap.clientHeight;
    if (!width || !height) return;

    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    }
    sizeRef.current = { width, height, dpr };

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    if (!base) return;

    const imageWidth = base.naturalWidth;
    const imageHeight = base.naturalHeight;
    const view = viewRef.current;
    const current = layersRef.current;

    ctx.save();
    ctx.translate(width / 2 + view.x, height / 2 + view.y);
    ctx.scale(view.scale, view.scale);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(base, -imageWidth / 2, -imageHeight / 2, imageWidth, imageHeight);

    const mask = maskRef.current;
    const contour = contourBaseRef.current;
    const showMask = mask && (current.maskVisible || current.contourVisible);
    if (showMask && mask) {
      const seriesColor = cssVar(wrap, `--series-${current.seriesIndex + 1}`, "");
      const inkColor = cssVar(wrap, "--series-4", "");
      const key = `${current.seriesIndex}|${inkColor}`;
      if (!tintRef.current || tintRef.current.key !== key) {
        tintRef.current = { key, canvas: tintCanvas(mask, seriesColor) };
        contourTintRef.current = contour ? { key, canvas: tintCanvas(contour, inkColor) } : null;
      }

      ctx.save();
      if (compareRef.current) {
        ctx.beginPath();
        ctx.rect(-imageWidth / 2, -imageHeight / 2, imageWidth * splitRef.current, imageHeight);
        ctx.clip();
      }
      if (current.maskVisible && tintRef.current) {
        ctx.globalAlpha = current.opacity;
        ctx.drawImage(tintRef.current.canvas, -imageWidth / 2, -imageHeight / 2, imageWidth, imageHeight);
        ctx.globalAlpha = 1;
      }
      if (current.contourVisible && contourTintRef.current) {
        ctx.globalAlpha = 0.95;
        const weight = Math.max(1, Math.min(3, current.contourWeight));
        for (let offset = 0; offset < weight; offset += 1) {
          const step = offset * 0.8;
          ctx.drawImage(
            contourTintRef.current.canvas,
            -imageWidth / 2 - step,
            -imageHeight / 2,
            imageWidth,
            imageHeight,
          );
          if (offset > 0) {
            ctx.drawImage(
              contourTintRef.current.canvas,
              -imageWidth / 2 + step,
              -imageHeight / 2,
              imageWidth,
              imageHeight,
            );
          }
        }
        ctx.globalAlpha = 1;
      }
      ctx.restore();
    }
    ctx.restore();

    if (compareRef.current) {
      const handleX =
        width / 2 + view.x + (imageWidth * splitRef.current - imageWidth / 2) * view.scale;
      const paper = cssVar(document.documentElement, "--paper", "");
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,0.45)";
      ctx.shadowBlur = 10;
      ctx.fillStyle = paper;
      ctx.fillRect(handleX - 1, 0, 2, height);
      ctx.restore();
    }

    reportStatus();
  }, [reportStatus]);

  const scheduleDraw = useCallback(() => {
    if (frameRef.current) return;
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = 0;
      draw();
    });
  }, [draw]);

  const fit = useCallback(() => {
    const wrap = wrapRef.current;
    const base = baseRef.current;
    if (!wrap || !base) return;
    const width = wrap.clientWidth;
    const height = wrap.clientHeight;
    if (!width || !height) return;
    const fitScale = Math.min(width / base.naturalWidth, height / base.naturalHeight) * 0.92;
    fitRef.current = fitScale;
    viewRef.current = { scale: fitScale, x: 0, y: 0 };
    fittedRef.current = true;
    scheduleDraw();
  }, [scheduleDraw]);

  const zoomAt = useCallback(
    (nextScale: number, anchorX: number, anchorY: number) => {
      const wrap = wrapRef.current;
      if (!wrap) return;
      const width = wrap.clientWidth;
      const height = wrap.clientHeight;
      const view = viewRef.current;
      const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, nextScale));
      const worldX = (anchorX - width / 2 - view.x) / view.scale;
      const worldY = (anchorY - height / 2 - view.y) / view.scale;
      viewRef.current = {
        scale,
        x: anchorX - width / 2 - worldX * scale,
        y: anchorY - height / 2 - worldY * scale,
      };
      fittedRef.current = false;
      scheduleDraw();
    },
    [scheduleDraw],
  );

  const zoomBy = useCallback(
    (factor: number) => {
      const wrap = wrapRef.current;
      if (!wrap) return;
      zoomAt(viewRef.current.scale * factor, wrap.clientWidth / 2, wrap.clientHeight / 2);
    },
    [zoomAt],
  );

  const actualSize = useCallback(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    zoomAt(1, wrap.clientWidth / 2, wrap.clientHeight / 2);
  }, [zoomAt]);

  useImperativeHandle(ref, () => ({ fit, zoomBy, actualSize }), [fit, zoomBy, actualSize]);

  // Latest callbacks, so the loader never depends on render identity.
  const scheduleRef = useRef(scheduleDraw);
  scheduleRef.current = scheduleDraw;
  const fitRefFn = useRef(fit);
  fitRefFn.current = fit;
  const histogramRef = useRef(onHistogram);
  histogramRef.current = onHistogram;

  // Load the source image, then the mask and the contours.
  useEffect(() => {
    let cancelled = false;
    setReady(false);
    setFailed(false);
    pixelsRef.current = null;
    tintRef.current = null;
    contourTintRef.current = null;

    const image = new Image();
    image.decoding = "async";
    image.crossOrigin = "anonymous";
    image.src = imageUrl;
    image
      .decode()
      .then(() => {
        if (cancelled) return;
        baseRef.current = image;
        const probe = document.createElement("canvas");
        probe.width = image.naturalWidth;
        probe.height = image.naturalHeight;
        const ctx = probe.getContext("2d", { willReadFrequently: true });
        if (ctx) {
          ctx.drawImage(image, 0, 0);
          try {
            pixelsRef.current = ctx.getImageData(0, 0, probe.width, probe.height);
            const bins = new Array<number>(64).fill(0);
            const data = pixelsRef.current.data;
            const stride = 4 * 2;
            for (let index = 0; index < data.length; index += stride) {
              const gray = 0.2126 * data[index] + 0.7152 * data[index + 1] + 0.0722 * data[index + 2];
              const bin = Math.min(63, Math.floor(gray / 4));
              bins[bin] += 1;
            }
            histogramRef.current?.(bins);
          } catch {
            pixelsRef.current = null;
          }
        }
        setReady(true);
        fittedRef.current = false;
        fitRefFn.current();
        scheduleRef.current();
      })
      .catch(() => {
        if (cancelled) return;
        const plain = new Image();
        plain.decoding = "async";
        plain.src = imageUrl;
        plain
          .decode()
          .then(() => {
            if (cancelled) return;
            baseRef.current = plain;
            setReady(true);
            fittedRef.current = false;
            fitRefFn.current();
            scheduleRef.current();
          })
          .catch(() => {
            if (!cancelled) setFailed(true);
          });
      });

    maskRef.current = null;
    if (maskUrl) {
      const maskImage = new Image();
      maskImage.crossOrigin = "anonymous";
      maskImage.src = maskUrl;
      maskImage
        .decode()
        .then(() => {
          if (!cancelled) {
            const normalized = normalizeMask(maskImage);
            maskRef.current = normalized;
            contourBaseRef.current = buildContour(normalized);
            tintRef.current = null;
            contourTintRef.current = null;
            scheduleRef.current();
          }
        })
        .catch(() => {
          // A missing mask simply leaves the layer off.
        });
    }

    return () => {
      cancelled = true;
    };
  }, [imageUrl, maskUrl]);

  useEffect(() => {
    scheduleDraw();
  }, [ready, failed, layers.maskVisible, layers.contourVisible, layers.seriesIndex, layers.opacity, layers.contourWeight, compare, split, scheduleDraw]);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const observer = new ResizeObserver(() => {
      if (fittedRef.current) {
        fit();
      } else {
        scheduleDraw();
      }
    });
    observer.observe(wrap);
    return () => observer.disconnect();
  }, [fit, scheduleDraw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const factor = Math.exp(-event.deltaY * 0.0015);
      zoomAt(viewRef.current.scale * factor, event.clientX - rect.left, event.clientY - rect.top);
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (event.code === "Space") spaceRef.current = true;
    };
    const up = (event: KeyboardEvent) => {
      if (event.code === "Space") spaceRef.current = false;
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);

  function splitFromEvent(clientX: number) {
    const wrap = wrapRef.current;
    const base = baseRef.current;
    if (!wrap || !base) return splitRef.current;
    const rect = wrap.getBoundingClientRect();
    const view = viewRef.current;
    const worldX = (clientX - rect.left - wrap.clientWidth / 2 - view.x) / view.scale;
    return Math.min(1, Math.max(0, (worldX + base.naturalWidth / 2) / base.naturalWidth));
  }

  function onPointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    const wrap = wrapRef.current;
    if (!wrap) return;
    (event.target as Element).setPointerCapture(event.pointerId);
    if (compare && !spaceRef.current) {
      dragRef.current = { mode: "split", startX: event.clientX, startY: event.clientY, x: 0, y: 0 };
      setSplit(splitFromEvent(event.clientX));
      return;
    }
    dragRef.current = {
      mode: "pan",
      startX: event.clientX,
      startY: event.clientY,
      x: viewRef.current.x,
      y: viewRef.current.y,
    };
  }

  function onPointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const drag = dragRef.current;
    if (drag?.mode === "split") {
      setSplit(splitFromEvent(event.clientX));
      return;
    }
    if (drag?.mode === "pan") {
      viewRef.current.x = drag.x + (event.clientX - drag.startX);
      viewRef.current.y = drag.y + (event.clientY - drag.startY);
      fittedRef.current = false;
      scheduleDraw();
      return;
    }

    const base = baseRef.current;
    const data = pixelsRef.current;
    if (!base || !data) return;
    const rect = wrap.getBoundingClientRect();
    const view = viewRef.current;
    const worldX = (event.clientX - rect.left - wrap.clientWidth / 2 - view.x) / view.scale;
    const worldY = (event.clientY - rect.top - wrap.clientHeight / 2 - view.y) / view.scale;
    const px = Math.floor(worldX + base.naturalWidth / 2);
    const py = Math.floor(worldY + base.naturalHeight / 2);
    if (px < 0 || py < 0 || px >= data.width || py >= data.height) {
      if (pixelRef.current) {
        pixelRef.current = null;
        reportStatus();
      }
      return;
    }
    const offset = (py * data.width + px) * 4;
    const r = data.data[offset];
    const g = data.data[offset + 1];
    const b = data.data[offset + 2];
    pixelRef.current = { x: px, y: py, r, g, b, gray: Math.round(0.2126 * r + 0.7152 * g + 0.0722 * b) };
    reportStatus();
  }

  function onPointerUp(event: React.PointerEvent<HTMLCanvasElement>) {
    dragRef.current = null;
    (event.target as Element).releasePointerCapture?.(event.pointerId);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const step = event.shiftKey ? 120 : 32;
    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      zoomBy(1.25);
    } else if (event.key === "-" || event.key === "_") {
      event.preventDefault();
      zoomBy(1 / 1.25);
    } else if (event.key.toLowerCase() === "f" || event.key === "Home") {
      event.preventDefault();
      fit();
    } else if (event.key === "1") {
      event.preventDefault();
      actualSize();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      viewRef.current.x -= step;
      scheduleDraw();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      viewRef.current.x += step;
      scheduleDraw();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      viewRef.current.y -= step;
      scheduleDraw();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      viewRef.current.y += step;
      scheduleDraw();
    }
  }

  return (
    <div
      ref={wrapRef}
      role="application"
      tabIndex={0}
      aria-label={labels.stage}
      aria-describedby="canvas-hint"
      onKeyDown={onKeyDown}
      className="relative h-full w-full overflow-hidden bg-stage outline-none focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-paper"
    >
      <span id="canvas-hint" className="sr-only">
        {labels.hint}
      </span>
      <canvas
        ref={canvasRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        onDoubleClick={fit}
        className={`h-full w-full touch-none ${compare ? "cursor-ew-resize" : "cursor-grab active:cursor-grabbing"}`}
      />
      {!ready && !failed && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="num text-12 tracking-wide text-stage-ink-soft">{labels.loading}</span>
        </div>
      )}
      {failed && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-stage">
          <span className="num text-12 tracking-wide text-stage-ink-soft">{labels.failed}</span>
        </div>
      )}
      {compare && (
        <span
          className="sr-only"
          aria-live="polite"
        >{`${Math.round(split * 100)} ${labels.percent}`}</span>
      )}
    </div>
  );
});

// Copy a mask into a solid-colour canvas, alpha preserved.
function tintCanvas(source: HTMLImageElement | HTMLCanvasElement, color: string): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = source instanceof HTMLImageElement ? source.naturalWidth : source.width;
  canvas.height = source instanceof HTMLImageElement ? source.naturalHeight : source.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  ctx.drawImage(source, 0, 0);
  ctx.globalCompositeOperation = "source-in";
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  return canvas;
}

// Masks arrive as grayscale PNG (opaque everywhere) or RGBA with alpha.
// Normalize to white pixels with a real alpha channel before tinting.
function normalizeMask(image: HTMLImageElement): HTMLCanvasElement {
  const width = image.naturalWidth;
  const height = image.naturalHeight;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return canvas;
  ctx.drawImage(image, 0, 0);
  try {
    const data = ctx.getImageData(0, 0, width, height);
    const px = data.data;
    for (let index = 0; index < px.length; index += 4) {
      const luma = 0.2126 * px[index] + 0.7152 * px[index + 1] + 0.0722 * px[index + 2];
      const on = px[index + 3] > 127 && luma > 96 ? 255 : 0;
      px[index] = 255;
      px[index + 1] = 255;
      px[index + 2] = 255;
      px[index + 3] = on;
    }
    ctx.putImageData(data, 0, 0);
  } catch {
    // Unreadable mask: leave it empty rather than tinting the whole frame.
  }
  return canvas;
}

// Extract a one-pixel outline from the mask alpha channel.
function buildContour(mask: HTMLCanvasElement): HTMLCanvasElement {
  const width = mask.width;
  const height = mask.height;
  const source = document.createElement("canvas");
  source.width = width;
  source.height = height;
  const sourceCtx = source.getContext("2d", { willReadFrequently: true });
  const out = document.createElement("canvas");
  out.width = width;
  out.height = height;
  const outCtx = out.getContext("2d");
  if (!sourceCtx || !outCtx) return out;

  sourceCtx.drawImage(mask, 0, 0);
  let data: Uint8ClampedArray;
  try {
    data = sourceCtx.getImageData(0, 0, width, height).data;
  } catch {
    return out;
  }
  const filled = new Uint8Array(width * height);
  for (let index = 0; index < filled.length; index += 1) {
    filled[index] = data[index * 4 + 3] > 127 ? 1 : 0;
  }

  const outline = outCtx.createImageData(width, height);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = y * width + x;
      if (!filled[index]) continue;
      const edge =
        x === 0 ||
        y === 0 ||
        x === width - 1 ||
        y === height - 1 ||
        !filled[index - 1] ||
        !filled[index + 1] ||
        !filled[index - width] ||
        !filled[index + width];
      if (!edge) continue;
      const offset = index * 4;
      outline.data[offset] = 255;
      outline.data[offset + 1] = 255;
      outline.data[offset + 2] = 255;
      outline.data[offset + 3] = 255;
    }
  }
  outCtx.putImageData(outline, 0, 0);
  return out;
}
