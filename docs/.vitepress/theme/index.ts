import Mermaid from "./Mermaid.vue";
import DefaultTheme from "vitepress/theme";
import type { Theme } from "vitepress";
import "./custom.css";

const theme: Theme = {
    ...DefaultTheme,
    enhanceApp(ctx) {
        DefaultTheme.enhanceApp?.(ctx);
        // 覆盖插件默认 Mermaid 组件，避免亮暗模式切换时强制重渲染导致闪烁
        ctx.app.component("Mermaid", Mermaid);
    },
};

export default theme;
