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

  const [messages, setMessages] = useState(["Brak połączenia"]);
  const [reps, setReps] = useState("");
  const [phase, setPhase] = useState("");
  const lastSendTime = useRef(0);

  useEffect(() => {
    socket.on("pose_result", (data) => {
      if (data.messages) setMessages(data.messages);
      if (data.reps !== undefined) setReps(data.reps);
      if (data.phase) setPhase(data.phase);
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

        if (
          results.worldLandmarks &&
          results.worldLandmarks[0] &&
          results.landmarks
        ) {
          const worldLandmarks = results.worldLandmarks[0];
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
          if (now - lastSendTime.current > 33) {
            socket.emit("pose_data", {
              landmarks: landmarks,
              world_landmarks: results.worldLandmarks[0],
            });
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

      <div className="flex gap-4 mb-4">
        <div className="bg-gray-800 px-4 py-2 rounded text-white font-mono text-xl border border-gray-700">
          Reps: <span className="font-bold text-blue-400">{reps}</span>
        </div>
        <div className="bg-gray-800 px-4 py-2 rounded text-white font-mono text-xl border border-gray-700">
          Faza: <span className="font-bold text-green-400">{phase}</span>
        </div>
      </div>

      <div className="relative w-full max-w-4xl bg-black border-2 border-gray-700 shadow-lg">
        <Webcam
          ref={webcamRef}
          className="w-full h-auto block opacity-80"
          audio={false}
        />

        <canvas
          ref={canvasRef}
          className="absolute top-0 left-0 w-full h-full"
        />
      </div>

      <div className="w-full max-w-4xl mt-4 flex flex-col gap-2">
        {Array.isArray(messages) && messages.length > 0 ? (
          messages.map((msg, index) => (
            <div
              key={index}
              className="px-4 py-3 text-lg font-bold rounded border bg-slate-800 text-slate-300 border-slate-600"
            >
              {msg}
            </div>
          ))
        ) : (
          <div className="px-4 py-3 text-lg font-bold rounded border bg-slate-800 text-slate-500 border-slate-700">
            Oczekiwanie na dane...
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
