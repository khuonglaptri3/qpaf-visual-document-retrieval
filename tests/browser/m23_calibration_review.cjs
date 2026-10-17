/* Real-data workspace checks; all entered decisions stay in an ephemeral test profile. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const html = path.resolve(process.argv[2] || 'results/m2.3/review/index.html');
  const preview = path.resolve('results/m2.3/review/previews');
  const scratch = path.resolve('.superpowers/m23-review-browser/calibration');
  fs.mkdirSync(preview, { recursive: true });
  fs.mkdirSync(scratch, { recursive: true });
  const executablePath = process.env.BROWSER_PATH || (process.platform === 'win32'
    ? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe' : undefined);
  const browser = await chromium.launch({ headless: true, executablePath });
  const errors = [], checks = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1120 }, acceptDownloads: true });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(html).href);
    await page.waitForFunction(() => document.querySelector('#page-image').naturalWidth > 0);
    const data = await page.evaluate(() => JSON.parse(document.querySelector('#review-data').textContent));
    assert.equal(data.demo, false);
    assert.equal(data.pages.length, 121);
    assert.equal(data.pages.filter(p => p.reference_required).length, 41);
    assert.equal(new Set(data.pages.map(p => p.page_id)).size, 121);
    assert.equal(await page.locator('#reviewed-count').textContent(), '0');
    assert.match(await page.locator('#dataset-badge').textContent(), /DỮ LIỆU THẬT/);
    checks.push('121 real pages / 41 required references; no inherited demo reviews');
    await page.screenshot({ path: path.join(preview, 'native-review.png'), fullPage: true });

    await page.locator('#page-filter').selectOption('holdout');
    assert.equal(await page.locator('.page-item').count(), 40);
    await page.locator('#page-filter').selectOption('required');
    assert.equal(await page.locator('.page-item').count(), 41);
    let selectedIndex = await page.evaluate(() => current);
    assert.equal(data.pages[selectedIndex].reference_required, true);
    const requiredIndices = data.pages.map((p, i) => p.reference_required ? i : -1).filter(i => i >= 0);
    const position = requiredIndices.indexOf(selectedIndex);
    await page.locator('#next-page').click();
    assert.equal(await page.evaluate(() => current), requiredIndices[position + 1]);
    checks.push('Holdout/reference filters select matching pages; next-page stays inside the active filter');

    await page.locator('[data-mode="reference"]').click();
    assert.equal(await page.locator('#pending-count').textContent(), '41');
    await page.locator('#compare-source').selectOption('ocr300');
    selectedIndex = await page.evaluate(() => current);
    const first = data.pages[selectedIndex];
    assert.equal(await page.locator('#comparison-text').textContent(), first.ocr300_text || 'Đầu ra máy rỗng (0 ký tự).');
    assert.equal(await page.locator('#cer-value').textContent(), '—');
    checks.push('Actual OCR 300 output is visible; metrics stay empty without a confirmed reference');
    await page.screenshot({ path: path.join(preview, 'reference-review.png'), fullPage: true });

    const downloading = page.waitForEvent('download');
    await page.locator('#export-button').click();
    const download = await downloading;
    const exportPath = path.join(scratch, 'empty-real-review.json');
    await download.saveAs(exportPath);
    const exported = JSON.parse(fs.readFileSync(exportPath, 'utf8'));
    assert.equal(exported.artifact_type, 'm23_human_review');
    assert.equal(exported.demo, false);
    assert.equal(exported.dataset_sha256, data.dataset_sha256);
    assert.equal(exported.pages.length, 121);
    await page.locator('#import-file').setInputFiles(exportPath);
    await page.waitForFunction(() => document.querySelector('#message').textContent.startsWith('Đã nhập'));
    checks.push('Real review export/import preserves run identity and all pending records');

    await page.locator('#reviewer').fill('Browser fixture — not human evidence');
    await page.locator('#seed-native').click();
    await page.locator('#reference-checked').check();
    await page.locator('#confirm-reference').click();
    await page.locator('#compare-source').selectOption('native');
    assert.equal(await page.locator('#cer-value').textContent(), '0%');
    await page.locator('#reference-text').fill('Changed test reference');
    assert.equal(await page.locator('#reference-status').textContent(), 'BẢN NHÁP');
    assert.equal(await page.locator('#cer-value').textContent(), '—');
    checks.push('Confirmation/edit invalidation works on real data in an ephemeral test profile');
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    checks.push('No browser errors; mobile has no horizontal overflow');
    const receipt = { status: 'PASS', browser: await browser.version(), source_run: data.source_run,
      dataset_sha256: data.dataset_sha256, checks, note: 'No test decisions were written to human review artifacts.' };
    fs.writeFileSync(path.join(preview, 'browser-checks.json'), JSON.stringify(receipt, null, 2) + '\n');
    console.log(JSON.stringify(receipt, null, 2));
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
