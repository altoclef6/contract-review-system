<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

function trackPointer(event: PointerEvent) {
  document.documentElement.style.setProperty('--cursor-x', `${event.clientX}px`)
  document.documentElement.style.setProperty('--cursor-y', `${event.clientY}px`)
}

onMounted(() => window.addEventListener('pointermove', trackPointer, { passive: true }))
onBeforeUnmount(() => window.removeEventListener('pointermove', trackPointer))
</script>

<template>
  <div class="global-particles" aria-hidden="true"><i v-for="index in 18" :key="index"></i></div>
  <router-view />
</template>
