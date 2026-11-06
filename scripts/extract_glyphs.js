const fs = require('fs');
const js = fs.readFileSync('app/static/js/opensheetmusicdisplay.min.js', 'utf8');

function extractGlyph(key) {
  const marker = key + ':{';
  const start = js.indexOf(marker);
  const end = js.indexOf('}', start);
  const jsonStr = '{' + js.substring(start, end + 1) + '}';
  console.log(key, 'length:', end - start);
  return js.substring(start, end + 1);
}

const g = extractGlyph('v83');
const f = extractGlyph('v79');

fs.writeFileSync('scripts/glyphs.json', JSON.stringify({ v83: g, v79: f }, null, 2));
console.log('Saved glyphs!');
