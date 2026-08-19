import { createTheme } from '@mui/material/styles';

// Create a theme instance
const theme = createTheme({
  palette: {
    primary: {
      main: '#0066cc',
      light: '#4d94ff',
      dark: '#004c99',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#ff9900',
      light: '#ffb84d',
      dark: '#cc7a00',
      contrastText: '#000000',
    },
    error: {
      main: '#d13212',
      light: '#dc5a41',
      dark: '#a2260e',
      contrastText: '#ffffff',
    },
    warning: {
      main: '#ffcc00',
      light: '#ffd633',
      dark: '#cca300',
      contrastText: '#000000',
    },
    info: {
      main: '#0073bb',
      light: '#3391c9',
      dark: '#005994',
      contrastText: '#ffffff',
    },
    success: {
      main: '#1d8102',
      light: '#4a9a35',
      dark: '#166401',
      contrastText: '#ffffff',
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
    text: {
      primary: '#16191f',
      secondary: '#5f6b7a',
      disabled: '#9ba7b6',
    },
  },
  typography: {
    fontFamily: '"Amazon Ember", "Helvetica Neue", Arial, sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 500,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 500,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 500,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 500,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 500,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 500,
    },
    body1: {
      fontSize: '1rem',
    },
    body2: {
      fontSize: '0.875rem',
    },
    button: {
      textTransform: 'none',
    },
  },
  shape: {
    borderRadius: 4,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 4,
          padding: '8px 16px',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
        },
      },
    },
  },
});

export default theme;
