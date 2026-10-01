const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

test('new project redacted design requires review before any download', async ({ page }) => {
  await page.goto(pathToFileURL(path.join(__dirname, '..', 'src', 'client-application.html')).href);
  const result = await page.evaluate(async () => {
    const built = await VASAgentHandoffWeb.buildNew({ project_name: 'synthetic', problem_desc: 'Header typography' },
      { included: true, direction: 'Typography contact@example.com', tokens: { fontFamily: 'contact@example.com' } });
    let blobs = 0;
    const original = URL.createObjectURL;
    URL.createObjectURL = function (value) { blobs += 1; return original.call(URL, value); };
    let message = '';
    try { await VASAgentHandoffWeb.save(built.document); } catch (error) { message = error.message; }
    finally { URL.createObjectURL = original; }
    return { document: built.document, blobs, message };
  });
  expect(JSON.stringify(result.document)).not.toContain('contact@example.com');
  expect(result.document.context.design.tokens.fontFamily).toBe('[redacted]');
  expect(result.document.inputReview).toMatchObject({ required: true, acknowledged: false });
  expect(result.document.inputReview.fields).toContain('디자인');
  expect(result.blobs).toBe(0);
  expect(result.message).toContain('최종 내용');
});
