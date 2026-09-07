// Browser evidence for the controlled live-agent fixture; this does not spawn agents.
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('@playwright/test');

async function main() {
  const [fixture, output] = process.argv.slice(2).map(value => path.resolve(value));
  if (!fixture || !output) throw new Error('Usage: node tests/agent-live-check.cjs FIXTURE OUTPUT');
  const brief = JSON.parse(fs.readFileSync(path.join(fixture, 'requirements.json'), 'utf8'));
  fs.mkdirSync(output, { recursive: true });
  const chrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  const browser = await chromium.launch(fs.existsSync(chrome) ? { executablePath: chrome } : {});
  const checks = [];
  const check = (name, actual, expected) => checks.push({ name, actual, expected, passed: actual === expected });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(fixture, 'index.html')).href);
    const initial = Number(await page.locator('#quantity').textContent());
    check('initial quantity', initial, brief.behavior.initialQuantity);
    await page.locator('#increment').click();
    check('first increment', Number(await page.locator('#quantity').textContent()), initial + 1);
    await page.locator('#increment').click();
    check('second increment', Number(await page.locator('#quantity').textContent()), initial + 2);
    await page.keyboard.press('Space');
    check('keyboard Space', Number(await page.locator('#quantity').textContent()), initial + 3);
    await page.keyboard.press('Enter');
    check('keyboard Enter', Number(await page.locator('#quantity').textContent()), initial + 4);
    const style = await page.locator('#increment').evaluate(element => {
      const value = getComputedStyle(element);
      return { color: value.backgroundColor, radius: value.borderRadius, outline: value.outlineWidth };
    });
    const rgb = brief.tokens.primary.match(/[a-f0-9]{2}/gi).map(hex => parseInt(hex, 16));
    check('primary token', style.color, `rgb(${rgb.join(', ')})`);
    check('radius token', style.radius, brief.tokens.radius + 'px');
    check('keyboard focus ring', style.outline, '3px');
    check('padding token', await page.locator('article').evaluate(element => getComputedStyle(element).padding), brief.tokens.padding + 'px');
    check('live announcement', await page.locator('#quantity').getAttribute('aria-live'), 'polite');
    const columns = () => page.locator('.grid').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length);
    check('desktop columns', await columns(), brief.responsive.desktopColumns);
    await page.screenshot({ path: path.join(output, 'desktop.png') });
    await page.setViewportSize({ width: brief.responsive.mobileWidth, height: 844 });
    check('mobile columns', await columns(), brief.responsive.mobileColumns);
    check('mobile overflow', await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false);
    check('browser errors', errors.length, 0);
    await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
  } finally {
    await browser.close();
  }
  const report = { scope: 'browser fixture only; agent execution requires separate host evidence', checks, passed: checks.every(item => item.passed) };
  fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
  process.exitCode = report.passed ? 0 : 1;
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
