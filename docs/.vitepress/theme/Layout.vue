<script setup>
import DefaultTheme from "vitepress/theme";
import ShootingStar from "./ShootingStar.vue";

const { Layout } = DefaultTheme;
</script>

<template>
  <Layout>
    <template #home-hero-after>
      <ShootingStar />
    </template>
  </Layout>
</template>
