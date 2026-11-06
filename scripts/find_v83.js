const fs = require('fs');
const js = fs.readFileSync('app/static/js/opensheetmusicdisplay.min.js', 'utf8');

let pos = js.indexOf('v83:');
if (pos === -1) pos = js.indexOf('"v83"');
console.log('v83 at pos', pos);
if (pos !== -1) {
  console.log(js.substring(pos, pos + 300));
}

let posF = js.indexOf('v79:');
if (posF === -1) posF = js.indexOf('"v79"');
console.log('v79 at pos', posF);
if (posF !== -1) {
  console.log(js.substring(posF, posF + 300));
}
