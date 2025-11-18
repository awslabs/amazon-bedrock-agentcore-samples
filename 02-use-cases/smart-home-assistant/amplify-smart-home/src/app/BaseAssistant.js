import { useState, useEffect } from "react";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Container from "@mui/material/Container";
import Grow from "@mui/material/Grow";
import ConversationInterface from "../assistant/ConversationInterface";

const BaseAssistant = ({ assistantConfig, userName, email }) => {
  const [showContent, setShowContent] = useState(false);

  // Trigger animations on component mount
  useEffect(() => {
    const timer = setTimeout(() => {
      setShowContent(true);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  return (
    <Container
      disableGutters
      maxWidth={false}
      sx={{
        flexGrow: 1,
        height: "calc(100vh - 64px)",
      }}
    >
      <Grid
        container
        columns={{ xs: 4, sm: 8, md: 12 }}
        sx={{ height: "100%" }}
      >
        {/* Chat - Full Width */}
        <Grid
          item
          size={{ xs: 12, sm: 12, md: 12 }}
          sx={{
            height: "100%",
          }}
        >
          <Grow in={showContent} timeout={800}>
            <Box
              sx={{ height: "100%", display: "flex", flexDirection: "column" }}
            >
              <ConversationInterface
                assistantConfig={assistantConfig}
                userName={userName}
                email={email}
              />
            </Box>
          </Grow>
        </Grid>
      </Grid>
    </Container>
  );
};

export default BaseAssistant;