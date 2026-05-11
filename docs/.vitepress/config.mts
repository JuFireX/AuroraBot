import { defineConfig } from "vitepress";
import { withMermaid } from "vitepress-plugin-mermaid";

export default withMermaid(
  defineConfig({
    title: "AuroraBot",
    description: "AuroraBot — 一个本地运行的、自循环、自规划的数字生命",
    base: "/AuroraBot/",
    cleanUrls: false,
    lastUpdated: true,
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
        { text: "开始", link: "/start/overview.html" },
        { text: "架构", link: "/architecture/system-overview.html" },
        { text: "开发", link: "/guide/app-development.html" },
      ],
      sidebar: [
        {
          text: "开始",
          items: [
            { text: "项目总览", link: "/start/overview.html" },
            { text: "快速开始", link: "/start/getting-started.html" },
          ],
        },
        {
          text: "架构",
          items: [
            {
              text: "系统架构总览",
              link: "/architecture/system-overview.html",
            },
            {
              text: "内核流水线",
              link: "/architecture/kernel-pipeline.html",
            },
            {
              text: "平台运行时",
              link: "/architecture/platform-runtime.html",
            },
          ],
        },
        {
          text: "开发",
          items: [
            {
              text: "App 开发者指南",
              link: "/guide/app-development.html",
            },
          ],
        },
        {
          text: "路线图",
          items: [
            {
              text: "AUR CLI 路线图",
              link: "/roadmap/aur-cli.html",
            },
          ],
        },
      ],
      search: {
        provider: "local",
      },
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
        copyright: "Copyright © 2026 AuroraBot",
      },
    },
  })
);
