import { Link } from "react-router-dom";
import Box from "@mui/material/Box";
import Drawer from "@mui/material/Drawer";
import Typography from "@mui/material/Typography";
import Divider from "@mui/material/Divider";
import Tooltip from "@mui/material/Tooltip";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import LogoutIcon from "@mui/icons-material/Logout";
import Avatar from "@mui/material/Avatar";
import IconButton from "@mui/material/IconButton";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import PendingIcon from "@mui/icons-material/Pending";
import { signOut } from "aws-amplify/auth";

import { APP_NAME } from "../env";
import { DRAWER_WIDTH } from "../constants";

function AppNavigationDrawer({
  mobileOpen,
  desktopOpen,
  onMobileDrawerToggle,
  onDesktopDrawerToggle,
  onSectionChange,
  userName,
  email,
  theme,
  currentSection,
  sectionsConfig,
  sessionId,
}) {

  // Handle logout
  const handleLogout = async () => {
    try {
      await signOut();
      // Redirect to login or refresh the page
      window.location.reload();
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  const drawer = (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflowY: "auto",
        // Hide scrollbar for WebKit browsers (Chrome, Safari, Edge)
        "&::-webkit-scrollbar": {
          display: "none",
        },
        // Hide scrollbar for Firefox
        scrollbarWidth: "none",
        // Ensure smooth scrolling
        scrollBehavior: "smooth",
      }}
    >
      {/* Header - App Name */}
      <Box
        sx={{
          px: 3,
          pt: 1.6,
          pb: 1.6,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          minHeight: "64px",
          borderBottom: `1px solid ${theme.palette.primary.main}20`
        }}
      >
        <Link
          to="/home"
          onClick={() => onSectionChange("home")}
          style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "10px" }}
        >
          <Box
            component="img"
            src="/images/app-logo.svg"
            alt="App Logo"
            sx={{
              width: 32,
              height: 32,
              transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
              "&:hover": {
                transform: "scale(1.05)"
              }
            }}
          />
          <Typography
            variant="h6"
            sx={{
              fontWeight: 700,
              fontSize: "1.15rem",
              background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text"
            }}
          >
            {APP_NAME}
          </Typography>
        </Link>

        <IconButton
          onClick={onDesktopDrawerToggle}
          size="small"
          sx={{
            display: { xs: "none", sm: "flex" }, // Hide on mobile (xs), show on desktop (sm and up)
            color: theme.palette.text.secondary,
            alignSelf: "flex-start",
            "&:hover": {
              backgroundColor: `${theme.palette.primary.main}15`,
              color: theme.palette.primary.main,
            },
          }}
        >
          <ChevronLeftIcon />
        </IconButton>
      </Box>

      {/* Agent Core Information */}
      <Box
        sx={{
          flex: 1,
          py: 2,
          px: 2,
          overflowY: "auto",
          // Hide scrollbar for WebKit browsers (Chrome, Safari, Edge)
          "&::-webkit-scrollbar": {
            display: "none",
          },
          // Hide scrollbar for Firefox
          scrollbarWidth: "none",
          // Ensure smooth scrolling
          scrollBehavior: "smooth",
        }}
      >
        <Box sx={{ position: "relative", mb: 2 }}>
          {/* Aurora Borealis Effect */}
          <Box
            sx={{
              position: "absolute",
              top: -20,
              left: 0,
              right: 0,
              height: "100px",
              background: `linear-gradient(90deg, 
                transparent 0%, 
                ${theme.palette.primary.main}40 20%, 
                ${theme.palette.secondary.main}40 40%, 
                ${theme.palette.primary.main}50 60%, 
                ${theme.palette.secondary.main}40 80%, 
                transparent 100%)`,
              filter: "blur(25px)",
              opacity: 0.9,
              animation: "aurora 6s ease-in-out infinite",
              pointerEvents: "none",
              "@keyframes aurora": {
                "0%, 100%": {
                  transform: "translateX(-15%) skewX(-8deg)",
                  opacity: 0.7,
                },
                "50%": {
                  transform: "translateX(15%) skewX(8deg)",
                  opacity: 1,
                },
              },
            }}
          />
          
          <Box sx={{ px: 1, display: "flex", alignItems: "center", gap: 1.5, position: "relative" }}>
            <Box
              component="img"
              src="/images/amazon-bedrock-agentcore.png"
              alt="Amazon Bedrock AgentCore"
              sx={{
                width: 32,
                height: 32,
                objectFit: "contain",
              }}
            />
            <Box sx={{ flex: 1 }}>
              <Typography
                variant="h6"
                sx={{
                  fontSize: "0.95rem",
                  fontWeight: 700,
                  color: theme.palette.text.primary,
                  mb: 0.5,
                }}
              >
                Amazon Bedrock AgentCore
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  fontSize: "0.75rem",
                  color: theme.palette.text.secondary,
                  lineHeight: 1.4,
                }}
              >
                Accelerate agents to production with composable services that work with any framework, any model
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Amazon Bedrock AgentCore Features */}
        {[
          { 
            name: "Runtime", 
            image: "/images/runtime.png", 
            description: "Execute agents", 
            checked: true,
            info: {
              "Runtime ID": sectionsConfig?.[currentSection]?.agent?.runtimeArn?.split('/').pop() || "N/A",
              "Endpoint": sectionsConfig?.[currentSection]?.agent?.endpointName || "DEFAULT"
            }
          },
          { 
            name: "Memory", 
            image: "/images/memory.png", 
            description: "Conversation context", 
            checked: true,
            info: {
              "Session ID": sessionId ? `${sessionId}` : "N/A"
            }
          },
          { name: "Gateway", image: "/images/gateway.png", description: "API management", checked: true },
          { name: "Identity", image: "/images/identity.png", description: "Authentication", checked: true },
          { name: "Observability", image: "/images/observability.png", description: "Monitoring & logs", checked: false },
          { name: "Browser", image: "/images/browser.png", description: "Web automation", checked: false },
          { name: "Code Interpreter", image: "/images/code-interpreter.png", description: "Execute code", checked: false },
        ].map((feature, index) => (
          <Box
            key={index}
            sx={{
              mb: 1.5,
              p: 1.5,
              borderRadius: "12px",
              background: "rgba(26, 31, 46, 0.3)",
              backdropFilter: "blur(8px)",
              border: "1px solid rgba(255, 255, 255, 0.03)",
              transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
              cursor: feature.checked ? "pointer" : "default",
              opacity: feature.checked ? 1 : 0.4,
              "&:hover": feature.checked ? {
                background: `linear-gradient(135deg, 
                  ${theme.palette.primary.main}12 0%, 
                  ${theme.palette.secondary.main}08 100%)`,
                border: `1px solid ${theme.palette.primary.main}25`,
                transform: "scale(1.02)",
              } : {},
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
              <Box
                component="img"
                src={feature.image}
                alt={feature.name}
                sx={{
                  width: 32,
                  height: 32,
                  objectFit: "contain",
                  filter: "brightness(1.1)",
                }}
              />
              <Box sx={{ flex: 1 }}>
                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <Typography
                    variant="body2"
                    sx={{
                      fontSize: "0.875rem",
                      fontWeight: 600,
                      color: theme.palette.text.primary,
                      mb: 0.25,
                    }}
                  >
                    {feature.name}
                  </Typography>
                  {feature.checked ? (
                    <CheckCircleIcon
                      sx={{
                        fontSize: "1rem",
                        color: theme.palette.primary.main,
                      }}
                    />
                  ) : (
                    <PendingIcon
                      sx={{
                        fontSize: "1rem",
                        color: theme.palette.text.secondary,
                        opacity: 0.5,
                      }}
                    />
                  )}
                </Box>
                <Typography
                  variant="caption"
                  sx={{
                    fontSize: "0.7rem",
                    color: theme.palette.text.secondary,
                    lineHeight: 1.2,
                  }}
                >
                  {feature.description}
                </Typography>
                {feature.info && Object.keys(feature.info).length > 0 && (
                  <Box sx={{ mt: 0.5 }}>
                    {Object.entries(feature.info).map(([key, value]) => (
                      <Typography
                        key={key}
                        variant="caption"
                        sx={{
                          fontSize: "0.65rem",
                          color: theme.palette.primary.main,
                          display: "block",
                          lineHeight: 1.3,
                          opacity: 0.8,
                        }}
                      >
                        {key}: {value}
                      </Typography>
                    ))}
                  </Box>
                )}
              </Box>
            </Box>
          </Box>
        ))}
      </Box>


      {/* Powered By AWS */}
      <Box
        component="a"
        href="https://aws.amazon.com/bedrock/agentcore/"
        target="_blank"
        rel="noopener noreferrer"
        sx={{
          px: 3,
          py: 2,
          pb: 1,
          textAlign: "center",
          textDecoration: "none",
          display: "block",
          background: `linear-gradient(135deg, 
            ${theme.palette.primary.main}08 0%, 
            ${theme.palette.secondary.main}05 100%)`,
          borderTop: `1px solid ${theme.palette.primary.main}10`,
          borderBottom: `1px solid ${theme.palette.primary.main}10`,
          transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
          cursor: "pointer",
          "&:hover": {
            background: `linear-gradient(135deg, 
              ${theme.palette.primary.main}15 0%, 
              ${theme.palette.secondary.main}10 100%)`,
            transform: "translateY(-1px)",
            boxShadow: `0 4px 20px ${theme.palette.primary.main}20`,
            "& img": {
              opacity: 0.85,
              transform: "scale(1.05)",
              filter: "brightness(1.2) drop-shadow(0 2px 8px rgba(201, 45, 37, 0.3))",
            }
          }
        }}
      >
        <img
          src="/images/Powered-By_logo-horiz_RGB_REV.png"
          alt="Powered By AWS"
          style={{
            width: "55%",
            height: "auto",
            opacity: 0.7,
            transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
            filter: "brightness(1.1)",
            transform: "scale(1)",
          }}
        />
      </Box>

      <Divider sx={{ borderColor: `${theme.palette.primary.main}20` }} />


      {/* User Profile - With Logout Icon */}
      <Box sx={{ px: 3, py: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center" }}>
          <Avatar
            sx={{
              width: 32,
              height: 32,
              mr: 2,
              background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
              color: "white",
              fontSize: "0.875rem",
              fontWeight: 600,
            }}
          >
            {(userName || "U").charAt(0).toUpperCase()}
          </Avatar>
          <Box sx={{ flex: 1 }}>
            <Typography
              variant="body2"
              sx={{
                fontSize: "0.875rem",
                fontWeight: 600,
                color: theme.palette.text.primary,
              }}
            >
              {userName || "Loading..."}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontSize: "0.75rem",
                color: theme.palette.text.secondary,
              }}
            >
              {email || ""}
            </Typography>
          </Box>
          <Tooltip title="Sign Out" placement="top">
            <IconButton
              onClick={handleLogout}
              size="small"
              sx={{
                color: theme.palette.text.secondary,
                "&:hover": {
                  backgroundColor: `${theme.palette.primary.main}15`,
                  color: theme.palette.primary.main,
                },
              }}
            >
              <LogoutIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    </Box>
  );

  return (
    <Box
      component="nav"
      sx={{
        width: { xs: 0, sm: desktopOpen ? DRAWER_WIDTH : 0 },
        flexShrink: { sm: 0 },
        transition: "width 0.3s ease",
      }}
    >
      {/* Mobile Drawer */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onMobileDrawerToggle}
        ModalProps={{
          keepMounted: true,
        }}
        sx={{
          display: { xs: "block", sm: "none" },
          "& .MuiDrawer-paper": {
            boxSizing: "border-box",
            width: DRAWER_WIDTH,
            borderRight: `1px solid ${theme.palette.primary.main}20`,
            background: `linear-gradient(135deg, 
              ${theme.palette.primary.main}15 0%, 
              ${theme.palette.secondary.main}12 100%)`,
          },
        }}
      >
        {drawer}
      </Drawer>

      {/* Desktop Drawer */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: "none", sm: desktopOpen ? "block" : "none" },
          "& .MuiDrawer-paper": {
            boxSizing: "border-box",
            width: DRAWER_WIDTH,
            transition: "transform 0.3s ease",
            borderRight: `1px solid ${theme.palette.primary.main}20`,
            background: `linear-gradient(135deg, 
              ${theme.palette.primary.main}15 0%, 
              ${theme.palette.secondary.main}12 100%)`,
          },
        }}
        open
      >
        {drawer}
      </Drawer>
    </Box>
  );
}

export default AppNavigationDrawer;