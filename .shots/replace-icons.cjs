const fs = require("fs");
const path = require("path");
const root = "C:/Users/ashut/Downloads/TazaKhabar/src";

function walk(d) {
  return fs.readdirSync(d, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(path.join(d, e.name)) : path.join(d, e.name),
  );
}

const files = walk(root).filter((f) => f.endsWith(".tsx") && !f.endsWith("Icon.tsx"));
let total = 0;
const STATIC = /<span\s+className="material-symbols-outlined([^"]*)"\s+aria-hidden\s*>\s*([a-z0-9_]+)\s*<\/span>/g;

for (const f of files) {
  let s = fs.readFileSync(f, "utf8");
  const before = s;
  s = s.replace(STATIC, (_, cls, name) =>
    `<Icon name="${name}" className="${cls.trim()}" aria-hidden />`,
  );
  if (s === before) continue;
  if (!s.includes('from "@/components/Icon"')) {
    const m = s.match(/^import[^\n]*\n(?=(?:import|\/\/))/m);
    if (m) s = s.slice(0, m.index + m[0].length) + 'import { Icon } from "@/components/Icon";\n' + s.slice(m.index + m[0].length);
    else s = 'import { Icon } from "@/components/Icon";\n' + s;
  }
  fs.writeFileSync(f, s);
  const n =
    (before.match(/material-symbols-outlined/g) || []).length -
    (s.match(/material-symbols-outlined/g) || []).length;
  total += n;
  console.log(`${path.basename(path.dirname(f))}/${path.basename(f)} -${n}`);
}
console.log("total replaced:", total);

// Remaining (dynamic) material spans for manual edit
for (const f of walk(root).filter((f) => f.endsWith(".tsx"))) {
  const s = fs.readFileSync(f, "utf8");
  if (s.includes("material-symbols-outlined"))
    console.log(`REMAINING: ${path.relative(root, f)}`);
}
