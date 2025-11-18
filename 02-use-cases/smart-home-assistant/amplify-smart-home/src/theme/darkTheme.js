import { createTheme } from "@mui/material/styles";
import { alpha } from "@mui/material/styles";

const darkTheme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#00D4FF",
    },
    secondary: {
      main: "#A260F6",
    },
    background: {
      default: "#0a0a0f",
      paper: "#12141a",
    },
    surface: {
      main: "#1a1d26",
    },
    text: {
      primary: "#FFFFFF",
      secondary: "#8B9DC3",
    },
    divider: "rgba(0, 212, 255, 0.08)",
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          minHeight: "100vh",
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: () => ({
          background: "#12141a",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
        }),
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: ({ theme }) => ({
          background: "#1a1d26",
          backdropFilter: "blur(12px)",
          borderRight: `1px solid rgba(255, 255, 255, 0.05)`,
        }),
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: () => ({
          background: "rgba(18, 20, 26, 0.98)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
        }),
      },
    },
    MuiChip: {
      styleOverrides: {
        root: ({ theme }) => ({
          background: `linear-gradient(135deg, 
            ${alpha(theme.palette.primary.main, 0.2)} 0%, 
            ${alpha(theme.palette.secondary.main, 0.15)} 100%)`,
          color: "#FFFFFF",
          border: `1px solid ${alpha(theme.palette.primary.main, 0.3)}`,
        }),
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          background: "transparent",
          border: "0px",
          color: "text.secondary",
          fontSize: "1.4rem",
          "&:hover": {
            background: "rgba(255, 255, 255, 0.05)",
          },
        },
      },
    },
    MuiCard: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: () => ({
          // Cross-browser background gradients
          background: [
            // Fallback for very old browsers
            "rgba(18, 20, 26, 0.9)",
            // Modern browsers
            "rgba(18, 20, 26, 0.6)",
          ],

          // Cross-browser backdrop filter support
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)", // Safari
          MozBackdropFilter: "blur(20px)", // Firefox (experimental)
          msBackdropFilter: "blur(20px)", // Edge Legacy

          // Fallback for browsers without backdrop-filter support
          "@supports not (backdrop-filter: blur(20px))": {
            backgroundColor: "rgba(18, 20, 26, 0.95)",
          },

          // Cross-browser border
          border: "1px solid rgba(255, 255, 255, 0.08)",

          // Enhanced box-shadow for better cross-browser support
          boxShadow: [
            // Fallback for older browsers
            "0 8px 24px rgba(0, 0, 0, 0.15)",
            // Modern shadow with multiple layers for depth
            `0 2px 8px rgba(0, 0, 0, 0.08),
             0 8px 24px rgba(0, 0, 0, 0.15),
             0 16px 48px rgba(0, 0, 0, 0.1)`,
          ],

          // Cross-browser border radius
          borderRadius: 16,
          WebkitBorderRadius: 16, // Older Webkit
          MozBorderRadius: 16, // Older Firefox

          // Additional properties for better rendering
          isolation: "isolate", // Creates new stacking context
          willChange: "transform", // Optimizes for animations
          transform: "translateZ(0)", // Forces hardware acceleration

          // Ensure proper positioning context
          position: "relative",

          // Smooth transitions
          transition: "all 0.2s ease-in-out",
          WebkitTransition: "all 0.2s ease-in-out",
          MozTransition: "all 0.2s ease-in-out",

          // Better text rendering
          WebkitFontSmoothing: "antialiased",
          MozOsxFontSmoothing: "grayscale",

          // Prevent selection issues
          WebkitTouchCallout: "none",
          WebkitUserSelect: "none",
          userSelect: "none",

          // Remove outline for accessibility compliance
          outline: "none",
          "&:focus-visible": {
            outline: "2px solid rgba(255, 255, 255, 0.3)",
            outlineOffset: "2px",
          },
        }),
      },
    },
    MuiCardContent: {
      styleOverrides: {
        root: () => ({}),
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: ({ theme }) => ({
          borderRadius: "12px",
          margin: "6px 12px",
          padding: "12px 16px",
          position: "relative",
          overflow: "hidden",
          transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          border: "1px solid transparent",

          // Default state
          background: "transparent",
          color: "#FFFFFF",

          // Hover state
          "&:hover": {
            background: "rgba(255, 255, 255, 0.05)",
            transform: "translateY(-1px)",
          },

          // Selected state
          "&.Mui-selected": {
            background: `linear-gradient(90deg, 
              ${alpha(theme.palette.primary.main, 0.2)} 0%, 
              ${alpha(theme.palette.secondary.main, 0.15)} 100%)`,
            color: "#FFFFFF",
            borderLeft: `3px solid ${theme.palette.primary.main}`,
            paddingLeft: "13px",

            // Selected hover state
            "&:hover": {
              background: `linear-gradient(90deg, 
                ${alpha(theme.palette.primary.main, 0.25)} 0%, 
                ${alpha(theme.palette.secondary.main, 0.2)} 100%)`,
            },

            // Selected text and icon colors
            "& .MuiListItemText-primary": {
              color: "#FFFFFF",
              fontWeight: 600,
            },
            "& .MuiListItemIcon-root": {
              color: "#FFFFFF",
            },
          },

          // Focus state
          "&:focus-visible": {
            outline: `2px solid ${alpha(theme.palette.primary.main, 0.6)}`,
            outlineOffset: "2px",
          },

          // Active state
          "&:active": {
            transform: "translateY(0px)",
            transition: "all 0.1s ease",
          },

          // Disabled state
          "&.Mui-disabled": {
            opacity: 0.4,
            background: "transparent",
            color: "rgba(255, 255, 255, 0.3)",
          },
        }),
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: () => ({
          borderColor: "rgba(255, 255, 255, 0.06)",
        }),
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: () => ({
          backgroundColor: "rgba(18, 20, 26, 0.98)",
          color: "#FFFFFF",
          fontSize: "0.75rem",
          fontWeight: 500,
          padding: "8px 12px",
          borderRadius: "6px",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.5)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          backdropFilter: "blur(10px)",
        }),
        arrow: () => ({
          color: "rgba(18, 20, 26, 0.98)",
          "&:before": {
            border: "1px solid rgba(255, 255, 255, 0.1)",
          },
        }),
      },
    },
  },
});

export default darkTheme;