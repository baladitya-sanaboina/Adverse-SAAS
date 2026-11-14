import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const projectDirectory = dirname(fileURLToPath(import.meta.url));
const workspaceDirectory = resolve(projectDirectory, "..");
const workspaceNextPackage = resolve(workspaceDirectory, "node_modules/next/package.json");

// Sent with every page and API response: no framing by other sites (clickjacking), no MIME
// sniffing of downloads, and camera/microphone/screen only for this app's own calls.
const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(self), microphone=(self), display-capture=(self), geolocation=()",
  },
];

const nextConfig: NextConfig = {
  devIndicators: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  turbopack: {
    root: existsSync(workspaceNextPackage) ? workspaceDirectory : projectDirectory,
  },
};

export default nextConfig;
