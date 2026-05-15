<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <section class="card placeholder-card">
    <div class="placeholder-box">
      <span class="placeholder-badge">占位页面</span>
      <h2 class="placeholder-title">{{ title }}</h2>
      <p class="placeholder-copy">
        {{ description }}
      </p>
      <p class="placeholder-copy">
        当前阶段已完成工作台与智能润色页联调，其余页面先保留路由入口和视觉占位，便于后续逐页补齐业务。
      </p>
    </div>
  </section>
</template>
