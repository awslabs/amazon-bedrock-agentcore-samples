import { useState, useRef } from "react";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";
import { useTheme } from "@mui/material/styles";

const VideoPlayer = ({
  videoSource, // Single video source object: { src, type, thumbnail }
  width = "100%",
  height = "auto",
  borderRadius = "16px"
}) => {
  const theme = useTheme();
  const [isPlaying, setIsPlaying] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [progress, setProgress] = useState(0);
  const videoRef = useRef(null);

  // Extract video URL and thumbnail
  const videoUrl = videoSource?.src || "";
  const videoType = videoSource?.type || "video/mp4";
  const poster = videoSource?.thumbnail || null;

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const currentProgress = (videoRef.current.currentTime / videoRef.current.duration) * 100;
      setProgress(currentProgress);
    }
  };

  const handleProgressClick = (e) => {
    if (videoRef.current) {
      const progressBar = e.currentTarget;
      const rect = progressBar.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const percentage = clickX / rect.width;
      videoRef.current.currentTime = percentage * videoRef.current.duration;
    }
  };

  const togglePlayPause = () => {
    if (videoRef.current) {
      if (videoRef.current.paused) {
        videoRef.current.play();
        setIsPlaying(true);
        setShowControls(false);
      } else {
        videoRef.current.pause();
        setIsPlaying(false);
        setShowControls(true);
      }
    }
  };

  const handleVideoClick = () => {
    togglePlayPause();
  };

  const handleMouseEnter = () => {
    if (isPlaying) {
      setShowControls(true);
    }
  };

  const handleMouseLeave = () => {
    if (isPlaying) {
      setShowControls(false);
    }
  };

  return (
    <Box
      sx={{
        position: "relative",
        display: "inline-block",
        borderRadius: borderRadius,
        overflow: "hidden",
        cursor: "pointer",
        width: width,
        height: height,
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <video
        ref={videoRef}
        onClick={handleVideoClick}
        onTimeUpdate={handleTimeUpdate}
        onPlay={() => {
          setIsPlaying(true);
          setShowControls(false);
        }}
        onPause={() => {
          setIsPlaying(false);
          setShowControls(true);
        }}
        onEnded={() => {
          setIsPlaying(false);
          setShowControls(true);
          setProgress(0);
        }}
        style={{
          width: width,
          height: height,
          borderRadius: borderRadius,
          backgroundColor: "#000",
          display: "block",
          objectFit: "contain", // Maintains aspect ratio
        }}
        poster={poster}
      >
        <source src={videoUrl} type={videoType} />
        Your browser does not support the video tag.
      </video>

      {/* Thin Progress Bar */}
      <Box
        onClick={handleProgressClick}
        sx={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "3px",
          backgroundColor: "rgba(255, 255, 255, 0.3)",
          cursor: "pointer",
          zIndex: 2,
          transition: "height 0.2s ease",
          "&:hover": {
            height: "5px",
          },
        }}
      >
        <Box
          sx={{
            height: "100%",
            width: `${progress}%`,
            backgroundColor: theme.palette.secondary.main,
            transition: "width 0.1s linear",
            boxShadow: `0 0 8px ${theme.palette.secondary.main}99`,
          }}
        />
      </Box>

      {/* Centered Play/Pause Button */}
      {showControls && (
        <Box
          sx={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            transition: "opacity 0.3s ease",
            zIndex: 1,
          }}
        >
          <IconButton
            onClick={togglePlayPause}
            sx={{
              backgroundColor: "rgba(0, 0, 0, 0.2)",
              color: "white",
              width: "clamp(40px, 20%, 100px)",
              height: "clamp(40px, 20%, 100px)",
              "&:hover": {
                backgroundColor: "rgba(0, 0, 0, 0.4)",
                transform: "scale(1.1)",
              },
              transition: "all 0.3s ease",
            }}
          >
            {isPlaying ? (
              <PauseIcon sx={{ fontSize: "clamp(20px, 10%, 50px)" }} />
            ) : (
              <PlayArrowIcon sx={{ fontSize: "clamp(20px, 10%, 50px)" }} />
            )}
          </IconButton>
        </Box>
      )}
    </Box>
  );
};

export default VideoPlayer;