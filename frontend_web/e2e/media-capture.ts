import type { Page, TestInfo } from '@playwright/test';

const mode = (process.env.TEST_MEDIA_UPLOAD_MODE || 'never').toLowerCase();
// Shared across auth.spec.ts/main.flow.spec.ts (context-creation option) and below.
export const shouldCaptureVideo = mode !== 'never';

/**
 * Media for the manually-created context is NOT auto-attached by Playwright,
 * so we attach both explicitly (one screenshot + one video per test):
 * - Screenshot must be captured while the page is still open (before we close it).
 * - Video path is only available AFTER the page/context closes, so we grab the
 *   Video reference first, then attach once the page has been closed.
 */
export async function attachTestMedia(page: Page | undefined, testInfo: TestInfo): Promise<void> {
  const failed = testInfo.status !== testInfo.expectedStatus;
  // Recording itself can't be conditionally skipped (Playwright's recordVideo
  // context option is fixed at context-creation time, before pass/fail is known),
  // but whether we persist/attach/upload it follows the same on_failures gate as
  // screenshots -- otherwise every passing test's video gets saved and uploaded
  // regardless of TEST_MEDIA_UPLOAD_MODE, wasting time/space in the common case.
  const wantMedia = mode === 'always' || (mode !== 'never' && failed);
  const video = shouldCaptureVideo && wantMedia && page && !page.isClosed() ? page.video() : null;
  try {
    if (wantMedia && page && !page.isClosed()) {
      const screenshot = await page.screenshot();
      await testInfo.attach('screenshot', { body: screenshot, contentType: 'image/png' });
    }
  } catch (err) {
    console.error('Failed to capture screenshot:', err);
  } finally {
    if (page && !page.isClosed()) {
      await page.close();
    }
  }
  if (video) {
    try {
      // Persist with saveAs() instead of attaching video.path() directly:
      // saveAs() waits until the page is closed and the recording is fully
      // flushed to disk. Attaching the raw path can copy a still-open
      // (empty/corrupt) file for this shared context-level recording, which
      // then fails to convert/render downstream, showing a blank video in
      // the report UI.
      const savedPath = testInfo.outputPath('video.webm');
      await video.saveAs(savedPath);
      await testInfo.attach('video', { path: savedPath, contentType: 'video/webm' });
    } catch (err) {
      console.error('Failed to attach video:', err);
    }
  }
}
