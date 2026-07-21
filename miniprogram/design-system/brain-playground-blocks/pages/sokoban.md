# Sokoban — Page Override

## Subject-specific direction

推箱子游玩区模拟旧仓库的地砖、砖墙、木箱、装卸工与工业控制台，让玩家一眼认出游戏对象。该页允许在全局积木系统之外使用一组仓库材质色，但控制栏、触控尺寸和硬边框仍继承 Master。

## Palette

- warehouse canvas: `#E8E4D9`
- floor tile: `#E7D8B8`
- brick wall: `#596269`
- timber crate: `#B96A34`
- industrial ink: `#332B27`
- control green: `#315E52`
- safety yellow: `#EFB647`

## Rules

- 棋盘永远适应父容器宽度，不使用横向滚动。
- 墙、目标、箱子和玩家同时依靠形状、轮廓和颜色区分。
- 方向键保持至少 `88rpx` 等效触控区域，滑动棋盘作为快捷操作。
- 材质全部使用 CSS 几何图形，不依赖 emoji、远程图片或渐变。
