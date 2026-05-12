import { defineConfig } from "vitepress";
import { withMermaid } from "vitepress-plugin-mermaid";
import { generateSidebar } from "vitepress-sidebar";

export default withMermaid(
  defineConfig({
    title: "AuroraBot",
    description: "AuroraBot — 一个本地运行的、自循环、自规划的数字生命",
    base: "/AuroraBot/",
    cleanUrls: true,
    lastUpdated: true,
    head: [
      [
        "link",
        { rel: "icon", type: "image/svg+xml", href: "/AuroraBot/logo.svg" },
      ],
    ],
    mermaid: {
      theme: "default",
      securityLevel: "loose",
      look: "handDrawn",
      startOnLoad: false,
      flowchart: {
        curve: "basis",
      },
    },
    themeConfig: {
      nav: [
        { text: "首页", link: "/" },
        { text: "开始", link: "/start/overview" },
        { text: "架构", link: "/architecture/system-overview" },
        { text: "开发", link: "/guide/app-development" },
      ],
      sidebar: generateSidebar({
        documentRootPath: ".",
        scanStartPath: ".",
        resolvePath: "/",
        useTitleFromFileHeading: true,
        useFolderTitleFromIndexFile: true,
        includeFolderIndexFile: false,
        sortMenusByFrontmatterOrder: true,
        frontmatterOrderDefaultValue: 99,
        collapsed: false,
      }),
      search: {
        provider: "local",
      },
      socialLinks: [
        { icon: "github", link: "https://github.com/JuFireX/AuroraBot" },
      ],
      outline: {
        label: "本页内容",
      },
      docFooter: {
        prev: "上一页",
        next: "下一页",
      },
      lastUpdated: {
        text: "最后更新",
        formatOptions: {
          dateStyle: "short",
          timeStyle: "medium",
        },
      },
      footer: {
        message: "Built with VitePress",
        copyright: "Copyright © 2026 JuFireX",
      },
    },
  }),
);
