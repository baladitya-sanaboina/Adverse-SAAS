"use client";

/*
 * Crop a profile photo before it is uploaded (owner request 2026-11-28: photos showed stretched;
 * people now choose the square part to keep). Drag to move, zoom with the slider, the wheel or the
 * buttons. The result is a 512 × 512 JPEG, so every avatar in the app gets the same shape.
 * Used by every Profile page and the onboarding photo step.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from "react";
import { Check, Minus, Plus, X } from "lucide-react";

const BOX = 280;
const OUTPUT = 512;
const MAX_ZOOM = 4;

type Loaded = { url: string; width: number; height: number };
type Point = { x: number; y: number };

export function PhotoCropper({
  file,
  onCancel,
  onDone,
  title = "Crop your photo",
}: {
  file: File;
  onCancel: () => void;
  onDone: (cropped: File) => void;
  title?: string;
}) {
  const [size, setSize] = useState<Loaded | null>(null);
  const [failed, setFailed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 });
  const [busy, setBusy] = useState(false);
  const drag = useRef<{ start: Point; from: Point } | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    const image = new window.Image();
    image.onload = () => setSize({ url, width: image.naturalWidth, height: image.naturalHeight });
    image.onerror = () => setFailed(true);
    image.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  // The photo always covers the square: its short side fills it at zoom 1.
  const shown = useMemo(() => {
    if (!size) return null;
    const scale = (BOX / Math.min(size.width, size.height)) * zoom;
    return { width: size.width * scale, height: size.height * scale };
  }, [size, zoom]);

  const clamp = useCallback(
    (point: Point, at = shown): Point => {
      if (!at) return point;
      const maxX = (at.width - BOX) / 2;
      const maxY = (at.height - BOX) / 2;
      return { x: Math.max(-maxX, Math.min(maxX, point.x)), y: Math.max(-maxY, Math.min(maxY, point.y)) };
    },
    [shown],
  );

  const changeZoom = (next: number) => {
    const value = Math.max(1, Math.min(MAX_ZOOM, next));
    setZoom(value);
    if (size) {
      const scale = (BOX / Math.min(size.width, size.height)) * value;
      setOffset((current) => clamp(current, { width: size.width * scale, height: size.height * scale }));
    }
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { start: { x: event.clientX, y: event.clientY }, from: offset };
  };
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    const { start, from } = drag.current;
    setOffset(clamp({ x: from.x + event.clientX - start.x, y: from.y + event.clientY - start.y }));
  };
  const onPointerUp = () => {
    drag.current = null;
  };
  const onWheel = (event: WheelEvent<HTMLDivElement>) => {
    changeZoom(zoom - event.deltaY * 0.0015);
  };

  const save = () => {
    if (!shown || !size) return;
    setBusy(true);
    const image = new window.Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = OUTPUT;
      canvas.height = OUTPUT;
      const context = canvas.getContext("2d");
      if (!context) {
        setBusy(false);
        return;
      }
      const factor = OUTPUT / BOX;
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, OUTPUT, OUTPUT);
      context.imageSmoothingQuality = "high";
      context.drawImage(
        image,
        (BOX / 2 + offset.x - shown.width / 2) * factor,
        (BOX / 2 + offset.y - shown.height / 2) * factor,
        shown.width * factor,
        shown.height * factor,
      );
      canvas.toBlob(
        (blob) => {
          setBusy(false);
          if (!blob) return;
          const name = `${file.name.replace(/\.[^.]+$/, "") || "photo"}.jpg`;
          onDone(new File([blob], name, { type: "image/jpeg" }));
        },
        "image/jpeg",
        0.9,
      );
    };
    image.onerror = () => setBusy(false);
    image.src = size.url;
  };

  return (
    <div
      className="photo-crop-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onCancel()}
    >
      <div className="photo-crop-card" role="dialog" aria-modal="true" aria-labelledby="photo-crop-title">
        <header>
          <h2 id="photo-crop-title">{title}</h2>
          <button type="button" className="photo-crop-close" aria-label="Cancel" onClick={onCancel}>
            <X aria-hidden="true" />
          </button>
        </header>
        <p>Drag the photo to place your face in the circle, then zoom to fit.</p>
        {failed ? (
          <p className="photo-crop-error" role="alert">
            This image could not be opened. Try a JPG or PNG photo.
          </p>
        ) : (
          <div
            className="photo-crop-stage"
            style={{ width: BOX, height: BOX }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            onWheel={onWheel}
            aria-label="Photo crop area. Drag to move."
          >
            {shown && (
              <div
                className="photo-crop-image"
                style={{
                  backgroundImage: `url(${size?.url})`,
                  backgroundSize: `${shown.width}px ${shown.height}px`,
                  backgroundPosition: `${BOX / 2 + offset.x - shown.width / 2}px ${BOX / 2 + offset.y - shown.height / 2}px`,
                }}
              />
            )}
            <span className="photo-crop-ring" aria-hidden="true" />
          </div>
        )}
        <div className="photo-crop-zoom">
          <button type="button" aria-label="Zoom out" onClick={() => changeZoom(zoom - 0.2)} disabled={zoom <= 1}>
            <Minus aria-hidden="true" />
          </button>
          <input
            type="range"
            min={1}
            max={MAX_ZOOM}
            step={0.01}
            value={zoom}
            aria-label="Zoom"
            onChange={(event) => changeZoom(Number(event.target.value))}
          />
          <button type="button" aria-label="Zoom in" onClick={() => changeZoom(zoom + 0.2)} disabled={zoom >= MAX_ZOOM}>
            <Plus aria-hidden="true" />
          </button>
        </div>
        <footer>
          <button type="button" className="photo-crop-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="photo-crop-primary" onClick={save} disabled={!shown || busy || failed}>
            <Check aria-hidden="true" />
            {busy ? "Saving…" : "Use photo"}
          </button>
        </footer>
      </div>
      <style>{`
        .photo-crop-backdrop {
          position: fixed;
          inset: 0;
          z-index: 1000;
          display: grid;
          place-items: center;
          padding: 16px;
          background: rgba(15, 23, 42, 0.55);
        }
        .photo-crop-card {
          width: min(100%, 360px);
          display: grid;
          gap: 14px;
          padding: 20px;
          border: 1px solid var(--border, #e2e8f0);
          border-radius: 18px;
          color: var(--foreground, #0f172a);
          background: var(--surface, #ffffff);
          box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28);
          font-family: var(--font-poppins), "Poppins", Arial, sans-serif;
        }
        .photo-crop-card header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .photo-crop-card h2 {
          margin: 0;
          font-size: 1rem;
          font-weight: 700;
        }
        .photo-crop-card p {
          margin: 0;
          color: var(--muted, #64748b);
          font-size: 0.78rem;
        }
        .photo-crop-card .photo-crop-error {
          color: #b74858;
        }
        .photo-crop-close {
          width: 32px;
          height: 32px;
          display: grid;
          place-items: center;
          border: 1px solid var(--border, #e2e8f0);
          border-radius: 10px;
          color: inherit;
          background: transparent;
          cursor: pointer;
        }
        .photo-crop-close svg {
          width: 16px;
          height: 16px;
        }
        .photo-crop-stage {
          position: relative;
          justify-self: center;
          max-width: 100%;
          overflow: hidden;
          border-radius: 14px;
          background: #0f172a;
          cursor: grab;
          touch-action: none;
          user-select: none;
        }
        .photo-crop-stage:active {
          cursor: grabbing;
        }
        .photo-crop-image {
          position: absolute;
          inset: 0;
          background-repeat: no-repeat;
        }
        .photo-crop-ring {
          position: absolute;
          inset: 0;
          border-radius: 50%;
          box-shadow: 0 0 0 999px rgba(15, 23, 42, 0.5);
          outline: 2px solid rgba(255, 255, 255, 0.9);
          outline-offset: -2px;
          pointer-events: none;
        }
        .photo-crop-zoom {
          display: grid;
          grid-template-columns: 32px minmax(0, 1fr) 32px;
          align-items: center;
          gap: 10px;
        }
        .photo-crop-zoom button {
          width: 32px;
          height: 32px;
          display: grid;
          place-items: center;
          border: 1px solid var(--border, #e2e8f0);
          border-radius: 10px;
          color: #0876ed;
          background: transparent;
          cursor: pointer;
        }
        .photo-crop-zoom button:disabled {
          opacity: 0.45;
          cursor: not-allowed;
        }
        .photo-crop-zoom svg {
          width: 15px;
          height: 15px;
        }
        .photo-crop-zoom input {
          width: 100%;
          accent-color: #0876ed;
        }
        .photo-crop-card footer {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
        }
        .photo-crop-card footer button {
          min-height: 40px;
          display: inline-flex;
          align-items: center;
          gap: 7px;
          padding: 0 16px;
          border-radius: 10px;
          font: 600 0.8rem/1 var(--font-poppins), "Poppins", Arial, sans-serif;
          cursor: pointer;
        }
        .photo-crop-card footer svg {
          width: 16px;
          height: 16px;
        }
        .photo-crop-secondary {
          border: 1px solid var(--border, #e2e8f0);
          color: inherit;
          background: transparent;
        }
        .photo-crop-primary {
          border: 1px solid #0876ed;
          color: #ffffff;
          background: #0876ed;
        }
        .photo-crop-primary:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}
