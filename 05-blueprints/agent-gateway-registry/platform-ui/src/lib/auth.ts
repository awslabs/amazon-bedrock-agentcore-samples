import NextAuth from "next-auth"
import CognitoProvider from "next-auth/providers/cognito"

const REGION = process.env.GATEWAY_REGION || "us-east-1"

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    CognitoProvider({
      clientId: process.env.COGNITO_PLATFORM_CLIENT_ID || "34qdvk0q8ao79pg7aq47t503pf",
      clientSecret: "", // public client, no secret
      issuer: `https://cognito-idp.${REGION}.amazonaws.com/${process.env.COGNITO_PLATFORM_POOL_ID || "us-east-1_nDmwWEAsQ"}`,
    }),
  ],
  pages: {
    signIn: "/login",
  },
})
