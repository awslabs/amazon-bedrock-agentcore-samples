import { Box, Typography, Stack, CircularProgress } from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import BuildIcon from '@mui/icons-material/Build';
//import { SUB_AGENTS } from "../env";

const ToolBox = ({ item, isLoading = false }) => {
  //const isClickable = SUB_AGENTS.includes(item.name);
  const theme = useTheme();

  // Use the primary color from theme instead of hardcoded colors
  const agentColor = theme.palette.primary.main;
  const animationName = `borderPulse-${item.name.replace('_', '-')}`;

  return (
    <Box
      //onClick={isClickable ? onClick : undefined}
      sx={{
        p: 1.5,
        borderRadius: 3,
        overflow: "hidden",
        background: alpha(theme.palette.primary.main, 0.04),
        border: `1px solid ${alpha(agentColor, 0.3)}`,
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
              boxShadow: `0 0 0 1px ${alpha(agentColor, 0.2)}, 0 0 6px ${alpha(agentColor, 0.15)}`,
              filter: `drop-shadow(0 0 4px ${agentColor}20) drop-shadow(0 0 8px ${agentColor}10)`,
            },
            "50%": {
              background: alpha(agentColor, 0.08),
              border: `1px solid ${alpha(agentColor, 0.4)}`,
              borderLeft: `4px solid ${agentColor}`,
              boxShadow: `0 0 0 1px ${alpha(agentColor, 0.3)}, 0 0 10px ${alpha(agentColor, 0.2)}`,
              filter: `drop-shadow(0 0 6px ${agentColor}25) drop-shadow(0 0 12px ${agentColor}15)`,
            },
          },
        }),
        "&:hover": {
          transform: "translateY(-2px)",
          background: alpha(agentColor, 0.08),
          border: `1px solid ${alpha(agentColor, 0.4)}`,
          borderLeft: `4px solid ${agentColor}`,
          boxShadow: `0 0 0 1px ${alpha(agentColor, 0.3)}, 0 0 8px ${alpha(agentColor, 0.15)}`,
          filter: `drop-shadow(0 0 4px ${agentColor}20) drop-shadow(0 0 8px ${agentColor}10)`,
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
            <BuildIcon sx={{ fontSize: 18, color: "white" }} />
          )}
        </Box>

        {/* Second Column - Tool Information */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            mb: item.inputs &&
              ((typeof item.inputs === "object" && Object.keys(item.inputs).length > 0) ||
                (typeof item.inputs !== "object" && String(item.inputs).trim() !== "")) ? 1 : 0,
          }}>
            {item.name === "mux_agent" ? (
              <img
                src="/images/MUX-white.svg"
                alt="Mux"
                style={{
                  height: 20,
                }}
              />
            ) : item.name === "hydrolix_agent" ? (
              <img
                src="/images/Hydrolix-white.svg"
                alt="Hydrolix"
                style={{
                  height: 20,
                }}
              />
            ) : (
              <Typography
                variant="subtitle2"
                sx={{
                  fontWeight: 600,
                  color: "text.primary",
                  fontSize: "0.875rem",
                  textTransform: "uppercase",
                }}
              >
                {item.name}
              </Typography>
            )}
          </Box>
          {item.inputs &&
            ((typeof item.inputs === "object" && Object.keys(item.inputs).length > 0) ||
              (typeof item.inputs !== "object" && String(item.inputs).trim() !== "")) && (
              <Box sx={{
                mt: 1,
              }}>
                {typeof item.inputs === "object" ? (
                  Object.entries(item.inputs).map(([key, value]) => (
                    <Typography
                      key={key}
                      variant="body2"
                      sx={{
                        lineHeight: 1.5,
                        color: "text.secondary",
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
                  ))
                ) : (
                  <Typography
                    variant="body2"
                    sx={{
                      color: "text.secondary",
                      lineHeight: 1.5,
                      wordBreak: "break-word",
                    }}
                  >
                    {String(item.inputs)}
                  </Typography>
                )}
              </Box>
            )}
        </Box>
      </Stack>
    </Box>
  );
};

export default ToolBox;
