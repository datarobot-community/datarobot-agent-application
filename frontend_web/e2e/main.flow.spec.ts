import type { BrowserContext, Page } from 'playwright-core';
import { test, expect } from '@playwright/test';
import { baseURL } from '../playwright.config';
const TIMEOUT = 5 * 60 * 1000;

/** Types like a user so React controlled state stays in sync (fill alone can flake on deployed builds). */
async function typeComposerMessage(page: Page, text: string) {
  const input = page.getByTestId('chat-message-input');
  await input.click();
  await input.fill('');
  await input.pressSequentially(text, { delay: 15 });
  await expect(input).toHaveValue(text, { timeout: 60_000 });
}

test.describe('Main flow test', () => {
  let context: BrowserContext;
  let page: Page;

  const storageStatePath = './e2e/storageState.json';

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      serviceWorkers: 'block',
      storageState: storageStatePath,
    });
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
    await typeComposerMessage(page, 'tell me small story');
    await expect(page.getByTestId('send-message-btn')).toBeEnabled();
    await page.getByTestId('send-message-btn').click();
    const spinner = await page.getByTestId('thinking-loading');
    await expect(spinner).toBeVisible();
    await expect(page.getByTestId('send-message-disabled-btn')).toBeDisabled();

    // wait until message will be received
    await page.getByTestId('send-message-btn').waitFor({ state: 'visible', timeout: TIMEOUT });
  });

  test('new thread is active when user switches chats', async () => {
    test.setTimeout(TIMEOUT); // to wait for chat to be deleted
    let contentCount = 0;
    await page.getByTestId('start-new-chat-btn').click();
    await expect(page.locator('[data-testid^="initial-assistant-message-"]')).toBeVisible();
    await typeComposerMessage(page, 'tell some fun fact');
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
  });

  test('remove chat', async () => {
    test.setTimeout(TIMEOUT); // to wait for chat to be deleted
    await page.locator('#sidebar-chats').locator('[data-testid^="chat-"]')?.last().click();
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
});
