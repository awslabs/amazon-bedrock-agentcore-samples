import { Box, Typography, Stack, CircularProgress, Fade, Grow } from "@mui/material";
import { alpha } from "@mui/material/styles";
import ControlCameraIcon from '@mui/icons-material/ControlCamera';
//import { SUB_AGENTS } from "../env";

const ToolBox = ({ item, onClick, isLoading = false }) => {
  //const isClickable = SUB_AGENTS.includes(item.name);

  const agentColors = {
    mux_agent: "#e91e63", // pink
    hydrolix_agent: "#4caf50", // green
    default: "#fb8c00" // orange
  };

  const agentColor = agentColors[item.name] || agentColors.default;
  const animationName = `borderPulse-${item.name.replace('_', '-')}`;

  return (
    <Box
      //onClick={isClickable ? onClick : undefined}
      sx={{
        p: 1.5,
        borderRadius: 3,
        overflow: "hidden",
        background: alpha("#ffffff", 0.05),
        border: "1px solid rgba(255, 255, 255, 0.1)",
        borderLeft: `4px solid ${agentColor}`,
        mb: 1.5,
        //cursor: isClickable ? "pointer" : "default",
        position: "relative",
        transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
        ...(isLoading && {
          animation: `${animationName}-loading 1.5s ease-in-out infinite`,
          [`@keyframes ${animationName}-loading`]: {
            "0%, 100%": {
              background: alpha(agentColor, 0.05),
              border: `1px solid ${alpha(agentColor, 0.2)}`,
              borderLeft: `4px solid ${agentColor}`,
              boxShadow: `0 0 0 1px ${alpha(agentColor, 0.2)}, 0 0 10px ${alpha(agentColor, 0.25)}`,
              filter: `drop-shadow(0 0 8px ${agentColor}30) drop-shadow(0 0 16px ${agentColor}15)`,
            },
            "50%": {
              background: alpha(agentColor, 0.08),
              border: `1px solid ${alpha(agentColor, 0.4)}`,
              borderLeft: `4px solid ${agentColor}`,
              boxShadow: `0 0 0 1px ${alpha(agentColor, 0.4)}, 0 0 20px ${alpha(agentColor, 0.35)}`,
              filter: `drop-shadow(0 0 15px ${agentColor}40) drop-shadow(0 0 30px ${agentColor}20)`,
            },
          },
        }),
        "&:hover": {
          transform: "translateY(-4px)",
          background: alpha(agentColor, 0.08),
          border: `1px solid ${alpha(agentColor, 0.4)}`,
          borderLeft: `4px solid ${agentColor}`,
          boxShadow: `0 0 0 1px ${alpha(agentColor, 0.4)}, 0 0 20px ${alpha(agentColor, 0.35)}`,
          filter: `drop-shadow(0 0 15px ${agentColor}40) drop-shadow(0 0 30px ${agentColor}20)`,
        },
      }}
    >
      <Stack
        direction="row"
        spacing={2}
        alignItems="center"
        sx={{
          transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        {/* First Column - Icon */}
        <Box
          sx={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            bgcolor: agentColor,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            position: "relative",
          }}
        >
          {isLoading ? (
            <CircularProgress
              size={18}
              sx={{
                color: "white",
                position: "absolute",
              }}
            />
          ) : item.name === "mux_agent" ? (
            <img src="/images/MUX-white.svg" alt="Mux" style={{ width: 18, height: 18 }} />
          ) : item.name === "hydrolix_agent" ? (
            <img src="/images/Hydrolix-white.svg" alt="Hydrolix" style={{ width: 18, height: 18 }} />
          ) : (
            <ControlCameraIcon sx={{ fontSize: 18, color: "white" }} />
          )}
        </Box>

        {/* Second Column - Tool Information */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Fade
            in={true}
            timeout={{ enter: 600, exit: 400 }}
            style={{
              transitionDelay: '100ms'
            }}
          >
            <Box sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              mb: item.inputs &&
                ((typeof item.inputs === "object" && Object.keys(item.inputs).length > 0) ||
                  (typeof item.inputs !== "object" && String(item.inputs).trim() !== "")) ? 1 : 0,
              transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
            }}>
              {item.name === "mux_agent" ? (
                <Fade in={true} timeout={800}>
                  <img
                    src="/images/MUX-white.svg"
                    alt="Mux"
                    style={{
                      height: 20,
                      transition: "opacity 0.3s ease-in-out"
                    }}
                  />
                </Fade>
              ) : item.name === "hydrolix_agent" ? (
                <Fade in={true} timeout={800}>
                  <img
                    src="/images/Hydrolix-white.svg"
                    alt="Hydrolix"
                    style={{
                      height: 20,
                      transition: "opacity 0.3s ease-in-out"
                    }}
                  />
                </Fade>
              ) : (
                <Fade in={true} timeout={800}>
                  <Typography
                    variant="subtitle2"
                    sx={{
                      fontWeight: 600,
                      color: "#e3f2fd",
                      fontSize: "0.875rem",
                      textTransform: "uppercase",
                      transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)"
                    }}
                  >
                    {item.name}
                  </Typography>
                </Fade>
              )}
            </Box>
          </Fade>
          {item.inputs &&
            ((typeof item.inputs === "object" && Object.keys(item.inputs).length > 0) ||
              (typeof item.inputs !== "object" && String(item.inputs).trim() !== "")) && (
              <Grow
                in={true}
                timeout={{ enter: 800, exit: 400 }}
                style={{
                  transformOrigin: "top left",
                  transitionDelay: '200ms'
                }}
              >
                <Box sx={{
                  mt: 1,
                  transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                }}>
                  {typeof item.inputs === "object" ? (
                    Object.entries(item.inputs).map(([key, value], index) => (
                      <Fade
                        key={key}
                        in={true}
                        timeout={{ enter: 600, exit: 300 }}
                        style={{
                          transitionDelay: `${300 + (index * 100)}ms`
                        }}
                      >
                        <Typography
                          variant="body2"
                          sx={{
                            lineHeight: 1.5,
                            color: "#e5e7eb",
                            wordBreak: "break-word",
                            mb: 0.5,
                            "& strong": {
                              color: agentColor,
                              fontWeight: 500,
                            },
                          }}
                        >
                          <strong>{key}:</strong>{" "}
                          {typeof value === "object"
                            ? JSON.stringify(value, null, 2)
                            : String(value)}
                        </Typography>
                      </Fade>
                    ))
                  ) : (
                    <Fade
                      in={true}
                      timeout={{ enter: 600, exit: 300 }}
                      style={{
                        transitionDelay: '300ms'
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          color: "#e5e7eb",
                          lineHeight: 1.5,
                          wordBreak: "break-word",
                        }}
                      >
                        {String(item.inputs)}
                      </Typography>
                    </Fade>
                  )}
                </Box>
              </Grow>
            )}
        </Box>
      </Stack>
    </Box>
  );
};

export default ToolBox;
