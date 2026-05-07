import React, { useEffect, useRef, useState } from "react";
import Webcam from "react-webcam";
import io from "socket.io-client";
import {
  PoseLandmarker,
  FilesetResolver,
  DrawingUtils,
} from "@mediapipe/tasks-vision";

const socket = io(import.meta.env.VITE_BACKEND_URL || "http://localhost:5000");

function App() {
  const webcamRef = useRef(null);
  const canvasRef = useRef(null);
  const landmarkerRef = useRef(null);
  const requestRef = useRef(null);

  const [serverMsg, setServerMsg] = useState("Brak połączenia");
  const lastSendTime = useRef(0);
  const [serverPoints, setServerPoints] = useState(null);

  useEffect(() => {
    socket.on("pose_result", (data) => {
      setServerMsg(data.message);
      if (data.points) {
        setServerPoints(data.points);
      }
    });

    let isRunning = true;

    const initMediaPipe = async () => {
      const vision = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm",
      );

      landmarkerRef.current = await PoseLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task`,
          delegate: "GPU",
        },
        runningMode: "VIDEO",
      });

      if (isRunning) animate();
    };

    const animate = () => {
      if (
        webcamRef.current &&
        webcamRef.current.video &&
        webcamRef.current.video.readyState === 4 &&
        landmarkerRef.current
      ) {
        const video = webcamRef.current.video;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const startTimeMs = performance.now();
        const results = landmarkerRef.current.detectForVideo(
          video,
          startTimeMs,
        );

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (results.landmarks && results.landmarks[0]) {
          const landmarks = results.landmarks[0];
          const drawingUtils = new DrawingUtils(ctx);

          drawingUtils.drawConnectors(
            landmarks,
            PoseLandmarker.POSE_CONNECTIONS,
            { color: "#00FF00", lineWidth: 4 },
          );
          drawingUtils.drawLandmarks(landmarks, {
            color: "#FF0000",
            lineWidth: 2,
          });

          const now = Date.now();
          if (now - lastSendTime.current > 100) {
            socket.emit("pose_data", { landmarks: landmarks });
            lastSendTime.current = now;
          }
        }
      }

      if (isRunning) {
        requestRef.current = requestAnimationFrame(animate);
      }
    };

    initMediaPipe();

    return () => {
      isRunning = false;
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
      socket.off("pose_result");
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4 text-white font-sans">
      <h1 className="text-4xl font-black mb-4 tracking-tighter italic uppercase text-cyan-400">
        Cyber-Trener
      </h1>

      <div className="relative rounded-3xl overflow-hidden border-8 border-slate-800 shadow-[0_0_50px_rgba(34,211,238,0.2)]">
        <Webcam
          ref={webcamRef}
          className="w-full max-w-4xl h-auto block"
          mirrored={true}
          audio={false}
        />

        <canvas
          ref={canvasRef}
          className="absolute top-0 left-0 w-full h-full -scale-x-100"
        />
      </div>
      <div className="text-xl font-bold text-cyan-400">
        Serwer: {serverMsg}
        <span className="block text-sm font-mono text-green-400 mt-2 whitespace-pre-wrap">
          Punkt:{" "}
          {serverPoints ? JSON.stringify(serverPoints, null, 2) : "Czekam..."}
        </span>
      </div>
    </div>
  );
}

export default App;
