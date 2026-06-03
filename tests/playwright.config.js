const { defineConfig } = require('@playwright/test');
const fs = require('fs');

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

module.exports = defineConfig({
  testDir: __dirname,
  use: fs.existsSync(chromePath)
    ? { launchOptions: { executablePath: chromePath } }
    : {},
});
