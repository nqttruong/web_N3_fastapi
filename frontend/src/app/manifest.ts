import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "JLPT AI Review",
    short_name: "JLPT N3",
    description: "Học và ôn JLPT N3 trên Web",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f5f8fa",
    theme_color: "#315984",
    icons: [
      { src: "/pwa-icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/pwa-icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
