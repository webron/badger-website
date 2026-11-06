// Writes a Grid as an .xlsx file by hand: a zip of a few XML parts. No
// spreadsheet library, so the only dependency is the zip encoder.
//
// Kept deliberately small: one sheet, inline strings, a fixed style table,
// list validation, hyperlinks, a frozen header and column widths. The output is
// deterministic (fixed timestamps), so a rebuild of unchanged input is
// byte-identical and the drift test can compare files.

import { zipSync, strToU8 } from 'fflate';
import { colName } from './grid.mjs';

// Style names the builders use -> index into cellXfs below.
export const STYLES = {
  normal: 0,
  title: 1,
  header: 2,
  bold: 3,
  input: 4,
  note: 5,
  link: 6,
  section: 7,
  pct: 8,
  muted: 9,
  wrap: 10,
  calc: 11,
  inputPct: 12,
  headerLeft: 13,
};

const STYLES_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="0.0&quot;%&quot;"/></numFmts>
<fonts count="7">
<font><sz val="11"/><color rgb="FF222B33"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="11"/><color rgb="FF222B33"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="18"/><color rgb="FF222B33"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>
<font><i/><sz val="10"/><color rgb="FF5F6B75"/><name val="Calibri"/><family val="2"/></font>
<font><u/><sz val="11"/><color rgb="FF2E7E90"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="12"/><color rgb="FF1F5E6E"/><name val="Calibri"/><family val="2"/></font>
</fonts>
<fills count="5">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2C2"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF2F3B45"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEFEAE0"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="3">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFC9C2B4"/></left><right style="thin"><color rgb="FFC9C2B4"/></right><top style="thin"><color rgb="FFC9C2B4"/></top><bottom style="thin"><color rgb="FFC9C2B4"/></bottom><diagonal/></border>
<border><left/><right/><top/><bottom style="medium"><color rgb="FF2E7E90"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="14">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="3" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="5" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="6" fillId="4" borderId="2" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="164" fontId="1" fillId="2" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`;

const esc = (s) =>
  String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

/**
 * @param {import('./grid.mjs').Grid} grid
 * @param {{ omitCache?: boolean }} [opts] omitCache leaves out the cached
 *   formula results so a spreadsheet app has to calculate them. The tests use
 *   it to check the formulas against the cached numbers.
 */
export function writeXlsx(grid, opts = {}) {
  const rows = new Map();
  for (const [key, cell] of grid.cells) {
    const [r, c] = key.split(',').map(Number);
    if (!rows.has(r)) rows.set(r, []);
    rows.get(r).push([c, cell]);
  }
  const links = [];
  let sheetData = '';
  for (const r of [...rows.keys()].sort((a, b) => a - b)) {
    const cells = rows.get(r).sort((a, b) => a[0] - b[0]);
    sheetData += `<row r="${r + 1}">`;
    for (const [c, cell] of cells) {
      const a1 = `${colName(c)}${r + 1}`;
      const s = STYLES[cell.s ?? 'normal'];
      if (cell.link) links.push({ a1, url: cell.link });
      if (cell.f) {
        const isText = typeof cell.v === 'string';
        const cache = opts.omitCache || cell.v === undefined || cell.v === ''
          ? ''
          : `<v>${esc(cell.v)}</v>`;
        sheetData += `<c r="${a1}" s="${s}"${isText ? ' t="str"' : ''}><f>${esc(cell.f)}</f>${cache}</c>`;
      } else if (typeof cell.v === 'number') {
        sheetData += `<c r="${a1}" s="${s}"><v>${cell.v}</v></c>`;
      } else if (cell.v === '' || cell.v === undefined || cell.v === null) {
        sheetData += `<c r="${a1}" s="${s}"/>`;
      } else {
        sheetData += `<c r="${a1}" s="${s}" t="inlineStr"><is><t xml:space="preserve">${esc(cell.v)}</t></is></c>`;
      }
    }
    sheetData += '</row>';
  }

  const lastCol = colName(Math.max(0, grid.colCount - 1));
  const cols = grid.widths
    .map((w, i) => `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`)
    .join('');
  const pane = grid.freezeRows
    ? `<pane ySplit="${grid.freezeRows}" topLeftCell="A${grid.freezeRows + 1}" activePane="bottomLeft" state="frozen"/>`
    : '';
  const validations = grid.validations.length
    ? `<dataValidations count="${grid.validations.length}">${grid.validations
        .map(
          (v) =>
            `<dataValidation type="list" allowBlank="1" showErrorMessage="1" sqref="${v.ref}"><formula1>"${esc(v.list.join(','))}"</formula1></dataValidation>`,
        )
        .join('')}</dataValidations>`
    : '';
  const hyperlinks = links.length
    ? `<hyperlinks>${links.map((l, i) => `<hyperlink ref="${l.a1}" r:id="rId${i + 1}"/>`).join('')}</hyperlinks>`
    : '';

  const sheet = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<dimension ref="A1:${lastCol}${Math.max(1, grid.rowCount)}"/>
<sheetViews><sheetView workbookViewId="0" showGridLines="0">${pane}</sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="15"/>
<cols>${cols}</cols>
<sheetData>${sheetData}</sheetData>${validations}${hyperlinks}
<pageMargins left="0.5" right="0.5" top="0.6" bottom="0.6" header="0.3" footer="0.3"/>
<pageSetup orientation="landscape" fitToHeight="0"/>
</worksheet>`;

  const sheetRels = links.length
    ? `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${links
        .map(
          (l, i) =>
            `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="${esc(l.url)}" TargetMode="External"/>`,
        )
        .join('')}</Relationships>`
    : null;

  const files = {
    '[Content_Types].xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>`,
    '_rels/.rels': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>`,
    'docProps/core.xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>${esc(grid.title)}</dc:title><dc:creator>Badger</dc:creator></cp:coreProperties>`,
    'xl/workbook.xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><bookViews><workbookView/></bookViews><sheets><sheet name="${esc(grid.name)}" sheetId="1" r:id="rId1"/></sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>`,
    'xl/_rels/workbook.xml.rels': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`,
    'xl/styles.xml': STYLES_XML,
    'xl/worksheets/sheet1.xml': sheet,
  };
  if (sheetRels) files['xl/worksheets/_rels/sheet1.xml.rels'] = sheetRels;

  // Fixed timestamp and sorted entries: the same grid always zips to the same bytes.
  const mtime = new Date(Date.UTC(2026, 0, 1));
  const zipInput = {};
  for (const name of Object.keys(files).sort()) {
    zipInput[name] = [strToU8(files[name]), { mtime, level: 9 }];
  }
  return zipSync(zipInput);
}
