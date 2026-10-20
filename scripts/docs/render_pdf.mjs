// Render HTML documents to PDF with running header/footer and "page X of Y".
// Usage: node scripts/docs/render_pdf.mjs <jobs.json>   (jobs: [{html, pdf, header, footer}])
import { readFileSync } from 'fs';
import { pathToFileURL } from 'url';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  ({ chromium } = await import('playwright'));
}

const jobs = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const browser = await chromium.launch();
const style = 'font-family:"Segoe UI",Arial,sans-serif;font-size:7.5pt;color:#5b6675;width:100%;padding:0 18mm;display:flex;justify-content:space-between;';
for (const j of jobs) {
  const page = await browser.newPage();
  await page.goto(pathToFileURL(j.html).href, { waitUntil: 'load' });
  await page.pdf({
    path: j.pdf,
    format: 'A4',
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: !j.plain,
    headerTemplate: j.plain ? '<span></span>' : `<div style='${style}'><span>${j.header}</span><span>Team Kendali · ITB</span></div>`,
    footerTemplate: j.plain ? '<span></span>' : `<div style='${style}'><span>${j.footer}</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>`,
  });
  await page.close();
  console.log('wrote', j.pdf);
}
await browser.close();
