/* Local browser checks for the review prototype. No OCR, GPU, or Modal calls. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const html = path.resolve(process.argv[2] || 'results/m2.3/review-demo-2026-10-17/index.html');
  const outputs = path.resolve('.superpowers/m23-review-browser/output');
  fs.mkdirSync(outputs, { recursive: true });
  const preview = path.join(path.dirname(html), 'previews');
  fs.mkdirSync(preview, { recursive: true });
  const executable = process.env.BROWSER_PATH || (process.platform === 'win32'
    ? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe' : undefined);
  const browser = await chromium.launch({ headless: true, executablePath: executable });
  const errors = [], requests = [], checks = [];
  const check = name => checks.push(name);
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1120 }, acceptDownloads: true });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) requests.push(request.url()); });
    await page.goto(pathToFileURL(html).href);
    await page.waitForFunction(() => document.querySelector('#page-image').naturalWidth > 0);
    assert.equal(await page.locator('.page-item').count(), 16);
    assert.equal(await page.locator('#reviewed-count').textContent(), '0');
    check('16 real pages load from file URL; review starts pending');

    await page.locator('#save-native').click();
    assert.match(await page.locator('#message').textContent(), /Điền tên/);
    await page.locator('#reviewer').fill('Browser test');
    await page.locator('[name="native-status"][value="HAS_ERRORS"]').check();
    await page.locator('#native-image-checked').check();
    await page.locator('#save-native').click();
    assert.match(await page.locator('#message').textContent(), /Chọn loại lỗi/);
    await page.locator('#issue-options input[value="reading_order"]').check();
    await page.locator('#native-note').fill('Test fixture: check columns.');
    await page.locator('#save-native').click();
    assert.equal(await page.locator('#reviewed-count').textContent(), '1');
    await page.reload();
    assert.equal(await page.locator('#reviewed-count').textContent(), '1');
    assert.equal(await page.locator('#native-note').inputValue(), 'Test fixture: check columns.');
    check('Native review requires reviewer, image check, error reason and persists after reload');

    await page.locator('[data-mode="reference"]').click();
    await page.locator('#seed-native').click();
    assert.equal(await page.locator('#cer-value').textContent(), '—');
    await page.locator('#confirm-reference').click();
    assert.match(await page.locator('#message').textContent(), /đối chiếu toàn bộ/);
    await page.locator('#reference-checked').check();
    await page.locator('#confirm-reference').click();
    assert.equal(await page.locator('#cer-value').textContent(), '0%');
    assert.equal(await page.locator('#wer-value').textContent(), '0%');
    const original = await page.locator('#reference-text').inputValue();
    await page.locator('#reference-text').fill(original + ' changed');
    assert.equal(await page.locator('#reference-status').textContent(), 'BẢN NHÁP');
    assert.equal(await page.locator('#cer-value').textContent(), '—');
    check('Drafts do not produce metrics; confirmation enables metrics; edits invalidate confirmation');

    await page.locator('#reference-scope').selectOption('excerpt');
    await page.locator('#reference-checked').check();
    await page.locator('#confirm-reference').click();
    assert.match(await page.locator('#message').textContent(), /Mô tả vùng/);
    await page.locator('#reference-region').fill('Test region only');
    await page.locator('#reference-checked').check();
    await page.locator('#confirm-reference').click();
    assert.equal(await page.locator('#cer-value').textContent(), '—');
    assert.match(await page.locator('#cer-detail').textContent(), /cùng vùng/);
    check('Excerpt references cannot be scored against full-page outputs');

    await page.locator('#reference-scope').selectOption('full_page');
    await page.locator('#reference-text').fill('');
    await page.locator('#reference-no-text').check();
    await page.locator('#reference-checked').check();
    await page.locator('#confirm-reference').click();
    assert.equal(await page.locator('#cer-value').textContent(), '—');
    assert.match(await page.locator('#metric-note').textContent(), /nhận thừa/);
    await page.locator('#compare-source').selectOption('ocr300');
    assert.match(await page.locator('#comparison-text').textContent(), /Chưa chạy OCR 300/);
    assert.equal(await page.locator('#cer-value').textContent(), '—');
    check('No-text references avoid division by zero; missing OCR 300 never produces a metric');

    assert.equal(await page.evaluate(() => editDistance(Array.from('100'), Array.from('180'))), 1);
    assert.equal(await page.evaluate(() => editDistance(Array.from(normalize('e\u0301')), Array.from(normalize('é')))), 0);
    assert.equal(await page.evaluate(() => editDistance([], ['x'])), 1);
    assert.equal(await page.evaluate(() => editDistance(['a'], ['b', 'b', 'b'])), 3);
    check('Edit distance handles substitutions, Unicode NFC, empty inputs and insertion rates above 100%');

    const downloading = page.waitForEvent('download');
    await page.locator('#export-button').click();
    const download = await downloading;
    const exportPath = path.join(outputs, 'reviews.json');
    await download.saveAs(exportPath);
    const exported = JSON.parse(fs.readFileSync(exportPath, 'utf8'));
    assert.equal(exported.pages.length, 16);
    assert.equal(exported.demo, true);
    const altered = { ...exported, dataset_sha256: 'wrong-hash' };
    await page.locator('#import-file').setInputFiles({ name: 'wrong.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(altered)) });
    await page.waitForFunction(() => document.querySelector('#message').textContent.startsWith('Không nhập được'));
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.locator('#import-file').setInputFiles(exportPath);
    await page.waitForFunction(() => document.querySelector('#message').textContent.startsWith('Đã nhập'));
    assert.equal(await page.locator('#reviewed-count').textContent(), '1');
    check('JSON export/import round-trip preserves review; dataset hash mismatch is rejected');

    const cleanContext = await browser.newContext({ viewport: { width: 1440, height: 1120 } });
    const clean = await cleanContext.newPage();
    clean.on('pageerror', error => errors.push(error.message));
    await clean.goto(pathToFileURL(html).href);
    await clean.waitForFunction(() => document.querySelector('#page-image').naturalWidth > 0);
    await clean.screenshot({ path: path.join(preview, 'native-review.png'), fullPage: true });
    await clean.locator('[data-mode="reference"]').click();
    await clean.locator('#seed-native').click();
    await clean.screenshot({ path: path.join(preview, 'reference-review.png'), fullPage: true });
    await clean.setViewportSize({ width: 390, height: 844 });
    assert.equal(await clean.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await clean.screenshot({ path: path.join(preview, 'mobile-review.png') });
    check('Desktop screenshots captured; mobile has no horizontal overflow');
    assert.deepEqual(errors, []);
    assert.deepEqual(requests, []);
    check('No JavaScript errors or external HTTP requests');
    fs.writeFileSync(path.join(preview, 'browser-checks.json'), JSON.stringify({ status: 'PASS', browser: await browser.version(), checks }, null, 2) + '\n');
    console.log(JSON.stringify({ status: 'PASS', checks, previews: preview }, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
