<script setup>
const props = defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  notifications: {
    type: Array,
    default: () => [],
  },
  unreadCount: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['close', 'open-detail'])

function handleOverlayClick(event) {
  if (event.target === event.currentTarget) {
    emit('close')
  }
}
</script>

<template>
  <div v-if="open" class="notification-overlay" @click="handleOverlayClick">
    <aside class="notification-drawer">
      <div class="notification-drawer-header">
        <div>
          <h2 class="notification-drawer-title">消息</h2>
          <p class="notification-drawer-subtitle">当前有 {{ unreadCount }} 条未读提醒</p>
        </div>
        <button class="notification-close" type="button" @click="emit('close')">×</button>
      </div>

      <div class="notification-drawer-list">
        <button
          v-for="notification in props.notifications"
          :key="notification.id"
          type="button"
          class="notification-list-item"
          :class="{ 'is-unread': !notification.isRead }"
          @click="emit('open-detail', notification)"
        >
          <span class="notification-item-marker">
            <span v-if="!notification.isRead" class="notification-unread-dot"></span>
          </span>
          <div class="notification-item-main">
            <strong>{{ notification.title }}</strong>
            <p>{{ notification.summary }}</p>
            <small>{{ notification.createdAt }}</small>
          </div>
        </button>
      </div>
    </aside>
  </div>
</template>
