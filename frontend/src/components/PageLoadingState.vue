<script setup>
defineProps({
  title: {
    type: String,
    default: '正在加载中...',
  },
  description: {
    type: String,
    default: '请稍候，数据加载中',
  },
})
</script>

<template>
  <div class="page-loading-state" role="status" aria-live="polite">
    <div class="page-loading-spinner" aria-hidden="true"></div>
    <strong>{{ title }}</strong>
    <p>{{ description }}</p>
  </div>
</template>
