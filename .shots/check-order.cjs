const fs = require("fs");
const path = require("path");
function walk(d) {
  return fs.readdirSync(d, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)],
  );
}
for (const f of walk("C:/Users/ashut/Downloads/TazaKhabar/src").filter((f) =>
  f.endsWith(".tsx"),
)) {
  const t = fs.readFileSync(f, "utf8");
  if (!t.includes("@/components/Icon")) continue;
  const lines = t.split("\n");
  const dirIdx = lines.findIndex((l) => l.trim() === '"use client";');
  const impIdx = lines.findIndex((l) => l.includes("components/Icon"));
  if (dirIdx >= 0 && impIdx < dirIdx) console.log("BAD ORDER: " + f);
}
console.log("done");
