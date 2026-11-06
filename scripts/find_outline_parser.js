const fs = require('fs');
const js = fs.readFileSync('app/static/js/opensheetmusicdisplay.min.js', 'utf8');

// Find where .o is split or parsed
let pos = js.indexOf('.split(" ")');
while (pos !== -1) {
  const snippet = js.substring(pos - 50, pos + 100);
  if (snippet.includes('.o') || snippet.includes('outline')) {
    console.log('Found parser snippet:', snippet);
  }
  pos = js.indexOf('.split(" ")', pos + 1);
}
