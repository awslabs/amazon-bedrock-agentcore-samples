import { defineAuth } from '@aws-amplify/backend'

export const auth = defineAuth({
  loginWith: {
    email: true,
  },
  // // Require MFA for enhanced security
  // multifactor: {
  //   mode: 'REQUIRED',
  //   totp: true,
  //   sms: true, // Allow both SMS and TOTP options for user flexibility
  // },
  // MFA disabled
  multifactor: {
    mode: 'OFF',
  },
  // Enhanced password policy
  userAttributes: {
    email: {
      required: true,
      mutable: true,
    },
    givenName: {
      required: true,
      mutable: true,
    },
    familyName: {
      required: true,
      mutable: true,
    },
  },
  // Simple user group for basic access control
  groups: ['user'],
})
