import { Page } from '@playwright/test'

/**
 * Визуализация кликов в записи: на каждый pointerdown в точке нажатия
 * рисуется контрастное кольцо, расходящееся и гаснущее за ~0.7 с — зритель
 * видит, куда именно нажал сценарий. Вшивается в кадр видео, как и субтитры.
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
        const ring = document.createElement('div')
        Object.assign(ring.style, {
          position: 'fixed',
          left: `${e.clientX}px`,
          top: `${e.clientY}px`,
          width: '20px',
          height: '20px',
          marginLeft: '-10px',
          marginTop: '-10px',
          borderRadius: '50%',
          border: '3px solid #ff5722',
          background: 'rgba(255, 87, 34, 0.35)',
          boxShadow: '0 0 0 1px rgba(255,255,255,0.7)',
          zIndex: '2147483646',
          pointerEvents: 'none',
        } as CSSStyleDeclaration)
        document.documentElement.appendChild(ring)
        ring.animate(
          [
            { transform: 'scale(0.5)', opacity: 1 },
            { transform: 'scale(2.4)', opacity: 0 },
          ],
          { duration: 700, easing: 'ease-out' },
        ).onfinish = () => ring.remove()
      },
      true,
    )
  })
}
