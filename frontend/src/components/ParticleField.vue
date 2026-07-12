<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

interface Point { x: number; y: number; ox: number; oy: number; vx: number; vy: number; size: number; alpha: number }
interface Wave { x: number; y: number; radius: number; strength: number; life: number }

const canvas = ref<HTMLCanvasElement>()
const points: Point[] = []
const waves: Wave[] = []
const pointer = { x: -1000, y: -1000, px: -1000, py: -1000, vx: 0, vy: 0 }
let context: CanvasRenderingContext2D | null = null
let frame = 0
let width = 0
let height = 0
let lastWaveAt = 0

function buildPointCloud() {
  const source = document.createElement('canvas')
  source.width = 560
  source.height = 620
  const sourceContext = source.getContext('2d')!
  sourceContext.clearRect(0, 0, source.width, source.height)
  sourceContext.fillStyle = '#fff'
  sourceContext.strokeStyle = '#fff'
  sourceContext.textAlign = 'center'
  sourceContext.textBaseline = 'middle'
  sourceContext.lineWidth = 3
  sourceContext.beginPath()
  sourceContext.moveTo(280, 28)
  sourceContext.lineTo(500, 440)
  sourceContext.lineTo(60, 440)
  sourceContext.closePath()
  sourceContext.stroke()
  sourceContext.beginPath()
  sourceContext.arc(280, 270, 150, 0, Math.PI * 2)
  sourceContext.stroke()
  sourceContext.font = '260px "STSong", "SimSun", serif'
  sourceContext.fillText('契', 280, 268)
  sourceContext.fillRect(74, 470, 412, 3)
  sourceContext.font = '700 46px Georgia, serif'
  sourceContext.fillText('HENGQI', 280, 520)
  sourceContext.font = '16px Arial, sans-serif'
  sourceContext.fillText('CONTRACT INTELLIGENCE', 280, 566)

  const pixels = sourceContext.getImageData(0, 0, source.width, source.height).data
  const scale = Math.min(width / 1260, height / 960, 0.9)
  const centerX = width >= 1100 ? width * 0.55 : width * 0.5
  const offsetX = centerX - (source.width * scale) / 2
  const offsetY = height / 2 - (source.height * scale) / 2 + 20
  points.length = 0
  for (let y = 0; y < source.height; y += 5) {
    for (let x = 0; x < source.width; x += 5) {
      if (pixels[(y * source.width + x) * 4 + 3] < 90) continue
      const ox = offsetX + x * scale
      const oy = offsetY + y * scale
      points.push({ x: ox, y: oy, ox, oy, vx: 0, vy: 0, size: Math.max(0.65, scale * 1.15), alpha: 0.42 + Math.random() * 0.42 })
    }
  }
}

function resize() {
  if (!canvas.value) return
  const ratio = Math.min(window.devicePixelRatio || 1, 1.6)
  width = window.innerWidth
  height = window.innerHeight
  canvas.value.width = Math.floor(width * ratio)
  canvas.value.height = Math.floor(height * ratio)
  canvas.value.style.width = `${width}px`
  canvas.value.style.height = `${height}px`
  context = canvas.value.getContext('2d')
  context?.setTransform(ratio, 0, 0, ratio, 0, 0)
  buildPointCloud()
}

function emitWave(x: number, y: number, strength = 1) {
  waves.push({ x, y, radius: 8, strength, life: 0 })
  if (waves.length > 5) waves.shift()
}

function move(event: PointerEvent) {
  pointer.px = pointer.x
  pointer.py = pointer.y
  pointer.x = event.clientX
  pointer.y = event.clientY
  pointer.vx = pointer.px < 0 ? 0 : pointer.x - pointer.px
  pointer.vy = pointer.py < 0 ? 0 : pointer.y - pointer.py
  const now = performance.now()
  if (now - lastWaveAt > 145 && Math.hypot(pointer.vx, pointer.vy) > 3) {
    emitWave(pointer.x, pointer.y, 0.7)
    lastWaveAt = now
  }
}

function animate() {
  if (!context) return
  context.clearRect(0, 0, width, height)
  context.fillStyle = '#CBD5E1'
  context.shadowColor = 'rgba(37,99,235,.18)'
  context.shadowBlur = 3
  for (const point of points) {
    const dx = point.x - pointer.x
    const dy = point.y - pointer.y
    const distance = Math.hypot(dx, dy)
    if (distance < 118 && distance > 0) {
      const force = (118 - distance) / 118
      point.vx += (dx / distance) * force * 1.15 + pointer.vx * force * 0.025
      point.vy += (dy / distance) * force * 1.15 + pointer.vy * force * 0.025
    }
    for (const wave of waves) {
      const waveDistance = Math.hypot(point.x - wave.x, point.y - wave.y)
      const edgeDistance = Math.abs(waveDistance - wave.radius)
      if (edgeDistance < 24 && waveDistance > 0) {
        const waveForce = (1 - edgeDistance / 24) * wave.strength
        point.vx += ((point.x - wave.x) / waveDistance) * waveForce * 0.9
        point.vy += ((point.y - wave.y) / waveDistance) * waveForce * 0.9
      }
    }
    point.vx += (point.ox - point.x) * 0.032
    point.vy += (point.oy - point.y) * 0.032
    point.vx *= 0.88
    point.vy *= 0.88
    point.x += point.vx
    point.y += point.vy
    context.globalAlpha = point.alpha
    context.beginPath()
    context.arc(point.x, point.y, point.size, 0, Math.PI * 2)
    context.fill()
  }
  context.globalAlpha = 1
  context.shadowBlur = 0
  for (let index = waves.length - 1; index >= 0; index -= 1) {
    const wave = waves[index]
    wave.radius += 5.8
    wave.strength *= 0.982
    wave.life += 1
    if (wave.life > 72 || wave.radius > Math.max(width, height)) waves.splice(index, 1)
  }
  pointer.vx *= 0.78
  pointer.vy *= 0.78
  frame = requestAnimationFrame(animate)
}

function click(event: PointerEvent) { emitWave(event.clientX, event.clientY, 1.65) }

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
