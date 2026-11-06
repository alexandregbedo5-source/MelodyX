const fs = require('fs');
const js = fs.readFileSync('app/static/js/opensheetmusicdisplay.min.js', 'utf8');

const target = 'has no outline';
const pos = js.indexOf(target);
console.log(js.substring(pos, pos + 1000));
