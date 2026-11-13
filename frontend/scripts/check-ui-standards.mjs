import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const applications = ["Admin", "Manager", "Employee", "Client"];
const sourceDirectories = ["app", "components"];
const violations = [];

async function inspect(directory) {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return;
    throw error;
  }

  await Promise.all(
    entries.map(async (entry) => {
      const entryPath = path.join(directory, entry.name);
      if (entry.isDirectory()) return inspect(entryPath);
      if (!entry.isFile() || !/\.(?:ts|tsx)$/.test(entry.name)) return;

      const source = await readFile(entryPath, "utf8");
      if (/<\/?(?:select|option)(?:\s|>)/i.test(source)) {
        violations.push(path.relative(process.cwd(), entryPath));
      }
    }),
  );
}

for (const application of applications) {
  for (const sourceDirectory of sourceDirectories) {
    await inspect(path.join(process.cwd(), application, sourceDirectory));
  }
}

await inspect(path.join(process.cwd(), "shared"));

if (violations.length > 0) {
  console.error("Native browser dropdowns are prohibited by docs/UIStandards.md:");
  for (const violation of violations.sort()) console.error(`- ${violation}`);
  console.error("Use the reusable LooplessSelect component instead.");
  process.exit(1);
}

console.log("UI standards check passed: no native browser dropdowns found.");
