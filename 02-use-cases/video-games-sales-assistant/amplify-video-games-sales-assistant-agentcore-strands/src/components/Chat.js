import React, { useLayoutEffect, useRef, useEffect } from "react";
import Typography from "@mui/material/Typography";
import IconButton from "@mui/material/IconButton";
import SendIcon from "@mui/icons-material/Send";
import Paper from "@mui/material/Paper";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import InputBase from "@mui/material/InputBase";
import Divider from "@mui/material/Divider";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import Button from "@mui/material/Button";
import Grow from "@mui/material/Grow";
import Fade from "@mui/material/Fade";
import { v4 as uuidv4 } from "uuid";
import InsightsOutlinedIcon from "@mui/icons-material/InsightsOutlined";
import QuestionAnswerOutlinedIcon from "@mui/icons-material/QuestionAnswerOutlined";
import TableRowsRoundedIcon from "@mui/icons-material/TableRowsRounded";
import { WELCOME_MESSAGE, MAX_LENGTH_INPUT_SEARCH } from "../env";
import MyChart from "./MyChart.js";
import LoadingIndicator from "./LoadingIndicator.js";
import QueryResultsDisplay from "./QueryResultsDisplay";
import ToolBox from "./ToolBox";
import { alpha } from "@mui/material/styles";
import {
  generateChart,
} from "../utils/AwsCalls";
import { getAnswer } from "../utils/AgentCoreCall";
import MarkdownRenderer from "./MarkdownRenderer.js";

const Chat = () => {
  const [totalAnswers, setTotalAnswers] = React.useState(0);
  const [enabled, setEnabled] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [controlAnswers, setControlAnswers] = React.useState([]);
  const [answers, setAnswers] = React.useState([]);
  const [query, setQuery] = React.useState("");
  const [sessionId] = React.useState(uuidv4());
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
      const myh = window.innerHeight - 220;
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

  // Handle chart generation when queryResults are available
  useEffect(() => {
    const generateChartForAnswer = async (answerIndex, answer) => {
      if (answer.queryResults && answer.chart === "loading") {
        try {
          const chartData = await generateChart(answer);
          console.log("--------- Answer after chart generation ------");
          console.log(chartData);

          setAnswers((prevState) => {
            const newState = [...prevState];
            if (newState[answerIndex]) {
              newState[answerIndex] = {
                ...newState[answerIndex],
                chart: chartData,
              };
            }
            return newState;
          });

          setTotalAnswers((prevState) => prevState + 1);
        } catch (error) {
          console.error("Chart generation failed:", error);
          setAnswers((prevState) => {
            const newState = [...prevState];
            if (newState[answerIndex]) {
              newState[answerIndex] = {
                ...newState[answerIndex],
                chart: { rationale: "Error generating chart" },
              };
            }
            return newState;
          });
        }
      }
    };

    // Check all answers for pending chart generation
    answers.forEach((answer, index) => {
      if (answer.queryResults && answer.chart === "loading") {
        generateChartForAnswer(index, answer);
      }
    });
  }, [answers]);

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
        setCurrentWorkingToolId
      );
    }
  };

  const handleShowTab = (index, type) => () => {
    const updatedItems = [...controlAnswers];
    updatedItems[index] = { ...updatedItems[index], current_tab_view: type };
    setControlAnswers(updatedItems);
  };

  return (
    <Box sx={{ pl: 2, pr: 2, pt: 0, pb: 0 }}>
      {errorMessage !== "" && (
        <Alert
          severity="error"
          sx={{
            position: "fixed",
            width: "80%",
            top: "65px",
            left: "20%",
            marginLeft: "-10%",
          }}
          onClose={() => {
            setErrorMessage("");
          }}
        >
          {errorMessage}
        </Alert>
      )}

      <Box
        id="chatHelper"
        sx={{
          display: "flex",
          flexDirection: "column",
          height: height,
          overflow: "hidden",
          overflowY: "scroll",
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
                            controlAnswers[index].current_tab_view === "answer"
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
                          </Box>
                        </Grow>

                        {answer.hasOwnProperty("queryResults") && (
                          <Grow
                            in={
                              controlAnswers[index].current_tab_view ===
                              "records"
                            }
                            timeout={{ enter: 600, exit: 0 }}
                            style={{ transformOrigin: "50% 0 0" }}
                            mountOnEnter
                            unmountOnExit
                          >
                            <Box
                              sx={{
                                opacity: 0.8,
                                "&.MuiBox-root": {
                                  animation: "fadeIn 0.8s ease-in-out forwards",
                                },
                                transform: "translateY(10px)",
                                "&.MuiBox-root-appear": {
                                  transform: "translateY(0)",
                                },
                                mt: 1,
                              }}
                            >
                              <QueryResultsDisplay
                                index={index}
                                answer={answer}
                              />
                            </Box>
                          </Grow>
                        )}

                        {answer.hasOwnProperty("chart") &&
                          answer.chart.hasOwnProperty("chart_type") && (
                            <Grow
                              in={
                                controlAnswers[index].current_tab_view ===
                                "chart"
                              }
                              timeout={{ enter: 600, exit: 0 }}
                              style={{ transformOrigin: "50% 0 0" }}
                              mountOnEnter
                              unmountOnExit
                            >
                              <Box
                                sx={{
                                  opacity: 0.8,
                                  "&.MuiBox-root": {
                                    animation:
                                      "fadeIn 0.9s ease-in-out forwards",
                                  },
                                  transform: "translateY(10px)",
                                  "&.MuiBox-root-appear": {
                                    transform: "translateY(0)",
                                  },
                                  mt: 1,
                                }}
                              >
                                <MyChart
                                  caption={answer.chart.caption}
                                  options={
                                    answer.chart.chart_configuration.options
                                  }
                                  series={
                                    answer.chart.chart_configuration.series
                                  }
                                  type={answer.chart.chart_type}
                                />
                              </Box>
                            </Grow>
                          )}
                      </Box>

                      {answer.hasOwnProperty("queryResults") && (
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "flex-start",
                            gap: 1,
                            py: 1,
                            mt: 1,
                          }}
                        >
                          {answer.queryResults.length > 0 && (
                            <Fade
                              timeout={1000}
                              in={answer.queryResults.length > 0}
                            >
                              <Box
                                sx={{ display: "flex", alignItems: "center" }}
                              >
                                <Button
                                  sx={(theme) => ({
                                    pr: 1,
                                    pl: 1,
                                    "&.Mui-disabled": {
                                      borderBottom: 0.5,
                                      color: theme.palette.primary.main,
                                      borderRadius: 0,
                                    },
                                  })}
                                  data-amplify-analytics-on="click"
                                  data-amplify-analytics-name="click"
                                  data-amplify-analytics-attrs="button:answer-details"
                                  size="small"
                                  color="secondaryText"
                                  disabled={
                                    controlAnswers[index].current_tab_view ===
                                    "answer"
                                  }
                                  onClick={handleShowTab(index, "answer")}
                                  startIcon={<QuestionAnswerOutlinedIcon />}
                                >
                                  Answer
                                </Button>

                                <Button
                                  sx={(theme) => ({
                                    pr: 1,
                                    pl: 1,
                                    "&.Mui-disabled": {
                                      borderBottom: 0.5,
                                      color: theme.palette.primary.main,
                                      borderRadius: 0,
                                    },
                                  })}
                                  data-amplify-analytics-on="click"
                                  data-amplify-analytics-name="click"
                                  data-amplify-analytics-attrs="button:answer-details"
                                  size="small"
                                  color="secondaryText"
                                  disabled={
                                    controlAnswers[index].current_tab_view ===
                                    "records"
                                  }
                                  onClick={handleShowTab(index, "records")}
                                  startIcon={<TableRowsRoundedIcon />}
                                >
                                  Records
                                </Button>

                                {typeof answer.chart === "object" &&
                                  answer.chart.hasOwnProperty("chart_type") && (
                                    <Button
                                      sx={(theme) => ({
                                        pr: 1,
                                        pl: 1,
                                        "&.Mui-disabled": {
                                          borderBottom: 0.5,
                                          color: theme.palette.primary.main,
                                          borderRadius: 0,
                                        },
                                      })}
                                      data-amplify-analytics-on="click"
                                      data-amplify-analytics-name="click"
                                      data-amplify-analytics-attrs="button:answer-details"
                                      size="small"
                                      color="secondaryText"
                                      disabled={
                                        controlAnswers[index]
                                          .current_tab_view === "chart"
                                      }
                                      onClick={handleShowTab(index, "chart")}
                                      startIcon={<InsightsOutlinedIcon />}
                                    >
                                      Chart
                                    </Button>
                                  )}
                              </Box>
                            </Fade>
                          )}

                          {answer.chart === "loading" && (
                            <Box
                              sx={{
                                display: "flex",
                                alignItems: "center",
                                ml: 1,
                              }}
                            >
                              <CircularProgress size={16} color="primary" />
                              <Typography
                                variant="caption"
                                color="secondaryText"
                                sx={{ ml: 1 }}
                              >
                                Generating chart...
                              </Typography>
                            </Box>
                          )}

                          {answer.chart.hasOwnProperty("rationale") && (
                            <Typography variant="caption" color="secondaryText">
                              {answer.chart.rationale}
                            </Typography>
                          )}
                        </Box>
                      )}
                    </Box>
                  </Box>
                )}

                {answer.hasOwnProperty("query") && answer.query !== "" && (
                  <Grid container justifyContent="flex-end">
                    <Box
                      sx={(theme) => ({
                        textAlign: "right",
                        borderRadius: borderRadius,
                        fontWeight: 500,
                        py: 1,
                        px: 2,
                        mt: 2,
                        mb: 1.5,
                        mr: 1,
                        boxShadow: "rgba(0, 0, 0, 0.05) 0px 4px 12px",
                        border: `1px solid ${alpha(
                          theme.palette.secondary.main,
                          0.15
                        )}`,
                        backgroundColor: alpha(
                          theme.palette.secondary.main,
                          0.1
                        ),
                      })}
                    >
                      <Typography
                        sx={{
                          color: "text.primary",
                          fontSize: "0.95rem",
                          fontWeight: 500,
                        }}
                      >
                        {answer.query}
                      </Typography>
                    </Box>
                  </Grid>
                )}
              </li>
            ))}

            {loading && (
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
            )}

            {/* this is the last item that scrolls into
                    view when the effect is run */}
            <li ref={scrollRef} />
          </ul>
        ) : (
          <Box
            sx={{
              height: height,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              px: 3,
            }}
          >
            <Box sx={{ textAlign: "center", maxWidth: 600 }}>
              <Box sx={{ mb: 4 }}>
                <img
                  src="images/agentcore.png"
                  alt="Amazon Bedrock AgentCore"
                  height={128}
                  style={{ opacity: 0.9 }}
                />
              </Box>

              <Typography
                variant="h4"
                sx={{
                  fontWeight: 600,
                  fontSize: { xs: "1.75rem", sm: "2rem" },
                  lineHeight: 1.2,
                  mb: 2,
                  color: "text.primary",
                  letterSpacing: "-0.02em",
                }}
              >
                Amazon Bedrock AgentCore
              </Typography>

              <Typography
                variant="body1"
                sx={{
                  color: "text.secondary",
                  fontSize: "1.1rem",
                  lineHeight: 1.5,
                  mb: 3,
                  fontWeight: 400,
                }}
              >
                Secure, scalable AI agent deployment and operations platform
                with support for Strands Agent SDK and other frameworks.
              </Typography>

              <Box
                sx={(theme) => ({
                  borderRadius: 2,
                  px: 3,
                  py: 2,
                  border: `1px solid ${alpha(
                    theme.palette.secondary.main,
                    0.15
                  )}`,
                  backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                })}
              >
                <Typography
                  variant="body1"
                  sx={{
                    color: "secondary.main",
                    fontWeight: 500,
                    lineHeight: 1.4,
                  }}
                >
                  {WELCOME_MESSAGE}
                </Typography>
              </Box>
            </Box>
          </Box>
        )}
      </Box>

      <Paper
        component="form"
        sx={(theme) => ({
          zIndex: 0,
          p: 1,
          mb: 2,
          display: "flex",
          alignItems: "center",
          boxShadow:
            "rgba(20, 40, 60, 0.06) 0px 4px 16px, rgba(20, 40, 60, 0.04) 0px 8px 24px, rgba(20, 40, 60, 0.03) 0px 16px 56px",
          borderRadius: 6,
          position: "relative",
          // Remove the default border
          border: "none",
          // Add gradient border using pseudo-element
          "&::before": {
            content: '""',
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            borderRadius: 6,
            padding: "1px", // This creates the border thickness
            background: `linear-gradient(to right, 
                    ${theme.palette.divider}, 
                    ${alpha(theme.palette.primary.main, 0.3)}, 
                    ${theme.palette.divider})`,
            mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
            maskComposite: "xor",
            WebkitMask:
              "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
            WebkitMaskComposite: "xor",
            zIndex: -1,
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
          id="query"
          name="query"
          placeholder="Type your question..."
          fullWidth
          multiline
          onChange={handleQuery}
          onKeyDown={handleKeyPress}
          value={query}
          variant="outlined"
          inputProps={{ maxLength: MAX_LENGTH_INPUT_SEARCH }}
          sx={{ pl: 1, pr: 2 }}
        />
        <Divider sx={{ height: 32 }} orientation="vertical" />
        <IconButton
          color="primary"
          sx={{ p: 1 }}
          aria-label="directions"
          disabled={!enabled}
          onClick={handleClick}
        >
          <SendIcon />
        </IconButton>
      </Paper>
    </Box>
  );
};

export default Chat;
