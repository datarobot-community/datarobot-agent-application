import type { BrowserContext, ConsoleMessage, Page } from 'playwright-core';
import { test, expect } from '@playwright/test';
import { baseURL } from '../playwright.config';
import { shouldCaptureVideo, attachTestMedia } from './media-capture';
const TIMEOUT = 5 * 60 * 1000;

/** Types like a user so React controlled state stays in sync (fill alone can flake on deployed builds). */
async function typeComposerMessage(page: Page, text: string) {
  const input = page.getByTestId('chat-message-input');
  await input.click();
  await input.fill('');
  await input.pressSequentially(text, { delay: 15 });
  await expect(input).toHaveValue(text, { timeout: 60_000 });
}

function trackConsoleErrors(page: Page) {
  const errors: string[] = [];
  const handler = (msg: ConsoleMessage) => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  };
  page.on('console', handler);
  return {
    errors,
    dispose: () => page.off('console', handler),
  };
}

test.describe('Main flow test', () => {
  let context: BrowserContext;
  let page: Page;

  const storageStatePath = './e2e/storageState.json';

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      serviceWorkers: 'block',
      storageState: storageStatePath,
      ...(shouldCaptureVideo ? { recordVideo: { dir: 'test-results/videos' } } : {}),
    });
  });

  // These two tests must run in the same page/session: 'write a question...'
  // leaves a chat mid-stream on purpose, and 'new thread is active...'
  // switches away and back to confirm that stream is still active. Every
  // other test in this file still gets its own fresh page/session.
  const SHARED_SESSION_TESTS = [
    'write a question to agent and wait until response fully done',
    'new thread is active when user switches chats',
  ];

  // Playwright requires the fixtures param even when unused, to access
  // testInfo as the second argument.
  // eslint-disable-next-line no-empty-pattern
  test.beforeEach(async ({}, testInfo) => {
    // Reuse the page left open by SHARED_SESSION_TESTS[0] -- but only if it's
    // actually still open. If that test failed, afterEach already closed it
    // (to attach failure evidence), so fall back to a fresh page here.
    if (testInfo.title === SHARED_SESSION_TESTS[1] && page && !page.isClosed()) {
      return;
    }
    page = await context.newPage();
    await page.goto(baseURL, { waitUntil: 'networkidle' });
  });

  test.afterAll(async () => {
    await context?.close();
  });

  test('start new chat', async () => {
    await page.getByTestId('start-new-chat-btn').click();
    await expect(page.locator('[data-testid^="initial-assistant-message-"]')).toBeVisible();
    await expect(page.getByText('assistant')).toBeVisible();
  });

  test('write a question to agent and wait until response fully done', async () => {
    test.setTimeout(TIMEOUT); // to wait long response from agent
    await page.getByTestId('start-new-chat-btn').click();
    await expect(page.locator('[data-testid^="initial-assistant-message-"]')).toBeVisible();

    const { errors, dispose } = trackConsoleErrors(page);

    try {
      await typeComposerMessage(page, 'tell 2 facts about Kiyv in 1 sentence');
      await expect(page.getByTestId('send-message-btn')).toBeEnabled();
      await page.getByTestId('send-message-btn').click();
      const spinner = await page.getByTestId('thinking-loading');
      await expect(spinner).toBeVisible();
      await expect(page.getByTestId('send-message-disabled-btn')).toBeDisabled();

      // wait until message will be received
      await page.getByTestId('send-message-btn').waitFor({ state: 'visible', timeout: TIMEOUT });

      await expect(page.getByTestId('chat-error-message')).not.toBeVisible();
      expect(errors).toHaveLength(0);
    } finally {
      dispose();
    }
  });

  test('new thread is active when user switches chats', async () => {
    test.setTimeout(TIMEOUT); // to wait for chat to be deleted
    let contentCount = 0;
    const { errors, dispose } = trackConsoleErrors(page);

    try {
      await page.getByTestId('start-new-chat-btn').click();
      await expect(page.locator('[data-testid^="initial-assistant-message-"]')).toBeVisible();
      await typeComposerMessage(page, 'tell 2 facts about Lviv in 1 sentence');
      await expect(page.getByTestId('send-message-btn')).toBeEnabled();
      await page.getByTestId('send-message-btn').click();
      // Wait for the message to be sent and the chat to appear in the sidebar
      await page.getByTestId('thinking-loading').waitFor({ state: 'visible' });
      await page.locator('#sidebar-chats').locator('[data-testid^="chat-"]')?.last().click();
      await expect(page.getByTestId('send-message-btn')).toBeVisible();

      await page.locator('#sidebar-chats').locator('[data-testid^="chat-"]')?.first().click();

      await expect
        .poll(
          async () => {
            const content = await page
              .locator('[data-testid^="default-assistant-message-"]')
              ?.first();
            const text = await content.textContent();
            contentCount = text?.length ?? 0;
            return contentCount;
          },
          {
            timeout: TIMEOUT,
          }
        )
        .toBeGreaterThan(0);
      await expect(page.getByTestId('chat-error-message')).not.toBeVisible();
      expect(errors).toHaveLength(0);
    } finally {
      dispose();
    }
  });

  test('remove chat', async () => {
    test.setTimeout(TIMEOUT); // to wait for chat to be deleted
    // The fresh page from beforeEach reloads the sidebar from server state, so wait
    // for it to hydrate before clicking (a bare click can race an empty sidebar).
    const lastChat = page.locator('#sidebar-chats').locator('[data-testid^="chat-"]').last();
    await expect(lastChat).toBeVisible({ timeout: TIMEOUT });
    await lastChat.click();
    const oldUrl = page.url();
    await page.locator('[data-slot="dropdown-menu-trigger"]')?.last().click();
    await page.getByTestId('delete-chat-menu-item').click();
    await page.getByTestId('modal-confirm').click();
    await expect
      .poll(() => page.url(), {
        timeout: TIMEOUT,
      })
      .not.toBe(oldUrl); // check if user was redirected to the active chat
  });

  // Playwright requires the fixtures param even when unused, to access
  // testInfo as the second argument.
  // eslint-disable-next-line no-empty-pattern
  test.afterEach(async ({}, testInfo) => {
    // Keep the page open for SHARED_SESSION_TESTS[1] to reuse -- but only on
    // a pass. On failure, attach evidence for this test now (on_failures mode
    // exists precisely for this case); SHARED_SESSION_TESTS[1]'s beforeEach
    // falls back to a fresh page since this one will already be closed.
    if (testInfo.title === SHARED_SESSION_TESTS[0] && testInfo.status === testInfo.expectedStatus) {
      return;
    }
    await attachTestMedia(page, testInfo);
  });
});
