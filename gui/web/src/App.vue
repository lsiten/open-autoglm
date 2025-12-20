<template>
  <el-config-provider :dark="true">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { ElConfigProvider } from 'element-plus'
</script>

<style>
/* Ensure full height */
#app {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}
</style>
