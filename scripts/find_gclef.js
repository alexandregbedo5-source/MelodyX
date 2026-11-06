const fs = require('fs');
const js = fs.readFileSync('app/static/js/opensheetmusicdisplay.min.js', 'utf8');

// Search for outline or path of gClef
let pos = js.indexOf('gClef');
while (pos !== -1) {
  console.log('Found at pos', pos, ':', js.substring(pos - 30, pos + 100));
  pos = js.indexOf('gClef', pos + 1);
  if (pos > 500000) break;
}
