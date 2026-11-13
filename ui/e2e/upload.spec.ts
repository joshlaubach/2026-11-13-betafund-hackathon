// Pure-logic checks for the upload experience: file validation and analysis step states.
// These run without a browser page; the components are not on the page yet.
import { expect, test } from "@playwright/test";
import { ACCEPTED_IMAGE_TYPES, MAX_UPLOAD_BYTES, formatFileSize, stepStates, validateUpload } from "../lib/upload";

const MEGABYTE = 1024 * 1024;

test.describe("validateUpload", () => {
  for (const type of ACCEPTED_IMAGE_TYPES) {
    test(`accepts a ${type} photo`, () => {
      expect(validateUpload({ name: "worksheet.img", type, size: 2 * MEGABYTE })).toEqual({ ok: true });
    });
  }

  test("rejects a non-image type and names the file and the accepted types", () => {
    const check = validateUpload({ name: "notes.pdf", type: "application/pdf", size: 1000 });
    expect(check.ok).toBe(false);
    if (check.ok) return;
    expect(check.message).toContain('"notes.pdf"');
    expect(check.message).toContain("PNG, JPEG, WebP or GIF");
  });

  test("rejects a file with no type at all", () => {
    const check = validateUpload({ name: "photo", type: "", size: 1000 });
    expect(check.ok).toBe(false);
    if (check.ok) return;
    expect(check.message).toContain("unknown type");
  });

  test("accepts a file exactly at the 10 MB limit", () => {
    expect(validateUpload({ name: "big.png", type: "image/png", size: MAX_UPLOAD_BYTES })).toEqual({ ok: true });
  });

  test("rejects a file one byte over 10 MB with the limit in the message", () => {
    const check = validateUpload({ name: "big.png", type: "image/png", size: MAX_UPLOAD_BYTES + 1 });
    expect(check.ok).toBe(false);
    if (check.ok) return;
    expect(check.message).toContain('"big.png"');
    expect(check.message).toContain("10 MB limit");
    expect(check.message).toContain("10.0 MB");
  });

  test("rejects an empty file", () => {
    const check = validateUpload({ name: "empty.gif", type: "image/gif", size: 0 });
    expect(check.ok).toBe(false);
    if (check.ok) return;
    expect(check.message).toContain("is empty");
  });

  test("reports the type problem first when both type and size are wrong", () => {
    const check = validateUpload({ name: "huge.bmp", type: "image/bmp", size: MAX_UPLOAD_BYTES * 2 });
    expect(check.ok).toBe(false);
    if (check.ok) return;
    expect(check.message).toContain("not a photo Echo can read");
  });
});

test.describe("formatFileSize", () => {
  test("uses bytes, KB and MB by size", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(2048)).toBe("2 KB");
    expect(formatFileSize(1.5 * MEGABYTE)).toBe("1.5 MB");
  });
});

test.describe("stepStates", () => {
  test("reading: step 1 is active and nothing is done yet", () => {
    expect(stepStates("reading")).toEqual(["active", "waiting"]);
  });

  test("grading: step 1 is done only once grading has started, step 2 is active", () => {
    expect(stepStates("grading")).toEqual(["done", "active"]);
  });

  test("done: both steps are done", () => {
    expect(stepStates("done")).toEqual(["done", "done"]);
  });

  test("no step is marked done while the backend is still reading", () => {
    const [readingStep] = stepStates("reading");
    expect(readingStep).not.toBe("done");
  });
});
