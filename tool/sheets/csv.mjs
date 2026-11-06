// Writes a Grid as CSV. Formula cells are written as formulas ("=ROUND(...)"),
// which Google Sheets, Excel and Numbers all evaluate on import, so the sheet
// still calculates after File > Import. Cells with a number or text are
// written as they are.

function field(text) {
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function writeCsv(grid) {
  const rowCount = grid.rowCount;
  const colCount = grid.colCount;
  const lines = [];
  for (let r = 0; r < rowCount; r++) {
    const out = [];
    for (let c = 0; c < colCount; c++) {
      const cell = grid.get(r, c);
      if (!cell) out.push('');
      else if (cell.f) out.push(field(`=${cell.f}`));
      else if (cell.v === undefined || cell.v === null) out.push('');
      else out.push(field(String(cell.v)));
    }
    // Trim trailing empties so the file does not end every row in a run of commas.
    while (out.length && out[out.length - 1] === '') out.pop();
    lines.push(out.join(','));
  }
  return lines.join('\r\n') + '\r\n';
}
