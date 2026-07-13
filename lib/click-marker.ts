import { Page } from '@playwright/test'

/**
 * Визуализация кликов в записи: на каждый pointerdown в точке нажатия
 * вспыхивает аккуратный «клик-риппл» — небольшая сплошная точка (её h264 не
 * теряет) плюс короткое расходящееся кольцо (даёт заметное движение). Гаснут за
 * ~0.65 с. Заметно, но не крупно (кольцо доходит до ~40px). Вшивается в кадр.
 *
 * Инжектируется через addInitScript, поэтому работает на каждой странице
 * и переживает page.goto без восстановления вручную. Слушатель в capture-фазе:
 * маркер появится, даже если приложение гасит всплытие события.
 */
export async function installClickMarker(page: Page): Promise<void> {
  await page.addInitScript(() => {
    addEventListener(
      'pointerdown',
      (e) => {
        const base: Partial<CSSStyleDeclaration> = {
          position: 'fixed',
          left: `${e.clientX}px`,
          top: `${e.clientY}px`,
          borderRadius: '50%',
          zIndex: '2147483646',
          pointerEvents: 'none',
        }
        // Сплошная точка — точное место клика, читается всегда.
        const dot = document.createElement('div')
        Object.assign(dot.style, base, {
          width: '16px',
          height: '16px',
          marginLeft: '-8px',
          marginTop: '-8px',
          background: 'rgba(255, 87, 34, 0.95)',
          boxShadow: '0 0 0 2px rgba(255,255,255,0.9)',
        } as CSSStyleDeclaration)
        // Расходящееся кольцо — движение, за которое цепляется глаз.
        const ring = document.createElement('div')
        Object.assign(ring.style, base, {
          width: '16px',
          height: '16px',
          marginLeft: '-8px',
          marginTop: '-8px',
          border: '3px solid rgba(255, 87, 34, 0.9)',
        } as CSSStyleDeclaration)
        document.documentElement.append(dot, ring)
        const opts: KeyframeAnimationOptions = { duration: 650, easing: 'ease-out' }
        ring.animate(
          [
            { transform: 'scale(1)', opacity: 0.9 },
            { transform: 'scale(2.6)', opacity: 0 },
          ],
          opts,
        )
        dot.animate(
          [
            { transform: 'scale(0.6)', opacity: 1, offset: 0 },
            { transform: 'scale(1)', opacity: 1, offset: 0.4 },
            { transform: 'scale(1)', opacity: 0, offset: 1 },
          ],
          opts,
        ).onfinish = () => { dot.remove(); ring.remove() }
      },
      true,
    )
  })
}
