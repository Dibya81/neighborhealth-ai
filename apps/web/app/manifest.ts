import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "NeighborHealth: Dengue early warning",
    short_name: "NeighborHealth",
    description: "Weekly dengue risk for Bengaluru, with alerts for the places you care about.",
    start_url: "/?source=pwa",
    display: "standalone",
    background_color: "#F7F8F8",
    theme_color: "#0E1A2B",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
