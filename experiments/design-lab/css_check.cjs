// Usage: node css_check.cjs <templateDir> <file.css>...
// Parses each stylesheet with the same minifier the build uses and prints JSON [{file, line, message}] for failures,
// so a syntax error points at the source line instead of a line in the bundled output.
const fs = require("fs");
const [templateDir, ...files] = process.argv.slice(2);
const { transform } = require(templateDir + "/node_modules/lightningcss");
const problems = [];
for (const file of files) {
  try {
    transform({ filename: file, code: fs.readFileSync(templateDir + "/" + file), minify: true });
  } catch (error) {
    problems.push({ file, line: error.loc ? error.loc.line : 0, message: error.message });
  }
}
console.log(JSON.stringify(problems));
