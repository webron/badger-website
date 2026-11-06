// A tiny spreadsheet model: cells with a value, an optional formula, a style
// name and an optional hyperlink. The xlsx and CSV writers both read it, so the
// two files always say the same thing.
//
// Every formula cell carries the value the formula yields with the example
// inputs. Viewers that do not recalculate (a file preview, a phone's quick look)
// show that value; Excel, Numbers and Google Sheets recalculate on open.

/** Column index (0-based) to letters: 0 -> A, 27 -> AB. */
export function colName(c) {
  let s = '';
  for (let n = c + 1; n > 0; n = Math.floor((n - 1) / 26)) {
    s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  }
  return s;
}

/** A1-style reference. `abs` pins the column ('c'), the row ('r') or both ('rc'). */
export function ref(r, c, abs = '') {
  return `${abs.includes('c') ? '$' : ''}${colName(c)}${abs.includes('r') ? '$' : ''}${r + 1}`;
}

export class Grid {
  constructor(name) {
    this.name = name;
    this.cells = new Map(); // "r,c" -> { v, f, s, link }
    this.widths = [];
    this.validations = []; // { ref, list: [..] }
    this.freezeRows = 0;
    this.title = '';
  }

  /** Put a cell. `v` is the shown value; `f` (no leading =) makes it a formula. */
  set(r, c, v, opts = {}) {
    this.cells.set(`${r},${c}`, { v, ...opts });
    return this;
  }

  get(r, c) {
    return this.cells.get(`${r},${c}`);
  }

  get rowCount() {
    let max = -1;
    for (const k of this.cells.keys()) max = Math.max(max, Number(k.split(',')[0]));
    return max + 1;
  }

  get colCount() {
    let max = -1;
    for (const k of this.cells.keys()) max = Math.max(max, Number(k.split(',')[1]));
    return max + 1;
  }
}
