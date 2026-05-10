import { defineConfig } from "vitepress";

export default defineConfig({
  title: "AuroraBot",
  description: "AuroraBot 项目文档",
  base: "/AuroraBot/",
  cleanUrls: false,
  lastUpdated: true,
  themeConfig: {
    nav: [
      { text: "首页", link: "/" },
      { text: "项目总览", link: "/README.html" },
      { text: "App 开发", link: "/APP_DEVELOPMENT_GUIDE.html" },
    ],
    sidebar: [
      {
        text: "开始",
        items: [
          { text: "首页", link: "/" },
          { text: "项目总览", link: "/README.html" },
        ],
      },
      {
        text: "架构与设计",
        items: [
          {
            text: "内核架构",
            link: "/KERNEL_ARCHITECTURE_PLAN.html",
          },
          {
            text: "Platform 与 App 架构",
            link: "/PLATFORM_APP_ARCHITECTURE.html",
          },
          {
            text: "AUR CLI 规划",
            link: "/AUR_CLI_PLAN.html",
          },
        ],
      },
      {
        text: "开发",
        items: [
          {
            text: "App 开发者指南",
            link: "/APP_DEVELOPMENT_GUIDE.html",
          },
        ],
      },
    ],
    search: {
      provider: "local",
    },
    footer: {
      message: "Built with VitePress",
      copyright: "Copyright © 2026 AuroraBot",
    },
  },
});
