<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

interface Particle { x: number; y: number; vx: number; vy: number; size: number; alpha: number; tone: number }
interface WaveParticle extends Particle { life: number; maxLife: number }

const canvas = ref<HTMLCanvasElement>()
const field: Particle[] = []
const waves: WaveParticle[] = []
const pointer = { x: -1000, y: -1000, px: -1000, py: -1000, vx: 0, vy: 0 }
let context: CanvasRenderingContext2D | null = null
let frame = 0
let width = 0
let height = 0
let lastWaveAt = 0

function resetField() {
  const target = Math.min(190, Math.max(80, Math.floor((width * height) / 9500)))
  field.length = 0
  for (let index = 0; index < target; index += 1) {
    field.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.16,
      vy: (Math.random() - 0.5) * 0.16,
      size: Math.random() * 1.4 + 0.45,
      alpha: Math.random() * 0.36 + 0.14,
      tone: Math.random(),
    })
  }
}

function resize() {
  if (!canvas.value) return
  const ratio = Math.min(window.devicePixelRatio || 1, 1.75)
  width = window.innerWidth
  height = window.innerHeight
  canvas.value.width = Math.floor(width * ratio)
  canvas.value.height = Math.floor(height * ratio)
  canvas.value.style.width = `${width}px`
  canvas.value.style.height = `${height}px`
  context = canvas.value.getContext('2d')
  context?.setTransform(ratio, 0, 0, ratio, 0, 0)
  resetField()
}

function emitWave(x: number, y: number, strength = 1) {
  const count = Math.round(24 * strength)
  for (let index = 0; index < count; index += 1) {
    const angle = (Math.PI * 2 * index) / count + Math.random() * 0.08
    const speed = (0.9 + Math.random() * 0.75) * strength
    waves.push({ x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, size: Math.random() + 0.6, alpha: 0.8, tone: index / count, life: 0, maxLife: 58 + Math.random() * 18 })
  }
  if (waves.length > 260) waves.splice(0, waves.length - 260)
}

function move(event: PointerEvent) {
  pointer.px = pointer.x
  pointer.py = pointer.y
  pointer.x = event.clientX
  pointer.y = event.clientY
  pointer.vx = pointer.px < 0 ? 0 : pointer.x - pointer.px
  pointer.vy = pointer.py < 0 ? 0 : pointer.y - pointer.py
  const now = performance.now()
  if (now - lastWaveAt > 115 && Math.hypot(pointer.vx, pointer.vy) > 2) {
    emitWave(pointer.x, pointer.y, 0.72)
    lastWaveAt = now
  }
}

function drawParticle(particle: Particle, alpha = particle.alpha) {
  if (!context) return
  const color = particle.tone > 0.9 ? `255,78,132` : particle.tone > 0.78 ? `226,192,90` : `125,255,190`
  context.fillStyle = `rgba(${color},${alpha})`
  context.shadowColor = `rgba(${color},${Math.min(alpha, 0.55)})`
  context.shadowBlur = particle.size * 5
  context.beginPath()
  context.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2)
  context.fill()
}

function animate() {
  if (!context) return
  context.clearRect(0, 0, width, height)
  for (const particle of field) {
    const dx = particle.x - pointer.x
    const dy = particle.y - pointer.y
    const distance = Math.hypot(dx, dy)
    if (distance < 145 && distance > 0) {
      const force = (145 - distance) / 145
      particle.vx += (dx / distance) * force * 0.13 + pointer.vx * force * 0.018
      particle.vy += (dy / distance) * force * 0.13 + pointer.vy * force * 0.018
    }
    particle.vx *= 0.965
    particle.vy *= 0.965
    particle.x += particle.vx
    particle.y += particle.vy
    if (particle.x < -8) particle.x = width + 8
    if (particle.x > width + 8) particle.x = -8
    if (particle.y < -8) particle.y = height + 8
    if (particle.y > height + 8) particle.y = -8
    drawParticle(particle)
  }
  for (let index = waves.length - 1; index >= 0; index -= 1) {
    const particle = waves[index]
    particle.life += 1
    particle.x += particle.vx
    particle.y += particle.vy
    particle.vx *= 1.012
    particle.vy *= 1.012
    const remaining = 1 - particle.life / particle.maxLife
    drawParticle(particle, Math.max(0, remaining) * 0.72)
    if (particle.life >= particle.maxLife) waves.splice(index, 1)
  }
  pointer.vx *= 0.82
  pointer.vy *= 0.82
  context.shadowBlur = 0
  frame = requestAnimationFrame(animate)
}

function click(event: PointerEvent) { emitWave(event.clientX, event.clientY, 1.35) }

onMounted(() => {
  resize()
  window.addEventListener('resize', resize, { passive: true })
  window.addEventListener('pointermove', move, { passive: true })
  window.addEventListener('pointerdown', click, { passive: true })
  frame = requestAnimationFrame(animate)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  window.removeEventListener('resize', resize)
  window.removeEventListener('pointermove', move)
  window.removeEventListener('pointerdown', click)
})
</script>

<template><canvas ref="canvas" class="particle-field" aria-hidden="true"></canvas></template>
