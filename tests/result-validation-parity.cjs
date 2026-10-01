/* Shared synthetic fixture runner, also used by the Python parity gate. */
'use strict';
const fs = require('node:fs'), path = require('node:path');
global.window = globalThis;
require(path.join(__dirname, '..', 'src', 'agent-contract.js'));
const C = global.VASAgentContract, input = JSON.parse(fs.readFileSync(0, 'utf8'));
async function run() {
  if (input.operation === 'repair') return input.documents.map(raw => C.repairLegacyNumbers(raw));
  if (input.operation === 'handoff') return Promise.all(input.documents.map(async raw => {
    try { await C.normalizeHandoff(raw); return { ok: true, errorCodes: [] }; }
    catch (error) { return { ok: false, errorCodes: [error.message] }; }
  }));
  return input.documents.map(raw => {
    const value = C.validateResult(raw, 'existing');
    return { ok: value.ok, errorCodes: value.errorCodes, result: value.result };
  });
}
run().then(value => process.stdout.write(JSON.stringify(value))).catch(error => { process.stderr.write(error.stack); process.exit(1); });
