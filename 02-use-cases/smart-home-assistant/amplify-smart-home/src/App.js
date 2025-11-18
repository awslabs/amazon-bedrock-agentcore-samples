import { useEffect } from "react";
import "./App.css";
import {
  Authenticator,
  View,
  Heading,
  useTheme,
  ThemeProvider,
} from "@aws-amplify/ui-react";
import "@aws-amplify/ui-react/styles.css";
import { Amplify } from "aws-amplify";
import { BrowserRouter } from "react-router-dom";
import AppLayout from "./app/AppLayout";
import { APP_NAME } from "./env";

import awsExports from "./aws-exports";
Amplify.configure(awsExports);

function App() {
  useEffect(() => {
    document.title = APP_NAME;
  }, []);

  const components = {
    Header() {
      const { tokens } = useTheme();

      return (
        <View
          textAlign="center"
          padding={`${tokens.space.xl} ${tokens.space.large} ${tokens.space.large}`}
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "16px"
          }}
        >
          <img
            src="/images/app-logo.svg"
            alt="App Logo"
            style={{
              height: "64px",
              width: "64px",
            }}
          />
          <Heading
            level={1}
            style={{
              color: "var(--amplify-colors-brand-primary-80)",
              margin: "0",
              lineHeight: "1.2"
            }}
            fontWeight={tokens.fontWeights.bold}
            fontSize={tokens.fontSizes.xxl}
          >
            {APP_NAME}
          </Heading>
        </View>
      );
    },
  };

  return (
    <ThemeProvider>
      <Authenticator
        components={components}
      //hideSignUp
      >
        <BrowserRouter>
          <AppLayout />
        </BrowserRouter>
      </Authenticator>
    </ThemeProvider>
  );
}

export default App;
