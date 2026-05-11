<template>
  <div :class="props.class" v-html="svg"></div>
</template>

<script setup lang="ts">
import mermaid, { type MermaidConfig } from "mermaid";
import { onMounted, onUnmounted, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    graph: string;
    id: string;
    class?: string;
  }>(),
  {
    class: "mermaid",
  },
);

const svg = ref("");
let renderCount = 0;
let observer: MutationObserver | null = null;

const renderChart = async () => {
  const hasDarkClass = document.documentElement.classList.contains("dark");
  const config: MermaidConfig = {
    securityLevel: "loose",
    startOnLoad: false,
    theme: hasDarkClass ? "dark" : "neutral",
    look: "handDrawn",
    flowchart: {
      curve: "basis",
    },
  };

  mermaid.initialize(config);
  const uniqueId = `${props.id}-${renderCount++}`;
  const { svg: renderedSvg } = await mermaid.render(uniqueId, decodeURIComponent(props.graph));
  svg.value = renderedSvg;
};

onMounted(async () => {
  await renderChart();

  // 仅监听亮暗主题切换，保留基础亮暗适配并避免全局样式 hack。
  observer = new MutationObserver(async () => {
    await renderChart();
  });
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
});

watch(
  () => props.graph,
  async () => {
    await renderChart();
  },
);

onUnmounted(() => {
  observer?.disconnect();
  observer = null;
});
</script>
