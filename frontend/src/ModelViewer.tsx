import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

type Props = { data: ArrayBuffer; label: string };

export default function ModelViewer({ data, label }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    setError(null);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch (cause) {
      console.error("Could not initialize the 3D viewer.", cause);
      setError("3D view unavailable. Please enable WebGL in your browser.");
      return;
    }

    // Transparent canvas: the themed .model-stage background shows through.
    const scene = new THREE.Scene();
    renderer.setClearColor(0x000000, 0);
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 500);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.setAttribute("aria-label", `${label}. Drag to orbit, right-drag to pan, scroll to zoom.`);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.maxPolarAngle = Math.PI / 2.05;

    scene.add(new THREE.HemisphereLight(0xffffff, 0xb9c2b0, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    scene.add(sun, sun.target);

    let model: THREE.Object3D | null = null;
    let disposed = false;

    new GLTFLoader().parse(
      data,
      "",
      (gltf) => {
        if (disposed) return;
        model = gltf.scene;
        model.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.castShadow = child.name !== "Floor";
            child.receiveShadow = true;
          }
        });
        scene.add(model);

        // Frame the whole model and fit the shadow camera to it.
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const radius = Math.max(size.x, size.z) / 2 || 1;
        const sphere = box.getBoundingSphere(new THREE.Sphere());
        const fov = THREE.MathUtils.degToRad(camera.fov) / 2;
        const fitFov = camera.aspect < 1 ? Math.atan(Math.tan(fov) * camera.aspect) : fov;
        // A flat plan never fills its bounding sphere, so frame a bit tighter than the sphere.
        const distance = (sphere.radius / Math.tan(fitFov)) * 0.8;
        controls.target.copy(center);
        camera.position.copy(center).addScaledVector(new THREE.Vector3(0.55, 0.7, 1).normalize(), distance);
        controls.minDistance = radius * 0.3;
        controls.maxDistance = distance * 3;
        controls.update();

        sun.position.set(center.x + radius, radius * 2, center.z + radius * 0.6);
        sun.target.position.copy(center);
        Object.assign(sun.shadow.camera, { left: -radius * 1.5, right: radius * 1.5, top: radius * 1.5, bottom: -radius * 1.5, far: radius * 6 });
        sun.shadow.camera.updateProjectionMatrix();
      },
      (cause) => {
        console.error("Could not read the generated model.", cause);
        if (!disposed) setError("The generated model could not be displayed.");
      },
    );

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
      setError("The 3D connection was lost. Switch views to restart the viewer.");
    };
    renderer.domElement.addEventListener("webglcontextlost", onContextLost);
    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });

    return () => {
      disposed = true;
      renderer.setAnimationLoop(null);
      observer.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("webglcontextlost", onContextLost);
      model?.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose();
          (Array.isArray(child.material) ? child.material : [child.material]).forEach((m: THREE.Material) => m.dispose());
        }
      });
      sun.shadow.map?.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [data, label]);

  return (
    <div className="model-viewer">
      <div className="model-canvas" ref={containerRef} />
      {error && <p className="scene-error" role="alert">{error}</p>}
      <span className="model-hint" aria-hidden="true">Drag to orbit · Right-drag to pan · Scroll to zoom</span>
    </div>
  );
}
