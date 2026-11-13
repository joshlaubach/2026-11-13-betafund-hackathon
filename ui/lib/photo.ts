// Browser-side preparation of a photo before upload. A canvas re-encode drops all metadata
// and applies EXIF rotation, and it keeps phone photos well under the server's 5 MB cap.
export const MAX_SIDE_PX = 2000;
export const JPEG_QUALITY = 0.9;
export const KEEP_AS_IS_MAX_BYTES = 1.5 * 1024 * 1024;
export const UNDECODABLE_MAX_BYTES = 5 * 1024 * 1024;
export const UNPREPARED_MESSAGE =
  "This photo could not be prepared in your browser. Open it and export it as a JPEG, then try again.";
const FILL_COLOUR = "#ffffff"; // a transparent PNG would otherwise re-encode onto black
const JPEG_TYPE = "image/jpeg";
const JPEG_EXTENSION = ".jpg";

export interface PixelSize {
  width: number;
  height: number;
}

/** The size that fits the long side into maxSide. Never upscales. */
export function scaledSize(width: number, height: number, maxSide: number): PixelSize {
  const longSide = Math.max(width, height);
  if (longSide <= maxSide) return { width, height };
  const ratio = maxSide / longSide;
  return {
    width: Math.max(1, Math.round(width * ratio)),
    height: Math.max(1, Math.round(height * ratio)),
  };
}

function jpegName(name: string): string {
  const dot = name.lastIndexOf(".");
  const stem = dot > 0 ? name.slice(0, dot) : name;
  return `${stem}${JPEG_EXTENSION}`;
}

function encodeJpeg(bitmap: ImageBitmap, size: PixelSize): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = size.width;
  canvas.height = size.height;
  const context = canvas.getContext("2d");
  if (!context) return Promise.reject(new Error(UNPREPARED_MESSAGE));
  context.fillStyle = FILL_COLOUR;
  context.fillRect(0, 0, size.width, size.height);
  context.drawImage(bitmap, 0, 0, size.width, size.height);
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error(UNPREPARED_MESSAGE))),
      JPEG_TYPE,
      JPEG_QUALITY,
    );
  });
}

async function decode(file: File): Promise<ImageBitmap | null> {
  try {
    return await createImageBitmap(file);
  } catch {
    return null;
  }
}

function keepUndecodable(file: File): File {
  if (file.size <= UNDECODABLE_MAX_BYTES) return file;
  throw new Error(UNPREPARED_MESSAGE);
}

/**
 * Prepare a chosen photo for upload. Oversized or metadata-bearing images are re-encoded as
 * JPEG with the long side at most MAX_SIDE_PX. A small image that already fits is returned as is.
 * An image the browser cannot decode (for example HEIC) is returned unchanged when it is at most
 * UNDECODABLE_MAX_BYTES, and otherwise throws an Error with a user-facing message.
 */
export async function prepareUpload(file: File): Promise<File> {
  const bitmap = await decode(file);
  if (!bitmap) return keepUndecodable(file);
  try {
    const size = scaledSize(bitmap.width, bitmap.height, MAX_SIDE_PX);
    const unchanged = size.width === bitmap.width && size.height === bitmap.height;
    if (unchanged && file.size <= KEEP_AS_IS_MAX_BYTES) return file;
    const blob = await encodeJpeg(bitmap, size);
    return new File([blob], jpegName(file.name), { type: JPEG_TYPE });
  } finally {
    bitmap.close();
  }
}
