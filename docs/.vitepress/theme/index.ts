import Mermaid from "./Mermaid.vue";
import DefaultTheme from "vitepress/theme";
import type { Theme } from "vitepress";
import Layout from "./Layout.vue";
import "./custom.css";

const theme: Theme = {
    extends: DefaultTheme,
    Layout,
    enhanceApp(ctx) {
        DefaultTheme.enhanceApp?.(ctx);
        ctx.app.component("Mermaid", Mermaid);
    },
};

export default theme;
