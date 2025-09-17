import React, { useEffect } from "react";
import "./App.css";
import {
  Authenticator,
  View,
  Text,
  Heading,
  useTheme,
  ThemeProvider,
} from "@aws-amplify/ui-react";
import "@aws-amplify/ui-react/styles.css";
import { Amplify } from "aws-amplify";
import LayoutApp from "./components/LayoutApp";
import { APP_NAME } from "./env";

import awsExports from "./aws-exports";
Amplify.configure(awsExports);

function App({ signOut, user }) {
  useEffect(() => {
    document.title = APP_NAME;
  }, []);

  const components = {
    Header() {
      const { tokens } = useTheme();

      return (
        <View textAlign="center" padding={tokens.space.large}>
          <Heading
            level={2}
            style={{ color: "#333333", paddingTop: "48px" }}
            fontWeight={tokens.fontWeights.semibold}
            fontSize={tokens.fontSizes.xl}
          >
            {APP_NAME}
          </Heading>
        </View>
      );
    },

    Footer() {
      const { tokens } = useTheme();

      return (
        <View textAlign="center" style={{ padding: "0px", margin: "0px" }}>
          <Text
            style={{
              fontSize: "0.875rem",
              color: "#7F7F7F",
              padding: "16px 0px 8px 0px",
            }}
          >
            &copy;{new Date().getFullYear()}, Amazon Web Services, Inc. or its
            affiliates. All rights reserved.
          </Text>
          <img
            src="/images/Powered-By_logo-horiz_RGB.png"
            width={160}
            alt="Powered By AWS"
          />
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
        <LayoutApp />
      </Authenticator>
    </ThemeProvider>
  );
}

export default App;
