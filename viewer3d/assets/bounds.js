export function sceneBounds(data) {
  const root = data && data.bounds ? data.bounds : null;
  const scene = root && root.scene ? root.scene : root;
  if (!scene || !Array.isArray(scene.center) || !Array.isArray(scene.size)) return null;
  const center = scene.center;
  const size = scene.size;
  if (center.length !== 3 || size.length !== 3 || !center.every(Number.isFinite) || !size.every(Number.isFinite)) {
    return null;
  }
  const min = Array.isArray(scene.min) && scene.min.length === 3
    ? scene.min
    : center.map((value, axis) => value - size[axis] / 2);
  const max = Array.isArray(scene.max) && scene.max.length === 3
    ? scene.max
    : center.map((value, axis) => value + size[axis] / 2);
  return { center, size, min, max };
}
