import type { MetadataRoute } from "next";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tazakhabar.vercel.app";

export default function sitemap(): MetadataRoute.Sitemap {
  const routes = ["", "/auth", "/jobs", "/digest", "/trends", "/profile", "/qa"];
  return routes.map((route) => ({
    url: `${siteUrl}${route}`,
    lastModified: new Date(),
    changeFrequency: route === "" ? "daily" : "weekly",
    priority: route === "" ? 1 : route === "/jobs" ? 0.9 : 0.6,
  }));
}
