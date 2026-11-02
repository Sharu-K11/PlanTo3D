import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { useTheme, type Theme } from "./theme";

const GRID_COLORS: Record<Theme, [number, number]> = { light: [0xa5afa0, 0xd2d8cd], dark: [0x4d5a50, 0x2c3530] };

function makeGrid(theme: Theme) {
  const grid = new THREE.GridHelper(16, 32, ...GRID_COLORS[theme]);
  grid.position.y = -0.15;
  return grid;
}

function disposeGrid(grid: THREE.GridHelper) {
  grid.geometry.dispose();
  if (Array.isArray(grid.material)) grid.material.forEach((material) => material.dispose());
  else grid.material.dispose();
}

export default function ScenePreview() {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const [error, setError] = useState<string | null>(null);
  const theme = useTheme();

  // Swap only the grid when the theme changes; the rest of the scene stays.
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (gridRef.current) {
      scene.remove(gridRef.current);
      disposeGrid(gridRef.current);
    }
    gridRef.current = makeGrid(theme);
    scene.add(gridRef.current);
  }, [theme]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch (cause) {
      console.error("Could not initialize the Three.js preview.", cause);
      setError("3D preview unavailable. Please enable WebGL in your browser.");
      return;
    }

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(9, 10, 12);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.domElement.setAttribute("aria-label", "Interactive example floor plan. Drag to orbit and scroll to zoom.");
    renderer.domElement.setAttribute("role", "img");
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.minDistance = 8;
    controls.maxDistance = 24;
    controls.maxPolarAngle = Math.PI / 2.2;
    controls.target.set(0, 0.3, 0);

    scene.add(new THREE.AmbientLight(0xffffff, 2));
    const light = new THREE.DirectionalLight(0xffffff, 3);
    light.position.set(5, 10, 6);
    scene.add(light);

    const geometries: THREE.BoxGeometry[] = [];
    const floorMaterial = new THREE.MeshStandardMaterial({ color: 0xc3cbbd, roughness: 0.9 });
    const wallMaterial = new THREE.MeshStandardMaterial({ color: 0xedece0, roughness: 0.8 });
    const accentMaterial = new THREE.MeshStandardMaterial({ color: 0x7d9772, roughness: 0.9 });
    const addBox = (
      size: [number, number, number],
      position: [number, number, number],
      material: THREE.MeshStandardMaterial,
    ) => {
      const geometry = new THREE.BoxGeometry(...size);
      geometries.push(geometry);
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(...position);
      scene.add(mesh);
    };

    addBox([7, 0.25, 5.5], [0, 0, 0], floorMaterial);
    addBox([7, 1.7, 0.16], [0, 0.95, -2.65], wallMaterial);
    addBox([0.16, 1.7, 5.5], [-3.4, 0.95, 0], wallMaterial);
    addBox([0.16, 1.7, 2.6], [1, 0.95, -1.3], wallMaterial);
    addBox([2.4, 1.7, 0.16], [2.2, 0.95, 0], wallMaterial);
    addBox([1.5, 0.5, 0.8], [-1.7, 0.4, -1.7], accentMaterial);
    addBox([1, 0.35, 1.6], [2.2, 0.3, -1.35], accentMaterial);
    addBox([1.1, 0.4, 0.75], [-1, 0.35, 1], wallMaterial);
    sceneRef.current = scene;
    gridRef.current = makeGrid(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
    scene.add(gridRef.current);

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    const onContextLost = (event: Event) => {
      event.preventDefault();
      renderer.setAnimationLoop(null);
      setError("The 3D connection was lost. Reload the page to restart the preview.");
    };
    renderer.domElement.addEventListener("webglcontextlost", onContextLost);
    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });

    return () => {
      renderer.setAnimationLoop(null);
      observer.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("webglcontextlost", onContextLost);
      geometries.forEach((geometry) => geometry.dispose());
      floorMaterial.dispose();
      wallMaterial.dispose();
      accentMaterial.dispose();
      if (gridRef.current) disposeGrid(gridRef.current);
      gridRef.current = null;
      sceneRef.current = null;
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return (
    <div className="scene-wrap">
      <div className="scene" ref={containerRef} />
      {error && <p className="scene-error" role="alert">{error}</p>}
      <span className="scene-caption">ILLUSTRATIVE SCENE / NOT MODEL OUTPUT</span>
    </div>
  );
}
