const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

const appUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'client-application.html')).href;

async function waitStep(page, step) {
  await page.locator(`.step[data-step="${step}"].active`).waitFor();
  await page.waitForTimeout(450);
}

test('client application core flow works in a browser', async ({ page }) => {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });

  await expect(page.locator('#progressText')).toContainText('01');

  await expect(page.locator('#nextBtn')).toContainText('다음');

  await page.locator('input[name="client_name"]').fill('Acme');
  await page.locator('input[name="contact"]').fill('hello@example.com');
  await page.locator('#nextBtn').click();
  await expect(page.locator('#progressText')).toContainText('02');

  await page.locator('input[name="project_name"]').fill('Safe Flow');
  await page.locator('textarea[name="problem_desc"]').fill('Need a safe workflow.');
  await page.locator('#fileInput').setInputFiles({
    name: '<script>alert(1)</script>.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('reference')
  });
  await expect(page.locator('#fileChips')).toContainText('<script>alert(1)</script>.txt');
  await expect(page.locator('#fileChips script')).toHaveCount(0);
});

test('client application reaches JSON save step after required selections', async ({ page }) => {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });
  await waitStep(page, 1);

  await page.locator('input[name="client_name"]').fill('Acme');
  await page.locator('input[name="contact"]').fill('hello@example.com');
  await page.locator('#nextBtn').click();
  await waitStep(page, 2);

  await page.locator('input[name="project_name"]').fill('Safe Flow');
  await page.locator('textarea[name="problem_desc"]').fill('Need a safe workflow.');
  await page.locator('#nextBtn').click();
  await waitStep(page, 3);

  await page.locator('.step.active label.v-block').nth(1).click();
  await page.locator('#nextBtn').click();
  await waitStep(page, 4);

  await page.locator('.step.active label.block').first().click();
  await page.locator('#nextBtn').click();
  await waitStep(page, 5);

  await page.locator('.step.active label.v-block').last().click();
  await expect(page.locator('#nextBtn')).toContainText('내용 확인');
  await page.locator('#nextBtn').click();

  await expect(page.locator('#doneScreen')).toHaveClass(/active/);
  await expect(page.locator('[data-i18n="btnJson"]')).toBeVisible();
  await expect(page.locator('#createProjectButton')).toBeHidden();
  await expect(page.locator('#createdProjectNext')).toBeHidden();
});

test('client application shows visible required selection feedback', async ({ page }) => {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });
  await waitStep(page, 1);

  await page.locator('input[name="client_name"]').fill('Acme');
  await page.locator('input[name="contact"]').fill('hello@example.com');
  await page.locator('#nextBtn').click();
  await waitStep(page, 2);

  await page.locator('input[name="project_name"]').fill('Safe Flow');
  await page.locator('textarea[name="problem_desc"]').fill('Need a safe workflow.');
  await page.locator('#nextBtn').click();
  await waitStep(page, 3);

  await page.locator('.step.active label.v-block').nth(1).click();
  await page.locator('#nextBtn').click();
  await waitStep(page, 4);

  await page.locator('.step.active label.block').first().click();
  await page.locator('#nextBtn').click();
  await waitStep(page, 5);

  await page.locator('#nextBtn').click();
  await expect(page.locator('[data-validation-message]')).toContainText('필수 항목');
  await expect(page.locator('#doneScreen')).not.toHaveClass(/active/);
});
