import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const projectDirectory = dirname(fileURLToPath(import.meta.url));
const workspaceDirectory = resolve(projectDirectory, "..");
const workspaceNextPackage = resolve(workspaceDirectory, "node_modules/next/package.json");

const nextConfig: NextConfig = {
  devIndicators: false,
  turbopack: {
    root: existsSync(workspaceNextPackage) ? workspaceDirectory : projectDirectory,
  },
};

export default nextConfig;
