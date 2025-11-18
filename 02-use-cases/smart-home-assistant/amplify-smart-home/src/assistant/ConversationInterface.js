import React, { useLayoutEffect, useRef, useEffect } from "react";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Alert from "@mui/material/Alert";
import Grow from "@mui/material/Grow";
import Fade from "@mui/material/Fade";

import { useTheme } from "@mui/material/styles";
import LoadingIndicator from "./LoadingIndicator.js";
import { getAnswer } from "../utils/AgentCoreCall";
import MarkdownRenderer from "./MarkdownRenderer.js";
import ToolBox from "./ToolBox";
import WelcomeSection from "./WelcomeSection.js";
import ChatInput from "./ChatInput.js";
import MediaAssets from "./MediaAssets.js";

const ConversationInterface = ({
  assistantConfig = {},
  userName = "",
  email = "",
}) => {
  const theme = useTheme();

  const [enabled, setEnabled] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [controlAnswers, setControlAnswers] = React.useState([]);
  const [answers, setAnswers] = React.useState([]);
  const [query, setQuery] = React.useState("");
  const sessionId = assistantConfig.sessionId;
  const [errorMessage, setErrorMessage] = React.useState("");
  const [height, setHeight] = React.useState(480);
  const [currentWorkingToolId, setCurrentWorkingToolId] = React.useState(null);

  const borderRadius = 8;

  const scrollRef = useRef(null);
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [answers]);

  useLayoutEffect(() => {
    function updateSize() {
      const myh = window.innerHeight - 80;
      if (myh < 346) {
        setHeight(346);
      } else {
        setHeight(myh);
      }
    }
    window.addEventListener("resize", updateSize);
    updateSize();
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  const effectRan = React.useRef(false);
  useEffect(() => {
    if (!effectRan.current) {
      console.log("effect applied - only on the FIRST mount");
      const fetchData = async () => {
        console.log("Chat");
      };
      fetchData()
        // catch any error
        .catch(console.error);
    }
    return () => (effectRan.current = true);
  }, []);

  const handleQuery = (event) => {
    if (event.target.value.length > 0 && loading === false && query !== "")
      setEnabled(true);
    else setEnabled(false);
    setQuery(event.target.value.replace(/\n/g, ""));
  };

  const handleKeyPress = (event) => {
    if (event.code === "Enter" && loading === false && query !== "") {
      handleGetAnswer(query);
    }
  };

  const handleClick = async (e) => {
    e.preventDefault();
    if (query !== "") {
      handleGetAnswer(query);
    }
  };

  const handleGetAnswer = async (my_query) => {
    if (!loading && my_query !== "") {
      await getAnswer(
        my_query,
        sessionId,
        setControlAnswers,
        setAnswers,
        setEnabled,
        setLoading,
        setErrorMessage,
        setQuery,
        setCurrentWorkingToolId,
        assistantConfig,
        userName,
        email
      );
    }
  };

  return (
    <Box
      sx={{
        display: "flex",
        overflow: "hidden",
        width: "100%",
        height: "100vh",
      }}
    >
      {/* Main Chat Area */}
      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          maxWidth: "lg",
          mx: "auto",
          pl: 2,
          pr: 2,
          pt: 0,
          pb: 0,
        }}
      >
        {errorMessage !== "" && (
          <Alert
            severity="error"
            onClose={() => setErrorMessage("")}
            sx={{
              position: "fixed",
              top: 16,
              left: "50%",
              transform: "translateX(-50%)",
              maxWidth: 500,
              zIndex: 1300,
              boxShadow: 3,
            }}
          >
            {errorMessage}
          </Alert>
        )}

        <Box
          id="chatSpace"
          sx={{
            display: "flex",
            flexDirection: "column",
            height: height,
            overflow: "hidden",
            overflowY: "scroll",
            pt: { xs: "64px", sm: "68px" },
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
          {answers.length > 0 ? (
            <ul style={{ paddingBottom: 14, margin: 0, listStyleType: "none" }}>
              {answers.map((answer, index) => (
                <li key={"meg" + index} style={{ marginBottom: 0 }}>
                  {answer.hasOwnProperty("text") && answer.text.length > 0 && (
                    <Box
                      sx={{
                        borderRadius: borderRadius,
                        pl: 1,
                        pr: 1,
                        display: "flex",
                        alignItems: "flex-start",
                        marginBottom: 1,
                      }}
                    >
                      <Box sx={{ pr: 1, pt: 1.5, pl: 0.5 }}>
                        <img
                          src="/images/genai.png"
                          alt="Amazon Bedrock"
                          width={28}
                          height={28}
                        />
                      </Box>
                      <Box sx={{ p: 0, flex: 1 }}>
                        <Box>
                          <Grow
                            in={
                              controlAnswers[index].current_tab_view ===
                              "answer"
                            }
                            timeout={{ enter: 600, exit: 0 }}
                            style={{ transformOrigin: "50% 0 0" }}
                            mountOnEnter
                            unmountOnExit
                          >
                            <Box
                              id={"answer" + index}
                              sx={{
                                opacity: 0.8,
                                "&.MuiBox-root": {
                                  animation: "fadeIn 0.8s ease-in-out forwards",
                                },
                                mt: 1,
                              }}
                            >
                              <Typography component="div" variant="body1">
                                {answer.text.map((item, itemIndex) => {
                                  if (item.type === "text") {
                                    return (
                                      <MarkdownRenderer
                                        key={itemIndex}
                                        content={item.content}
                                      />
                                    );
                                  } else if (item.type === "tool") {
                                    return (
                                      <Fade
                                        key={itemIndex}
                                        in={true}
                                        timeout={{ enter: 600, exit: 400 }}
                                        style={{
                                          transition: 'opacity 0.6s cubic-bezier(0.4, 0.0, 0.2, 1)'
                                        }}
                                      >
                                        <Box>
                                          <ToolBox
                                            item={item}
                                            isLoading={currentWorkingToolId === item.toolUseId}
                                          />
                                        </Box>
                                      </Fade>
                                    );
                                  }
                                  return null;
                                })}
                              </Typography>

                              {/* Media Assets Display */}
                              {answer.hasOwnProperty("mediaAssets") &&
                                answer.mediaAssets &&
                                answer.mediaAssets.length > 0 && (
                                  <Box sx={{ mt: 2, mb: 2 }}>
                                    <MediaAssets mediaAssets={answer.mediaAssets} />
                                  </Box>
                                )}

                            </Box>
                          </Grow>
                        </Box>
                      </Box>
                    </Box>
                  )}
                  {answer.hasOwnProperty("query") && answer.query !== "" && (
                    <Grid container justifyContent="flex-end">
                      <Box
                        sx={(theme) => ({
                          textAlign: "right",
                          borderRadius: borderRadius,
                          pt: 1,
                          pb: 1,
                          pl: 2,
                          pr: 2,
                          mt: 2,
                          mb: 1.5,
                          mr: 1,
                          boxShadow: "rgba(0, 0, 0, 0.05) 0px 4px 12px",
                          background: `linear-gradient(135deg, #68C64E 0%, ${theme.palette.primary.dark} 100%)`,
                          border: "1px solid rgba(255, 255, 255, 0.1)",
                        })}
                      >
                        <Typography
                          variant="body1"
                          sx={{
                            fontWeight: 500,
                            textShadow: "0 1px 2px rgba(255, 255, 255, 0.2)",
                          }}
                        >
                          {answer.query}
                        </Typography>
                      </Box>
                    </Grid>
                  )}
                </li>
              ))}

              <Box
                sx={{
                  p: 0,
                  pl: 0.5,
                  mt: 1,
                  height: loading ? "48px" : "0px",
                  overflow: "hidden",
                  display: "flex",
                  justifyContent: "left",
                  transition: "height 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
                }}
              >
                <Grow
                  in={loading}
                  timeout={{ enter: 800, exit: 400 }}
                  style={{
                    transformOrigin: "top left",
                  }}
                >
                  <Box sx={{ width: "100%" }}>
                    <Fade
                      in={loading}
                      timeout={{ enter: 600, exit: 300 }}
                      style={{
                        transitionDelay: loading ? '100ms' : '0ms'
                      }}
                    >
                      <Box
                        sx={{
                          transform: loading ? "translateY(0)" : "translateY(10px)",
                          transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
                          opacity: loading ? 1 : 0,
                        }}
                      >
                        <LoadingIndicator loading={loading} />
                      </Box>
                    </Fade>
                  </Box>
                </Grow>
              </Box>

              {/* this is the last item that scrolls into
                    view when the effect is run */}
              <li ref={scrollRef} />
            </ul>
          ) : (
            <WelcomeSection
              image={ assistantConfig.assistantIcon}
              title={ assistantConfig.assistantName}
              description={ assistantConfig.assistantDescription}
              height={height}
              onQuestionClick={handleGetAnswer}
              sampleQuestions={ assistantConfig.sampleQuestions}
            />
          )}
        </Box>

        <ChatInput
          query={query}
          enabled={enabled}
          loading={loading}
          onQueryChange={handleQuery}
          onKeyPress={handleKeyPress}
          onSubmit={handleClick}
        />
      </Box>


    </Box >
  );
};

export default ConversationInterface;
