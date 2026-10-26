// Copies the ward boundaries into public/ so the map can load them as a static file.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../../frontend/assets/bengaluru-wards.geojson");
const dest = resolve(here, "../public/data/wards.geojson");
mkdirSync(dirname(dest), { recursive: true });
if (existsSync(src)) {
  copyFileSync(src, dest);
  console.log("wards.geojson ready");
} else if (!existsSync(dest)) {
  console.warn(`Ward boundaries not found at ${src}; the map will be empty.`);
}
