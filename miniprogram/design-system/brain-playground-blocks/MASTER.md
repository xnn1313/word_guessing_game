# Brain Playground Blocks — Master Design System

## Product direction

微信益智小游戏集合，面向碎片时间中的大众用户。视觉方向采用已经确认的方案 A「玩具积木」：高辨识度、轻快、有实体游戏块的触感，同时保证棋盘和输入控件优先于装饰。

## Signature

每款游戏是一块可以收集的彩色游戏积木。主页面使用双列等高积木矩阵承载全部游戏，不再混用横向轮播和异形卡片；进入游戏后，相同颜色仅作为该游戏的身份色，游玩区域统一回到高对比底色，避免影响可读性。

## Color tokens

- `background`: `#F1F3FF`
- `surface`: `#FFFFFF`
- `ink`: `#151B3A`
- `text`: `#17204A`
- `muted`: `#646C89`
- `cobalt`: `#3157FF`
- `yellow`: `#FFD84D`
- `coral`: `#FF7F75`
- `aqua`: `#63DDD0`
- `violet`: `#B6A4FF`
- `danger`: `#C63F48`

## Typography

- Display: system Chinese sans, weight 850–900, `43–48rpx`
- Section: system Chinese sans, weight 800–850, `30–34rpx`
- Body: system Chinese sans, weight 400–600, `25–28rpx`
- Data: system sans with tabular figures, weight 800–900

Remote fonts are intentionally avoided so the mini program does not depend on font downloads.

## Shape and depth

- Major cards: `3rpx` dark outline, `28rpx` radius
- Controls: `3rpx` dark outline, `18rpx` radius
- Signature cards: `6–8rpx` hard offset shadow with no blur
- Supporting panels: subtle blue shadow only; do not mix multiple elevation languages in one section

## Layout

- Phone-first, horizontal gutter `32rpx`
- Spacing rhythm: `8 / 12 / 16 / 24 / 32 / 48rpx`
- Main interactive targets at least `88rpx` high or equivalent hit area
- Game boards must fit the viewport width without horizontal scrolling
- The board/input area is the first visual focus on play screens; mode controls collapse into one or two compact rows

## Interaction

- Press feedback: translate `4rpx` in both axes and reduce opacity slightly; never change layout bounds
- State transitions: `140–220ms`, ease-out
- Loading longer than 300ms receives a visible loading panel
- Disabled controls retain labels, reduce opacity, and have no hard shadow
- Color is never the only status indicator; retain text, icons, stars, or borders

## Page families

- Hub: compact blue mission block + two-column equal-height game blocks
- Catalogs: compact progress block + expandable white category blocks
- Play screens: compact title, dark status strip, centered board, controls directly below
- Records: timeline/progress cards, data-first
- Profile: account badge and archive panel, clearly distinct from records

## Avoid

- No gradients, glassmorphism, oversized empty hero regions, or decorative emoji navigation icons
- No single-column oversized game cards on the hub
- No stacked full-width mode bars that push the game board below the fold
- No fixed pixel/rpx game boards wider than their parent
- No arbitrary per-page colors outside semantic tokens and the four game identity colors
