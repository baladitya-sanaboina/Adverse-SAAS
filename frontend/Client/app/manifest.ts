import type { MetadataRoute } from "next";

// Installable app (owner request 2026-11-15): Chrome, Edge and Safari offer "Install" for it.
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Adverse Client",
    short_name: "Client",
    description: "Adverse Client workspace",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    background_color: "#F8FBFF",
    theme_color: "#0876ED",
    icons: [
      { src: "/logos/adverse-favicon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/logos/adverse-favicon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    ],
  };
}
