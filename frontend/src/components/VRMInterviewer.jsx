import { useEffect, useRef, useState } from 'react';

const DEFAULT_MODEL_URL = '/models/interviewer.vrm';

function FallbackInterviewer() {
  return (
    <div className="virtual-interviewer-video" aria-hidden="true">
      <div className="interviewer-office-depth">
        <span />
        <span />
        <span />
      </div>
      <div className="interviewer-silhouette">
        <div className="interviewer-silhouette-head" />
        <div className="interviewer-silhouette-body" />
      </div>
      <div className="interviewer-speaking-bars">
        <span />
        <span />
        <span />
        <span />
      </div>
      <div className="interviewer-video-name">AI 面试官</div>
    </div>
  );
}

function frameVrmScene(vrm, scene, THREE, VRMUtils) {
  VRMUtils.rotateVRM0(vrm);
  vrm.scene.traverse(object => {
    object.frustumCulled = false;
  });

  const box = new THREE.Box3().setFromObject(vrm.scene);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const height = size.y || 1.8;
  const scale = 1.78 / height;

  vrm.scene.position.x -= center.x;
  vrm.scene.position.z -= center.z;
  vrm.scene.scale.setScalar(scale);

  const scaledBox = new THREE.Box3().setFromObject(vrm.scene);
  vrm.scene.position.y += -scaledBox.min.y - 1.02;

  scene.add(vrm.scene);
}

function setExpression(vrm, name, value) {
  const manager = vrm?.expressionManager;
  if (!manager?.getExpression(name)) return;
  manager.setValue(name, value);
}

function rememberBoneRotation(vrm, boneName, restRotations) {
  const bone = vrm.humanoid?.getNormalizedBoneNode(boneName);
  if (bone) restRotations[boneName] = bone.rotation.clone();
}

function resetBoneRotation(vrm, boneName, restRotations) {
  const bone = vrm.humanoid?.getNormalizedBoneNode(boneName);
  const restRotation = restRotations[boneName];
  if (!bone || !restRotation) return null;
  bone.rotation.copy(restRotation);
  return bone;
}

function applyNaturalArmPose(vrm, boneNames, restRotations, elapsed, mode) {
  const isSpeaking = mode === 'speaking';
  const isListening = mode === 'listening';
  const isThinking = mode === 'thinking';
  const breathe = Math.sin(elapsed * 1.25) * 0.012;
  const speakGesture = isSpeaking ? Math.sin(elapsed * 3.2) * 0.026 : 0;
  const listenMotion = isListening ? Math.sin(elapsed * 1.7) * 0.014 : 0;
  const thinkMotion = isThinking ? -0.012 : 0;
  const motion = breathe + speakGesture + listenMotion + thinkMotion;

  const leftShoulder = resetBoneRotation(vrm, boneNames.LeftShoulder, restRotations);
  const rightShoulder = resetBoneRotation(vrm, boneNames.RightShoulder, restRotations);
  const leftUpperArm = resetBoneRotation(vrm, boneNames.LeftUpperArm, restRotations);
  const rightUpperArm = resetBoneRotation(vrm, boneNames.RightUpperArm, restRotations);
  const leftLowerArm = resetBoneRotation(vrm, boneNames.LeftLowerArm, restRotations);
  const rightLowerArm = resetBoneRotation(vrm, boneNames.RightLowerArm, restRotations);
  const leftHand = resetBoneRotation(vrm, boneNames.LeftHand, restRotations);
  const rightHand = resetBoneRotation(vrm, boneNames.RightHand, restRotations);

  if (leftShoulder) leftShoulder.rotation.z += 0.06 + motion * 0.25;
  if (rightShoulder) rightShoulder.rotation.z -= 0.06 + motion * 0.25;

  if (leftUpperArm) {
    leftUpperArm.rotation.x -= 0.04;
    leftUpperArm.rotation.y += 0.05 + motion * 0.25;
    leftUpperArm.rotation.z += 1.18 + motion;
  }
  if (rightUpperArm) {
    rightUpperArm.rotation.x -= 0.04;
    rightUpperArm.rotation.y -= 0.05 + motion * 0.25;
    rightUpperArm.rotation.z -= 1.18 + motion;
  }
  if (leftLowerArm) {
    leftLowerArm.rotation.x += 0.08;
    leftLowerArm.rotation.z += 0.18 + motion * 0.65;
  }
  if (rightLowerArm) {
    rightLowerArm.rotation.x += 0.08;
    rightLowerArm.rotation.z -= 0.18 + motion * 0.65;
  }
  if (leftHand) leftHand.rotation.z += 0.06 + motion * 0.4;
  if (rightHand) rightHand.rotation.z -= 0.06 + motion * 0.4;
}

export default function VRMInterviewer({ state, modelUrl = DEFAULT_MODEL_URL }) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const stateRef = useRef(state);
  const [loadState, setLoadState] = useState('loading');

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    let disposed = false;
    let cleanupRenderer = () => {};
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return undefined;
    setLoadState('loading');

    const init = async () => {
      const [THREE, loaderModule, vrmModule] = await Promise.all([
        import('three'),
        import('three/examples/jsm/loaders/GLTFLoader.js'),
        import('@pixiv/three-vrm'),
      ]);
      if (disposed) return;

      const { GLTFLoader } = loaderModule;
      const { VRMHumanBoneName, VRMLoaderPlugin, VRMUtils } = vrmModule;
      let animationFrameId = 0;
      let lastRenderAt = 0;
      let resizeObserver;

      const renderer = new THREE.WebGLRenderer({
        canvas,
        alpha: true,
        antialias: true,
        powerPreference: 'high-performance',
      });
      renderer.setClearColor(0x000000, 0);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
      renderer.outputColorSpace = THREE.SRGBColorSpace;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 20);
      camera.position.set(0, 0.5, 2.85);
      camera.lookAt(0, 0.42, 0);

      const keyLight = new THREE.DirectionalLight(0xffffff, 2.3);
      keyLight.position.set(1.8, 2.4, 2.6);
      scene.add(keyLight);
      scene.add(new THREE.AmbientLight(0xffffff, 1.7));

      const vrmRef = { current: null };
      const restRotations = {};

      const resize = () => {
        const rect = container.getBoundingClientRect();
        const width = Math.max(1, Math.floor(rect.width));
        const height = Math.max(1, Math.floor(rect.height));
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
      };

      resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(container);
      resize();

      cleanupRenderer = () => {
        window.cancelAnimationFrame(animationFrameId);
        resizeObserver?.disconnect();
        if (vrmRef.current) VRMUtils.deepDispose(vrmRef.current.scene);
        renderer.dispose();
      };

      const loader = new GLTFLoader();
      loader.register(parser => new VRMLoaderPlugin(parser));
      loader.load(
        modelUrl,
        gltf => {
          if (disposed) return;
          const vrm = gltf.userData.vrm;
          if (!vrm) {
            setLoadState('fallback');
            return;
          }

          frameVrmScene(vrm, scene, THREE, VRMUtils);
          vrmRef.current = vrm;

          [
            VRMHumanBoneName.Head,
            VRMHumanBoneName.Neck,
            VRMHumanBoneName.Chest,
            VRMHumanBoneName.LeftShoulder,
            VRMHumanBoneName.RightShoulder,
            VRMHumanBoneName.LeftUpperArm,
            VRMHumanBoneName.RightUpperArm,
            VRMHumanBoneName.LeftLowerArm,
            VRMHumanBoneName.RightLowerArm,
            VRMHumanBoneName.LeftHand,
            VRMHumanBoneName.RightHand,
          ].forEach(name => rememberBoneRotation(vrm, name, restRotations));

          setLoadState('ready');
        },
        undefined,
        () => {
          if (!disposed) setLoadState('fallback');
        },
      );

      const clock = new THREE.Clock();
      const render = now => {
        if (disposed) return;
        animationFrameId = window.requestAnimationFrame(render);
        if (document.hidden || now - lastRenderAt < 1000 / 30) return;
        lastRenderAt = now;

        const delta = Math.min(clock.getDelta(), 0.033);
        const elapsed = clock.elapsedTime;
        const vrm = vrmRef.current;
        const mode = stateRef.current?.mode;
        const isSpeaking = mode === 'speaking';
        const isListening = mode === 'listening';
        const isThinking = mode === 'thinking';

        if (vrm) {
          const mouth = isSpeaking ? 0.16 + Math.abs(Math.sin(elapsed * 16)) * 0.72 : 0;
          const blinkPhase = elapsed % 4.6;
          const blink = blinkPhase > 4.42 ? Math.sin((blinkPhase - 4.42) / 0.18 * Math.PI) : 0;

          setExpression(vrm, 'aa', mouth);
          setExpression(vrm, 'ih', mouth * 0.24);
          setExpression(vrm, 'ou', mouth * 0.16);
          setExpression(vrm, 'blink', Math.max(0, blink));

          const head = vrm.humanoid?.getNormalizedBoneNode(VRMHumanBoneName.Head);
          const neck = vrm.humanoid?.getNormalizedBoneNode(VRMHumanBoneName.Neck);
          const chest = vrm.humanoid?.getNormalizedBoneNode(VRMHumanBoneName.Chest);
          const nod = isListening ? Math.sin(elapsed * 2.1) * 0.035 : 0;
          const thinkTilt = isThinking ? 0.055 : 0;
          const speakMotion = isSpeaking ? Math.sin(elapsed * 7) * 0.018 : 0;

          if (head && restRotations[VRMHumanBoneName.Head]) {
            head.rotation.copy(restRotations[VRMHumanBoneName.Head]);
            head.rotation.x += nod + speakMotion + thinkTilt;
            head.rotation.y += Math.sin(elapsed * 0.75) * 0.035;
          }
          if (neck && restRotations[VRMHumanBoneName.Neck]) {
            neck.rotation.copy(restRotations[VRMHumanBoneName.Neck]);
            neck.rotation.x += nod * 0.45 + thinkTilt * 0.5;
          }
          if (chest && restRotations[VRMHumanBoneName.Chest]) {
            chest.rotation.copy(restRotations[VRMHumanBoneName.Chest]);
            chest.rotation.x += Math.sin(elapsed * 1.3) * 0.01;
          }
          applyNaturalArmPose(vrm, VRMHumanBoneName, restRotations, elapsed, mode);

          vrm.update(delta);
        }

        renderer.render(scene, camera);
      };
      animationFrameId = window.requestAnimationFrame(render);
    };

    init().catch(() => {
      if (!disposed) setLoadState('fallback');
    });

    return () => {
      disposed = true;
      cleanupRenderer();
    };
  }, [modelUrl]);

  return (
    <div ref={containerRef} className={`vrm-interviewer ${loadState === 'ready' ? 'is-ready' : ''}`}>
      {loadState === 'fallback' && <FallbackInterviewer />}
      {loadState === 'loading' && (
        <div className="vrm-loading-panel">
          <span />
          <strong>载入面试官</strong>
        </div>
      )}
      <canvas ref={canvasRef} className="vrm-interviewer-canvas" aria-label="3D AI 面试官" />
    </div>
  );
}
