import * as THREE from "three";

type OrbState = "idle" | "listening" | "thinking" | "speaking";

const PARTICLE_COUNT = 2000;
const BASE_RADIUS = 1.5;

const STATE_COLORS: Record<OrbState, THREE.Color> = {
  idle: new THREE.Color(0xD4A843),
  listening: new THREE.Color(0xFF8C00),
  thinking: new THREE.Color(0xFFD700),
  speaking: new THREE.Color(0xE8912D),
};

export class ParticleOrb {
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private renderer: THREE.WebGLRenderer;
  private particles: THREE.Points;
  private geometry: THREE.BufferGeometry;
  private positions: Float32Array;
  private basePositions: Float32Array;
  private velocities: Float32Array;
  private state: OrbState = "idle";
  private targetColor: THREE.Color;
  private currentColor: THREE.Color;
  private audioLevel = 0;
  private time = 0;
  private animId = 0;

  constructor(container: HTMLElement) {
    // Scene
    this.scene = new THREE.Scene();

    // Camera
    this.camera = new THREE.PerspectiveCamera(
      60,
      container.clientWidth / container.clientHeight,
      0.1,
      100
    );
    this.camera.position.z = 4;

    // Renderer
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
    });
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(this.renderer.domElement);

    // Colors
    this.targetColor = STATE_COLORS.idle.clone();
    this.currentColor = STATE_COLORS.idle.clone();

    // Particles
    this.positions = new Float32Array(PARTICLE_COUNT * 3);
    this.basePositions = new Float32Array(PARTICLE_COUNT * 3);
    this.velocities = new Float32Array(PARTICLE_COUNT * 3);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const phi = Math.acos(2 * Math.random() - 1);
      const theta = Math.random() * Math.PI * 2;
      const r = BASE_RADIUS * (0.8 + Math.random() * 0.4);

      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);

      this.positions[i * 3] = x;
      this.positions[i * 3 + 1] = y;
      this.positions[i * 3 + 2] = z;

      this.basePositions[i * 3] = x;
      this.basePositions[i * 3 + 1] = y;
      this.basePositions[i * 3 + 2] = z;

      this.velocities[i * 3] = (Math.random() - 0.5) * 0.01;
      this.velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.01;
      this.velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.01;
    }

    this.geometry = new THREE.BufferGeometry();
    this.geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(this.positions, 3)
    );

    const material = new THREE.PointsMaterial({
      size: 0.025,
      color: this.currentColor,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.particles = new THREE.Points(this.geometry, material);
    this.scene.add(this.particles);

    // Handle resize
    window.addEventListener("resize", () => {
      this.camera.aspect = container.clientWidth / container.clientHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(container.clientWidth, container.clientHeight);
    });

    this.animate();
  }

  setState(state: OrbState): void {
    this.state = state;
    this.targetColor = STATE_COLORS[state].clone();
  }

  setAudioLevel(level: number): void {
    this.audioLevel = Math.max(0, Math.min(1, level));
  }

  private animate = (): void => {
    this.animId = requestAnimationFrame(this.animate);
    this.time += 0.016;

    // Lerp color
    this.currentColor.lerp(this.targetColor, 0.05);
    (this.particles.material as THREE.PointsMaterial).color = this.currentColor;

    // Animation parameters based on state
    let noiseScale: number;
    let breatheSpeed: number;
    let breatheAmplitude: number;
    let rotationSpeed: number;

    switch (this.state) {
      case "listening":
        noiseScale = 0.3 + this.audioLevel * 0.8;
        breatheSpeed = 2.0;
        breatheAmplitude = 0.15 + this.audioLevel * 0.3;
        rotationSpeed = 0.003;
        break;
      case "thinking":
        noiseScale = 0.4;
        breatheSpeed = 4.0;
        breatheAmplitude = 0.1;
        rotationSpeed = 0.01;
        break;
      case "speaking":
        noiseScale = 0.2 + this.audioLevel * 1.0;
        breatheSpeed = 1.5;
        breatheAmplitude = 0.1 + this.audioLevel * 0.5;
        rotationSpeed = 0.005;
        break;
      default: // idle
        noiseScale = 0.1;
        breatheSpeed = 0.8;
        breatheAmplitude = 0.05;
        rotationSpeed = 0.001;
    }

    const breathe = Math.sin(this.time * breatheSpeed) * breatheAmplitude;

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;
      const bx = this.basePositions[i3];
      const by = this.basePositions[i3 + 1];
      const bz = this.basePositions[i3 + 2];

      // Noise displacement
      const nx = Math.sin(bx * 3 + this.time * 1.5) * noiseScale;
      const ny = Math.cos(by * 3 + this.time * 1.3) * noiseScale;
      const nz = Math.sin(bz * 3 + this.time * 1.7) * noiseScale;

      // Apply breathe + noise
      const scale = 1 + breathe;
      this.positions[i3] = bx * scale + nx;
      this.positions[i3 + 1] = by * scale + ny;
      this.positions[i3 + 2] = bz * scale + nz;
    }

    this.geometry.attributes.position.needsUpdate = true;

    // Rotate the whole orb
    this.particles.rotation.y += rotationSpeed;
    this.particles.rotation.x += rotationSpeed * 0.3;

    this.renderer.render(this.scene, this.camera);
  };

  dispose(): void {
    cancelAnimationFrame(this.animId);
    this.geometry.dispose();
    (this.particles.material as THREE.PointsMaterial).dispose();
    this.renderer.dispose();
  }
}
