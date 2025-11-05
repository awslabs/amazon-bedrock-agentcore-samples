import React from "react";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Fade from "@mui/material/Fade";

const LoadingIndicator = ({ loading }) => {
  return (
    <Fade timeout={1000} in={loading}>
      <Stack
        direction="row"
        spacing={2}
        sx={{
          display: "flex",
          alignItems: "center",
          alignContent: "top",
        }}
      >
        <CircularProgress size={22} color="primary" sx={{ p: 0, m: 0 }} />
        <Box
          sx={(theme) => ({
            pt: 1,
            pb: 1,
            pl: 2,
            pr: 2,
            m: 0,
            borderRadius: 4,
            display: "flex",
            boxShadow: "rgba(0, 0, 0, 0.05) 0px 4px 12px",
          })}
        >
          <Typography variant="body1">Answering your question...</Typography>
        </Box>
      </Stack>
    </Fade>
  );
};

export default LoadingIndicator;