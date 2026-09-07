/* Regenerate selector thumbnails from the actual local sample sites. */
const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
(async () => {
  const root = path.resolve(__dirname, '..');
  const destination = path.join(root, 'src/assets/designs/samples');
  fs.mkdirSync(destination, { recursive: true });
  const chrome = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await chromium.launch(fs.existsSync(chrome) ? { executablePath: chrome } : {});
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1200 }, deviceScaleFactor: 1 });
    for (const key of ['awwwards', 'linear', 'stripe', 'notion']) {
      await page.goto(pathToFileURL(path.join(root, 'src/design-sample.html')).href + '?preset=' + key);
      await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(Array.from(document.images, image => image.decode()));
      });
      const bounds = await page.locator('#advPreview').boundingBox();
      await page.screenshot({ path: path.join(destination, key + '.png'),
        clip: { x: bounds.x, y: bounds.y, width: bounds.width, height: Math.min(bounds.height, 960) } });
      console.log('Captured ' + key);
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
