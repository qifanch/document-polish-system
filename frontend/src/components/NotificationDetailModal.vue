<script setup>
defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  notification: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['close'])

function handleOverlayClick(event) {
  if (event.target === event.currentTarget) {
    emit('close')
  }
}
</script>

<template>
  <div v-if="open && notification" class="notification-modal-overlay" @click="handleOverlayClick">
    <section class="notification-modal">
      <button class="notification-modal-close" type="button" @click="emit('close')">×</button>
      <p class="notification-modal-label">消息详情</p>
      <header class="notification-modal-header">
        <h3>{{ notification.title }}</h3>
        <span>{{ notification.createdAt }}</span>
      </header>
      <div class="notification-modal-body">
        <p>{{ notification.content }}</p>
      </div>
      <footer class="notification-modal-footer">
        <button class="cta-button notification-confirm" type="button" @click="emit('close')">已知晓</button>
      </footer>
    </section>
  </div>
</template>
