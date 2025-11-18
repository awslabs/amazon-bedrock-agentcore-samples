import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import MenuIcon from "@mui/icons-material/Menu";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";

import { APP_NAME } from "../env";
import { DRAWER_WIDTH } from "../constants";

function AppHeader({
  desktopOpen,
  onMobileDrawerToggle,
  onDesktopDrawerToggle,
  title,
  icon,
  currentSection,
}) {
  const theme = useTheme();
  const isSmallScreen = useMediaQuery(theme.breakpoints.down("md"));

  return (
    <AppBar
      position="fixed"
      elevation={0}
      sx={{
        width: {
          xs: "100%",
          sm: desktopOpen ? `calc(100% - ${DRAWER_WIDTH}px)` : "100%",
        },
        ml: {
          xs: 0,
          sm: desktopOpen ? `${DRAWER_WIDTH}px` : 0,
        },
        height: 64,
        transition: "width 0.3s ease, margin 0.3s ease",
        background: "transparent",
        zIndex: theme.zIndex.drawer - 1,
      }}
    >
      <Toolbar sx={{
        display: "flex",
        alignItems: "center",
        px: 2,
        py: 0,
        m: 0,
        minHeight: "64px !important",
        height: "100%",
        gap: 1
      }}>
        <IconButton
          color="inherit"
          aria-label="toggle drawer"
          edge="start"
          onClick={onMobileDrawerToggle}
          sx={{
            mr: 2,
            display: { xs: "block", sm: "none" },
            width: 40,
            height: 40,
            p: 0.5,
            background: "transparent",
            border: "none",
          }}
        >
          <MenuIcon sx={{ fontSize: "1.2rem" }} />
        </IconButton>

        <IconButton
          color="inherit"
          aria-label="toggle desktop drawer"
          edge="start"
          onClick={onDesktopDrawerToggle}
          sx={{
            mr: 2,
            display: { xs: "none", sm: desktopOpen ? "none" : "block" },
            width: 40,
            height: 40,
            p: 0.5,
            background: "transparent",
            border: "none",
          }}
        >
          <MenuIcon sx={{ fontSize: "1.2rem" }} />
        </IconButton>

        <Box
          sx={{
            flexGrow: 1,
            display: "flex",
            justifyContent: "flex-start",
            alignItems: "center",
          }}
        >
          {icon && (
            <Box
              sx={{
                mr: 1,
                pl:1,
                display: "flex",
                alignItems: "center",
                color: theme.palette.primary.main,
              }}
            >
              {icon}
            </Box>
          )}
          <Typography
            variant="h6"
            noWrap
            sx={{
              fontWeight: 600,
              background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            {title || APP_NAME}
          </Typography>
        </Box>


      </Toolbar>
    </AppBar>
  );
}

export default AppHeader;
