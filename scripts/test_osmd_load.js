const fs = require('fs');

const xml = fs.readFileSync('uploads/an_ce4fa2f6b6db/an_be261202d301.musicxml', 'utf8');
console.log('XML length:', xml.length);

async function test() {
  try {
    let jsdom;
    try {
      jsdom = require('jsdom');
    } catch(e) {
      console.log('jsdom not installed in project, checking npm list');
      return;
    }
  } catch (err) {
    console.error(err);
  }
}
test();
