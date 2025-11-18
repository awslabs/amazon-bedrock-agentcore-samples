import { Box, Typography, Grow, GlobalStyles, Button } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useState, useEffect } from "react";

const WelcomeSection = ({ image, title, description, height, onQuestionClick, sampleQuestions = [] }) => {
  const theme = useTheme();
  const [showContent, setShowContent] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowContent(true);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  return (
    <>
      <GlobalStyles
        styles={{
          "@keyframes logoFloat": {
            "0%, 100%": {
              transform: "translateY(0px) scale(1) rotate(0deg)",
            },
            "25%": {
              transform: "translateY(-20px) scale(1.1) rotate(2deg)",
            },
            "50%": {
              transform: "translateY(-25px) scale(1.15) rotate(0deg)",
            },
            "75%": {
              transform: "translateY(-20px) scale(1.1) rotate(-2deg)",
            },
          },
          "@keyframes logoGlow": {
            "0%, 100%": {
              filter: `drop-shadow(0 10px 40px rgba(0,0,0,0.3)) drop-shadow(0 0 30px ${theme.palette.primary.main}60) drop-shadow(0 0 60px ${theme.palette.secondary.main}40)`,
            },
            "50%": {
              filter: `drop-shadow(0 20px 60px rgba(0,0,0,0.4)) drop-shadow(0 0 80px ${theme.palette.primary.main}90) drop-shadow(0 0 120px ${theme.palette.secondary.main}70)`,
            },
          },
        }}
      />
      <Box
        sx={{
          height: height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          px: 3,
          py: 6,
        }}
      >
        <Box
          sx={{
            maxWidth: "md",
            mx: "auto",
          }}
        >
          {/* Animated Image */}
          <Grow in={showContent} timeout={1000}>
            <Box
              sx={{
                mb: 4,
                display: "flex",
                justifyContent: "center",
              }}
            >
              <img
                src={image}
                alt={title}
                style={{
                  height: 128,
                  width: "auto",
                  animation: "logoFloat 2.5s ease-in-out infinite, logoGlow 2s ease-in-out infinite alternate",
                  transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
                }}
              />
            </Box>
          </Grow>

          {/* Title with gradient and glow effect */}
          <Grow in={showContent} timeout={1200}>
            <Typography
              variant="h4"
              sx={{
                mb: 2,
                fontWeight: 700,
                fontSize: { xs: "2rem", sm: "2.5rem", md: "2.75rem" },
                background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
                letterSpacing: "-0.02em",
                position: "relative",
                "&::after": {
                  content: `"${title}"`,
                  position: "absolute",
                  bottom: "-8px",
                  left: "50%",
                  transform: "translateX(-50%)",
                  width: "auto",
                  height: "2px",
                  background: `linear-gradient(90deg, ${theme.palette.primary.main}40 0%, ${theme.palette.secondary.main}40 100%)`,
                  borderRadius: "1px",
                  color: "transparent",
                  fontSize: "inherit",
                  fontWeight: "inherit",
                  letterSpacing: "inherit",
                  whiteSpace: "nowrap",
                },
              }}
            >
              {title}
            </Typography>
          </Grow>

          {/* Subtitle with impact message */}
          <Grow in={showContent} timeout={1300}>
            <Typography
              variant="h6"
              sx={{
                color: "text.primary",
                fontSize: { xs: "1.1rem", sm: "1.3rem", md: "1.4rem" },
                fontWeight: 300,
                mb: 4,
                background: `linear-gradient(135deg, ${theme.palette.text.primary} 0%, ${theme.palette.text.secondary} 100%)`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              {description}
            </Typography>
          </Grow>

          {/* Starting Questions */}
          <Grow in={showContent} timeout={1600}>
            <Box sx={{ width: "100%", mx: "auto" }}>
              <Typography
                variant="h6"
                sx={{
                  color: "text.primary",
                  fontSize: "1.1rem",
                  fontWeight: 500,
                  mb: 3,
                  textAlign: "center",
                }}
              >
                Try asking:
              </Typography>
              <Box
                sx={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 2,
                  justifyContent: "center",
                }}
              >
                {sampleQuestions.map((item, index) => (
                  <Button
                    key={index}
                    variant="outlined"
                    onClick={() => onQuestionClick && onQuestionClick(item.question)}
                    sx={{
                      flex: { xs: "1 1 100%", md: "1 1 calc(50% - 8px)" },
                      minWidth: 0,
                      textAlign: "center",
                      justifyContent: "center",
                      textTransform: "none",
                      fontSize: "1rem",
                      fontWeight: 400,
                      py: 2.5,
                      px: 3,
                      borderRadius: "12px",
                      background: "rgba(26, 31, 46, 0.3)",
                      backdropFilter: "blur(8px)",
                      border: `2px solid ${item.color}10`,
                      color: item.color,
                      transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                      cursor: "pointer",
                      "&:hover": {
                        background: `linear-gradient(135deg, ${item.color}24 0%, ${item.color}06 100%)`,
                        border: `2px solid ${item.color}24`,
                        transform: "scale(1.02)",
                        color: item.color,
                      },
                    }}
                  >
                    {item.question}
                  </Button>
                ))}
              </Box>
            </Box>
          </Grow>
        </Box>
      </Box>
    </>
  );
};

export default WelcomeSection;
