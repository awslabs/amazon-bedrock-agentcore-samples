import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import { keyframes } from "@mui/system";

const elasticPulse = keyframes`
  0% { 
    transform: scale(1);
    opacity: 0.7;
  }
  25% { 
    transform: scale(1.4);
    opacity: 1;
  }
  50% { 
    transform: scale(0.8);
    opacity: 0.8;
  }
  75% { 
    transform: scale(1.2);
    opacity: 0.9;
  }
  100% { 
    transform: scale(1);
    opacity: 0.7;
  }
`;

const LoadingIndicator = ({
  loading = true,
  message = "Answering...",
}) => {
  return (
    <Box
      sx={(theme) => ({
        position: "relative",
        p: 1,
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        maxWidth: "70%",
        color: theme.palette.text.primary,
        transition: theme.transitions.create(["background-color"], {
          duration: theme.transitions.duration.short,
        }),
      })}
    >
      {/* Animated typing dots */}
      <Box sx={{ display: "flex", gap: 0.6, alignItems: "center", mr: 1 }}>
        {[0, 1, 2].map((index) => (
          <Box
            key={index}
            sx={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              backgroundColor: "#F4D455",
              animation: `${elasticPulse} 2s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite`,
              animationDelay: `${index * 0.3}s`,
              boxShadow: `0 0 8px rgba(244, 212, 85, 0.4)`,
            }}
          />
        ))}
      </Box>

      {/* Message text */}
      <Typography
        sx={{
          fontWeight: 400,
        }}
      >
        {message}
      </Typography>
    </Box>
  );
};

export default LoadingIndicator;