import React from "react";
import { useEffect } from "react";
import { Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import GlobalStyles from "@mui/material/GlobalStyles";
import Box from "@mui/material/Box";
import "@fontsource/roboto/300.css";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import BaseAssistant from "./BaseAssistant";
import AppHeader from "./AppHeader";
import AppNavigationDrawer from "./AppNavigationDrawer";
import SmartToyIcon from '@mui/icons-material/SmartToy';

import { fetchUserAttributes, getCurrentUser } from "aws-amplify/auth";
import { SECTIONS_CONFIG, DEFAULT_HOME_SECTION } from "../env";
import { darkTheme } from "../theme";
import { DRAWER_WIDTH } from "../constants";

function AppLayout() {
  const [userName, setUserName] = React.useState("");
  const [email, setEmail] = React.useState("");

  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [desktopOpen, setDesktopOpen] = React.useState(true);

  const location = useLocation();
  const navigate = useNavigate();

  const effectRan = React.useRef(false);
  useEffect(() => {
    if (!effectRan.current) {
      console.log("effect applied - only on the FIRST mount");

      const fetchData = async () => {
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
          // Fallback to demo data if authentication fails
          setUserName("Demo User");
          setEmail("demo@nomail.com");
        }
      };
      fetchData()
        // catch any error
        .catch(console.error);
    }

    return () => (effectRan.current = true);
  }, []);

  useEffect(() => {
    if (!effectRan.current) {
      console.log("effect applied - only on the FIRST mount");
    }
    return () => (effectRan.current = true);
  }, []);



  // Icon mapping function
  const getIconComponent = (iconName) => {
    const iconMap = {
      SmartToyIcon: <SmartToyIcon />,
    };
    return iconMap[iconName] || null;
  };

  // Create sectionsConfig with actual icon components
  const sectionsConfig = Object.entries(SECTIONS_CONFIG).reduce((acc, [key, config]) => {
    acc[key] = {
      ...config,
      icon: getIconComponent(config.iconName),
    };
    return acc;
  }, {});

  // Get current section from URL path using sectionsConfig
  const getCurrentSection = () => {
    const path = location.pathname;

    // Find matching section by URL
    for (const [sectionKey, sectionConfig] of Object.entries(sectionsConfig)) {
      if (sectionConfig.url === path) {
        return sectionKey;
      }
    }

    // Default fallback (this should rarely be reached due to redirects)
    return DEFAULT_HOME_SECTION;
  };

  const currentSection = getCurrentSection();

  // Reset scroll position when route changes
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  // Redirect to default home section if current path doesn't match any valid section
  useEffect(() => {
    const path = location.pathname;
    const defaultHomeUrl = sectionsConfig[DEFAULT_HOME_SECTION]?.url || "/";

    // Skip redirect for home route and default home section URL
    if (path === "/" || path === defaultHomeUrl) return;

    // Check if current path matches any valid section URL
    const isValidPath = Object.values(sectionsConfig).some(config => config.url === path);

    // If path is not valid, redirect to default home section URL
    if (!isValidPath) {
      navigate(defaultHomeUrl, { replace: true });
    }
  }, [location.pathname, sectionsConfig, navigate]);

  // Get current section title
  const getCurrentSectionTitle = () => {
    const section = getCurrentSection();
    return sectionsConfig[section]?.title || sectionsConfig[DEFAULT_HOME_SECTION]?.title || "Home";
  };

  // Get current section icon
  const getCurrentSectionIcon = () => {
    const section = getCurrentSection();
    return sectionsConfig[section]?.icon || null;
  };


  const currentSectionTitle = getCurrentSectionTitle();
  const currentSectionIcon = getCurrentSectionIcon();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleDesktopDrawerToggle = () => {
    setDesktopOpen(!desktopOpen);
  };

  const handleSectionChange = (section) => {
    // Navigate to the appropriate URL
    const sectionConfig = sectionsConfig[section];
    const path = sectionConfig?.url || "/";
    navigate(path);

    // Close mobile drawer when navigating
    if (mobileOpen) {
      setMobileOpen(false);
    }
  };

  return (
    <ThemeProvider theme={darkTheme}>
      <GlobalStyles
        styles={{ ul: { margin: 0, padding: 0, listStyle: "none" } }}
      />
      <CssBaseline />
      <Box sx={{ display: "flex" }}>
        <AppHeader
          desktopOpen={desktopOpen}
          onMobileDrawerToggle={handleDrawerToggle}
          onDesktopDrawerToggle={handleDesktopDrawerToggle}
          title={currentSectionTitle}
          icon={currentSectionIcon}
          currentSection={currentSection}
        />

        <AppNavigationDrawer
          mobileOpen={mobileOpen}
          desktopOpen={desktopOpen}
          onMobileDrawerToggle={handleDrawerToggle}
          onDesktopDrawerToggle={handleDesktopDrawerToggle}
          onSectionChange={handleSectionChange}
          userName={userName}
          email={email}
          theme={darkTheme}
          currentSection={currentSection}
          sectionsConfig={sectionsConfig}
          sessionId={sectionsConfig[currentSection]?.sessionId}
        />

        <Box
          component="main"
          key={location.pathname}
          sx={{
            flexGrow: 1,
            width: {
              xs: "100%",
              sm: desktopOpen ? `calc(100% - ${DRAWER_WIDTH}px)` : "100%",
            },
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            transition: "width 0.3s ease",
          }}
        >
          <Routes>
            {/* Home route - redirect to default section */}
            <Route
              path="/"
              element={<Navigate to={sectionsConfig[DEFAULT_HOME_SECTION]?.url || "/"} replace />}
            />

            {/* Dynamic routes for all sections in SECTIONS_CONFIG */}
            {Object.entries(sectionsConfig).map(([sectionKey, sectionConfig]) => (
              <Route
                key={sectionKey}
                path={sectionConfig.url}
                element={
                  <BaseAssistant
                    assistantConfig={sectionConfig}
                    userName={userName}
                    email={email}
                  />
                }
              />
            ))}

            {/* Catch-all route - redirect any unmatched URL to default section */}
            <Route
              path="*"
              element={<Navigate to={sectionsConfig[DEFAULT_HOME_SECTION]?.url || "/"} replace />}
            />
          </Routes>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default AppLayout;
