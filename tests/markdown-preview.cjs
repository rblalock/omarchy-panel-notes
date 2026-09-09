const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const preview = vm.createContext({});
vm.runInContext(fs.readFileSync('content/markdown/Preview.js', 'utf8'), preview);
const blocks = value => JSON.parse(JSON.stringify(preview.blocks(value)));

assert.equal(preview.markdown('First line\nSecond line'), 'First line  \nSecond line  ');
assert.deepEqual(blocks('# Heading\nFirst line\nSecond line\n\n> Quote\n> More'), [
  {kind:'text', text:'# Heading'},
  {kind:'text', text:'First line\nSecond line\n'},
  {kind:'quote', text:'Quote\nMore'}
]);
assert.deepEqual(blocks('> Quote\n![Picture](assets/abcdef.png)'), [
  {kind:'quote',text:'Quote'}, {kind:'image',path:'assets/abcdef.png',alt:'Picture'}
]);
const code = '  <tag>\n![Fake image](assets/abcdef.png)\n> literal quote';
assert.deepEqual(blocks('```html\n'+code+'\n```'), [{kind:'code',text:code}]);
assert.deepEqual(blocks('~~~\nunclosed'), [{kind:'code',text:'unclosed'}]);
assert.equal(preview.markdown('```\n<tag>\n```'), '```\n<tag>\n```');
const table = '| A | B |\n|---|---|\n| 1 | 2 |';
assert.equal(preview.markdown(table), table);
const list = '- One\n  - Nested\n\n  ```\n  code\n  ```\n- Two';
assert.deepEqual(blocks(list), [{kind:'text',text:list}]);
assert.equal(preview.markdown('![External](https://example.com/a.png)'), '[Image: External]  ');
assert.equal(preview.markdown('<b>Text</b>'), '&lt;b&gt;Text&lt;/b&gt;  ');
assert.deepEqual(blocks('> One\r\n> Two'), [{kind:'quote',text:'One\nTwo'}]);
console.log('PASS Markdown presentation: line breaks, quotes, literal code, lists, tables, images, source HTML');
