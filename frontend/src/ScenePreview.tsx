import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export default function ScenePreview() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

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
    const grid = new THREE.GridHelper(16, 32, 0xa5afa0, 0xd2d8cd);
    grid.position.y = -0.15;
    scene.add(grid);

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
      grid.geometry.dispose();
      if (Array.isArray(grid.material)) grid.material.forEach((material) => material.dispose());
      else grid.material.dispose();
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
