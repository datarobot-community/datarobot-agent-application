import type { BrowserContext, Page } from 'playwright-core';
import { test } from '@playwright/test';
import { baseURL } from '../playwright.config';

const USER_EMAIL = process.env.DATAROBOT_USER || 'buzok-ci-agents@datarobot.com';
const USER_PASSWORD = process.env.DATAROBOT_PASSWORD!;
const TIMEOUT = 5 * 60 * 1000;

test.describe('auth flow', () => {
  test.use({ testIdAttribute: 'test-id' });

  let context: BrowserContext;
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      serviceWorkers: 'block',
    });
    page = await context.newPage();
  });

  test('login if env is not localhost', async () => {
    const origin = new URL(baseURL).origin;
    if (origin.includes('localhost')) {
      test.skip();
    }
    test.setTimeout(TIMEOUT);

    await page.goto(origin, { waitUntil: 'networkidle' });

    // SaaS login (login.datarobot.com/login) and on-prem login (<origin>/sign-in)
    // use different test ids for the same fields.
    const emailField = page
      .getByTestId('email-field')
      .or(page.getByTestId('sign-in-input-username'));
    const passwordField = page
      .getByTestId('password-field')
      .or(page.getByTestId('sign-in-input-password'));
    const signInButton = page.getByTestId('sign-in-button').or(page.getByTestId('login-button'));

    await emailField.waitFor();
    await emailField.type(USER_EMAIL);
    await passwordField.type(USER_PASSWORD);
    await signInButton.click();

    // Wait until login is done: back on the app origin (SaaS leaves login.datarobot.com)
    // and no longer on the on-prem /sign-in page (which lives on the app origin).
    await page.waitForURL(url => url.origin === origin && url.pathname !== '/sign-in');
    await page.goto(baseURL, { waitUntil: 'networkidle' });
    await page.context().storageState({
      path: './e2e/storageState.json',
    });
  });
});
