import type { Directive } from 'vue'

type GlowElement = HTMLElement & {
  __floatingGlowMove__?: (event: PointerEvent) => void
}

function updatePointerPosition(element: GlowElement, event: PointerEvent) {
  const bounds = element.getBoundingClientRect()
  element.style.setProperty('--mouse-x', `${event.clientX - bounds.left}px`)
  element.style.setProperty('--mouse-y', `${event.clientY - bounds.top}px`)
}

export const floatingGlow: Directive<GlowElement> = {
  mounted(element) {
    const handlePointerMove = (event: PointerEvent) => updatePointerPosition(element, event)
    element.__floatingGlowMove__ = handlePointerMove
    element.addEventListener('pointermove', handlePointerMove, { passive: true })
  },
  beforeUnmount(element) {
    if (element.__floatingGlowMove__) {
      element.removeEventListener('pointermove', element.__floatingGlowMove__)
      delete element.__floatingGlowMove__
    }
  },
}
