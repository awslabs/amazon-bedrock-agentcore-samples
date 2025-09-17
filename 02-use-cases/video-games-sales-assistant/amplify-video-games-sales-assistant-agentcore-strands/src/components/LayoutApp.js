import React, { useEffect, useState, useRef } from "react";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import { alpha } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import GlobalStyles from "@mui/material/GlobalStyles";
import Container from "@mui/material/Container";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Button from "@mui/material/Button";

import "@fontsource/roboto/300.css";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import Chat from "./Chat";

import { APP_NAME } from "../env";
import IconButton from "@mui/material/IconButton";
import ArchitectureDiagramDialog from "./ArchitectureDiagramDialog";
import CloudOutlinedIcon from "@mui/icons-material/CloudOutlined";
import LogoutIcon from "@mui/icons-material/Logout";
import { signOut, fetchUserAttributes, getCurrentUser } from "aws-amplify/auth";

function LayoutApp() {
  const [userName, setUserName] = React.useState("Guest User");
  const [email, setEmail] = useState("");
  const [open, setOpen] = React.useState(false);

  const effectRan = useRef(false);
  useEffect(() => {
    if (!effectRan.current) {
      console.log("effect applied - only on the FIRST mount");

      const fetchUserData = async () => {
        console.log("Layout");
        try {
          const currentUser = await getCurrentUser();
          console.log(currentUser);
          setUserName(
            currentUser.signInDetails.loginId
              .split("@")[0]
              .charAt(0)
              .toUpperCase() +
              currentUser.signInDetails.loginId
                .split("@")[0]
                .slice(1)
                .toLowerCase()
          );
          setEmail(currentUser.signInDetails.loginId);
          const userAttributes = await fetchUserAttributes();
          if ("name" in userAttributes) {
            setUserName(userAttributes.name);
          }
          console.log(userAttributes);
        } catch (error) {
          console.error("Error fetching user data:", error);
        }
      };

      Promise.all([fetchUserData()])
        .catch(console.error)
        .finally(() => {
          console.log("complete loading");
        });
    }

    return () => (effectRan.current = true);
  }, []);

  const defaultTheme = createTheme({
    palette: {
      primary: {
        main: "#5425AF",
      },
      secondary: {
        main: "#812C90",
      },
    },
  });

  const handleClickOpen = () => {
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
  };

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error("Error signing out:", error);
    }
  };

  return (
    <ThemeProvider theme={defaultTheme}>
      <GlobalStyles
        styles={{ ul: { margin: 0, padding: 0, listStyle: "none" } }}
      />
      <CssBaseline />
      <AppBar
        position="static"
        elevation={0}
        sx={(theme) => ({
          bgcolor: alpha(theme.palette.secondary.main, 0.04),
          borderBottom: 1,
          borderColor: alpha(theme.palette.secondary.main, 0.1),
        })}
      >
        <Toolbar sx={{ minHeight: { xs: 56, sm: 64 }, px: { xs: 2, sm: 3 } }}>
          <Typography
            variant="h6"
            color="primary"
            sx={{
              flexGrow: 1,
              fontSize: { xs: "1.1rem", sm: "1.25rem" },
              fontWeight: 600,
            }}
          >
            {APP_NAME}
          </Typography>

          {/* Desktop view */}
          <Box
            sx={{
              display: { xs: "none", sm: "flex" },
              alignItems: "center",
              gap: 1.5,
            }}
          >
            <Typography variant="body1" color="text.primary">{userName}</Typography>
            <IconButton
              onClick={handleSignOut}
              size="small"
              sx={{ color: "primary.main" }}
            >
              <LogoutIcon fontSize="small" />
            </IconButton>
          </Box>

          {/* Mobile view */}
          <Box
            sx={{ display: { xs: "flex", sm: "none" }, alignItems: "center" }}
          >
            <IconButton
              onClick={handleSignOut}
              size="small"
              sx={{ color: "primary.main" }}
            >
              <LogoutIcon fontSize="small" />
            </IconButton>
          </Box>
        </Toolbar>
      </AppBar>
      <Container disableGutters maxWidth="xl" component="main">
        <Chat userName={userName} />
      </Container>
      <Box textAlign={"center"}>
        <Typography
          variant="body2"
          sx={{ pb: 1, pl: 2, pr: 2, fontSize: "0.775rem" }}
        >
          &copy;{new Date().getFullYear()}, Amazon Web Services, Inc. or its
          affiliates. All rights reserved.
        </Typography>
        <img src="/images/Powered-By_logo-horiz_RGB.png" />
      </Box>

      <Box sx={{ position: "fixed", bottom: "8px", right: "12px" }}>
        <IconButton aria-label="" onClick={handleClickOpen}>
          <CloudOutlinedIcon />
        </IconButton>
      </Box>

      <ArchitectureDiagramDialog open={open} onClose={handleClose} src="/images/gen-ai-assistant-diagram.png" />
    </ThemeProvider>
  );
}

export default LayoutApp;
