import { Box, Fade } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { keyframes } from "@mui/system";
import VideoPlayer from "./VideoPlayer";

const MediaAssets = ({ mediaAssets = [] }) => {
  const theme = useTheme();
  
  console.log("📺 MediaAssets received:", mediaAssets);
  
  if (!mediaAssets || mediaAssets.length === 0) {
    console.log("⚠️ No media assets to display");
    return null;
  }

  // Filter responses that have video or image content
  const responsesWithMedia = mediaAssets.filter(response =>
    (response.video && response.video.sources && response.video.sources.length > 0) ||
    (response.image && response.image.src)
  );

  console.log("🎬 Filtered media assets:", responsesWithMedia);

  if (responsesWithMedia.length === 0) {
    console.log("⚠️ No valid video or image content found");
    return null;
  }

  // Convert hex color to rgba
  const hexToRgba = (hex, alpha) => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const primaryColor = theme.palette.primary.main;
  const glowColor12 = hexToRgba(primaryColor, 0.125);
  const glowColor7 = hexToRgba(primaryColor, 0.075);
  const glowColor0 = hexToRgba(primaryColor, 0);

  // Smooth glow fade-in animation
  const glowFadeIn = keyframes`
    0% {
      filter: drop-shadow(0 0 0px ${glowColor0}) drop-shadow(0 0 0px ${glowColor0});
    }
    100% {
      filter: drop-shadow(0 0 8px ${glowColor12}) drop-shadow(0 0 16px ${glowColor7});
    }
  `;

  // Smooth glow fade-out animation
  const glowFadeOut = keyframes`
    0% {
      filter: drop-shadow(0 0 8px ${glowColor12}) drop-shadow(0 0 16px ${glowColor7});
    }
    100% {
      filter: drop-shadow(0 0 0px ${glowColor0}) drop-shadow(0 0 0px ${glowColor0});
    }
  `;

  return (
    <Box sx={{
      display: "flex",
      flexDirection: "column",
      gap: 2,
      alignItems: "flex-start",
      width: "100%",
    }}>
      {responsesWithMedia.map((response, index) => (
        <Fade
          key={index}
          in={true}
          timeout={{ enter: 800, exit: 400 }}
          style={{
            transitionDelay: `${index * 150}ms`
          }}
        >
          <Box sx={{
            width: { xs: "100%", sm: "400px", md: "450px" },
            borderRadius: "16px",
            overflow: "hidden",
            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1)",
            border: "1px solid rgba(255, 255, 255, 0.05)",
            position: "relative",
            filter: "drop-shadow(0 0 0px rgba(104, 198, 78, 0))",
            animation: `${glowFadeOut} 1s ease-in-out forwards`,
            "&:hover": {
              animation: `${glowFadeIn} 1s ease-in-out forwards`,
            },
          }}>
              {/* Render Video Content */}
              {response.video && response.video.sources && response.video.sources.length > 0 && (
                <Box sx={{
                  position: "relative",
                  width: "100%",
                  paddingBottom: "56.25%", // 16:9 aspect ratio (9/16 * 100%)
                  height: 0,
                  overflow: "hidden",
                  borderRadius: "16px",
                  backgroundColor: "#000",
                }}>
                  <Box sx={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: "100%",
                  }}>
                    <VideoPlayer
                      videoSource={response.video.sources[0]}
                      width="100%"
                      height="100%"
                      borderRadius="16px"
                    />
                  </Box>
                </Box>
              )}

              {/* Render Image Content */}
              {response.image && response.image.src && (
                <Box sx={{
                  position: "relative",
                  width: "100%",
                  borderRadius: "16px",
                  overflow: "hidden",
                }}>
                  <img
                    src={response.image.src}
                    alt={response.image.alt || response.image.title || "Security analysis image"}
                    style={{
                      width: "100%",
                      height: "auto",
                      display: "block",
                      borderRadius: "16px",
                      transition: "all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
                      filter: "brightness(1) contrast(1)",
                    }}

                    onError={(e) => {
                      console.error("Error loading image:", response.image.src);
                      e.target.style.display = "none";
                    }}
                  />
                  {/* Optional overlay with title/description */}
                  {(response.image.title || response.image.description) && (
                    <Fade
                      in={true}
                      timeout={{ enter: 800, exit: 400 }}
                      style={{
                        transitionDelay: `${index * 250 + 600}ms`
                      }}
                    >
                      <Box sx={{
                        position: "absolute",
                        bottom: 0,
                        left: 0,
                        right: 0,
                        background: "linear-gradient(transparent, rgba(0,0,0,0.7))",
                        color: "white",
                        p: 2,
                        borderRadius: "0 0 16px 16px",
                        transition: "all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
                      }}>
                        {response.image.title && (
                          <Fade
                            in={true}
                            timeout={{ enter: 600, exit: 300 }}
                            style={{
                              transitionDelay: `${index * 250 + 700}ms`
                            }}
                          >
                            <Box sx={{
                              fontWeight: 600,
                              fontSize: "0.9rem",
                              mb: 0.5,
                              transform: "translateY(0)",
                              transition: "transform 0.3s ease-out",
                            }}>
                              {response.image.title}
                            </Box>
                          </Fade>
                        )}
                        {response.image.description && (
                          <Fade
                            in={true}
                            timeout={{ enter: 600, exit: 300 }}
                            style={{
                              transitionDelay: `${index * 250 + 800}ms`
                            }}
                          >
                            <Box sx={{
                              fontSize: "0.8rem",
                              opacity: 0.9,
                              transform: "translateY(0)",
                              transition: "transform 0.3s ease-out",
                            }}>
                              {response.image.description}
                            </Box>
                          </Fade>
                        )}
                      </Box>
                    </Fade>
                  )}
                </Box>
              )}
            </Box>
        </Fade>
      ))}
    </Box>
  );
};

export default MediaAssets;
