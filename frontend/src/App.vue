<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

interface Ripple { id: number; x: number; y: number; strong: boolean }
const ripples = ref<Ripple[]>([])
const timers = new Set<number>()
let rippleId = 0
let lastRippleAt = 0

function createRipple(event: PointerEvent, strong = false) {
  const now = performance.now()
  if (!strong && now - lastRippleAt < 95) return
  lastRippleAt = now
  document.documentElement.style.setProperty('--cursor-x', `${event.clientX}px`)
  document.documentElement.style.setProperty('--cursor-y', `${event.clientY}px`)
  const id = ++rippleId
  ripples.value.push({ id, x: event.clientX, y: event.clientY, strong })
  if (ripples.value.length > 9) ripples.value.shift()
  const timer = window.setTimeout(() => {
    ripples.value = ripples.value.filter((ripple) => ripple.id !== id)
    timers.delete(timer)
  }, strong ? 1500 : 1150)
  timers.add(timer)
}

function trackPointer(event: PointerEvent) { createRipple(event) }
function emphasizeRipple(event: PointerEvent) { createRipple(event, true) }
onMounted(() => {
  window.addEventListener('pointermove', trackPointer, { passive: true })
  window.addEventListener('pointerdown', emphasizeRipple, { passive: true })
})
onBeforeUnmount(() => {
  window.removeEventListener('pointermove', trackPointer)
  window.removeEventListener('pointerdown', emphasizeRipple)
  timers.forEach((timer) => window.clearTimeout(timer))
})
</script>

<template>
  <div class="global-ripples" aria-hidden="true"><i v-for="ripple in ripples" :key="ripple.id" :class="{ strong: ripple.strong }" :style="{ left: `${ripple.x}px`, top: `${ripple.y}px` }"></i></div>
  <router-view />
</template>
