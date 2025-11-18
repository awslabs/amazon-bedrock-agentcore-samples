import React, { useEffect, useRef } from "react";
import { Paper, Box, InputBase, IconButton, GlobalStyles } from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import ArrowUpwardRoundedIcon from '@mui/icons-material/ArrowUpwardRounded';
import { alpha } from "@mui/material/styles";
import { MAX_LENGTH_INPUT_SEARCH } from "../env";

const ChatInput = ({
  query,
  enabled,
  loading,
  onQueryChange,
  onKeyPress,
  onSubmit
}) => {
  const inputRef = useRef(null);

  useEffect(() => {
    // Focus the input element
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []); // Empty dependency array means this runs once on mount

  return (
    <>
      <GlobalStyles
        styles={{
          "@keyframes inputGlow": {
            "0%": {
              opacity: 0.8,
              filter: "blur(1px)",
            },
            "50%": {
              opacity: 1,
              filter: "blur(0px)",
            },
            "100%": {
              opacity: 0.8,
              filter: "blur(1px)",
            },
          },
        }}
      />
      <Paper
        component="form"
        sx={(theme) => ({
          zIndex: 0,
          p: 1,
          mt: 1,
          display: "flex",
          alignItems: "center",
          background: "transparent",
          boxShadow: `
            ${alpha(theme.palette.primary.main, 0.01)} 0px 4px 16px, 
            ${alpha(theme.palette.primary.main, 0.01)} 0px 8px 24px, 
            ${alpha(theme.palette.primary.main, 0.01)} 0px 16px 56px
          `,
          borderRadius: 6,
          position: "relative",
          border: "none",
          transition: "all 0.3s ease-in-out",
          "&:hover, &:focus-within": {
            filter: `drop-shadow(0 0 20px ${theme.palette.secondary.main}60) drop-shadow(0 0 40px ${theme.palette.primary.main}40)`,
          },
          "&::before": {
            content: '""',
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            borderRadius: 6,
            padding: "2px",
            background: `linear-gradient(135deg, 
    ${alpha(theme.palette.primary.main, 0.9)}, 
    ${alpha(theme.palette.secondary.main, 0.8)}, 
    ${alpha(theme.palette.primary.light, 0.7)},
    ${alpha(theme.palette.secondary.main, 0.9)}
  )`,
            WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
            WebkitMaskComposite: "xor",
            mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
            maskComposite: "exclude",
            "@supports (-moz-appearance:none)": {
              mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
              maskComposite: "subtract",
            },
            zIndex: -1,
            animation: "inputGlow 3s ease-in-out infinite",
          },
        })}
      >
        <Box sx={{ pt: 1.5, pl: 0.5 }}>
          <img
            src="/images/AWS_logo_RGB.png"
            alt="Amazon Web Services"
            height={20}
          />
        </Box>
        <InputBase
          required
          inputRef={inputRef}
          id="query"
          name="query"
          placeholder="Type your question..."
          fullWidth
          multiline
          onChange={onQueryChange}
          onKeyDown={onKeyPress}
          value={query}
          variant="outlined"
          inputProps={{ maxLength: MAX_LENGTH_INPUT_SEARCH }}
          sx={{ pl: 1, pr: 2 }}
        />
        <IconButton
          color="primary"
          sx={(theme) => ({
            p: 1,
            background: enabled
              ? `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`
              : alpha(theme.palette.action.disabled, 0.1),
            borderRadius: "50%",
            width: 40,
            height: 40,
            minWidth: 40,
            "&:hover": enabled
              ? {
                background: `linear-gradient(135deg, ${theme.palette.primary.light}, ${theme.palette.secondary.light})`,
              }
              : {},
            "&:disabled": {
              background: alpha(theme.palette.action.disabled, 0.05),
              color: alpha(theme.palette.text.disabled, 0.3),
            },
            "& .MuiSvgIcon-root": {
              color: enabled ? "#ffffff" : "inherit",
              fontSize: 20,
            },
          })}
          aria-label="directions"
          disabled={!enabled}
          onClick={onSubmit}
        >
          <ArrowUpwardRoundedIcon />
        </IconButton>
      </Paper>
    </>
  );
};

export default ChatInput;