const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { pathToFileURL } = require('url');
const cases = require('./fixtures/secret-redaction-cases.json');
const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;
function stable(value) {
  if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + stable(value[key])).join(',') + '}';
  return JSON.stringify(value);
}
function verifyHash(document) {
  const payload = JSON.parse(JSON.stringify(document));
  delete payload.integrity;
  payload.assistantGuide.pasteText = '';
  expect(crypto.createHash('sha256').update(stable(payload)).digest('hex')).toBe(document.integrity.payloadSha256);
}
test('existing UI downloads redact the entire payload after edits and provider changes', async ({ page }) => {
  await page.goto(source('project-import.html'));
  await page.locator('#folderPath').fill('Z:\\work\\real-project');
  await page.locator('#projectName').fill('Design sample');
  const request = 'Keep React. password=VasCanarySensitive987 canary@example.invalid C:\\canary-private\\file';
  await page.locator('#taskRequest').fill(request);
  await page.locator('#continueSettings').click();
  await page.locator('#provider').selectOption('codex');
  await expect(page.locator('#previewContent')).toContainText('Z:\\work\\real-project');
  for (const iteration of [1, 2]) {
    if (iteration === 2) {
      await page.locator('#editWork').click();
      await page.locator('#taskRequest').fill(request + ' Preserve keyboard behavior.');
      await page.locator('#continueSettings').click();
      await page.locator('#provider').selectOption('claude');
    }
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#downloadJson').click();
    const download = await downloadPromise;
    const raw = fs.readFileSync(await download.path(), 'utf8');
    for (const forbidden of ['VasCanarySensitive987', 'canary@example.invalid', 'canary-private', 'real-project']) expect(raw).not.toContain(forbidden);
    const document = JSON.parse(raw);
    expect(document.task.request).toContain('Keep React.');
    expect(document.context.requirements.value.request).toBe(document.task.request);
    expect(document.assistantGuide.target).toBe(iteration === 1 ? 'codex' : 'claude');
    verifyHash(document);
  }
});
test('browser cleaners cover shared JSON encodings and preserve public design data', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const result = await page.evaluate(async input => {
    const cases = [];
    for (const item of input) {
      const built = await VASAgentHandoffWeb.buildNew({project_name:'Demo',problem_desc:item.input}, {included:false});
      const clean = VASAgentContract.clean(item.input);
      cases.push({clean, twice:VASAgentContract.clean(clean), prompt:built.pasteText, json:JSON.stringify(built.document)});
    }
    const document = (await VASAgentHandoffWeb.buildExisting('Demo','Preserve React',{
      design:{included:true,tokens:{colors:{primary:'#123abc'},password:'NestedCanarySecret'},direction:'Layout rule\n'.repeat(700)},
      requirements:{included:true,value:{reference:'https://example.com/home/design',nested:{apiKey:'NestedCanarySecret'}}}
    })).document;
    document.task.request += ' password=LateMutationCanary';
    document.context.requirements.value.credentials = {secret:'NestedCanarySecret'};
    const serialized = [];
    const oldCreate = URL.createObjectURL;
    const oldClick = HTMLAnchorElement.prototype.click;
    URL.createObjectURL = blob => { serialized.push(blob.text()); return 'blob:fixture'; };
    HTMLAnchorElement.prototype.click = function () {};
    try { await VASAgentHandoffWeb.save(document); } finally { URL.createObjectURL=oldCreate; HTMLAnchorElement.prototype.click=oldClick; }
    return {cases,saved:await serialized[0]};
  }, cases);
  result.cases.forEach((item,index) => {
    for (const value of [item.clean,item.prompt,item.json]) expect(value,cases[index].name).not.toContain(cases[index].marker);
    expect(item.twice,cases[index].name+' idempotence').toBe(item.clean);
  });
  expect(result.saved).not.toContain('NestedCanarySecret');
  expect(result.saved).not.toContain('LateMutationCanary');
  const document=JSON.parse(result.saved);
  expect(document.context.design.tokens.colors.primary).toBe('#123abc');
  expect(document.context.design.direction).toBe('Layout rule\n'.repeat(700).trim());
  expect(document.context.requirements.value.reference).toBe('https://example.com/home/design');
  verifyHash(document);
});
