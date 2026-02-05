import js from '@eslint/js';
import typescript from '@typescript-eslint/eslint-plugin';
import typescriptParser from '@typescript-eslint/parser';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import security from 'eslint-plugin-security';
import prettier from 'eslint-config-prettier';
import globals from 'globals';

export default [
  // Base configuration for all files
  {
    files: ['**/*.{js,mjs,cjs,ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      parser: typescriptParser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        ...globals.node,
        ...globals.es2022,
      },
    },
    plugins: {
      '@typescript-eslint': typescript,
      security,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...typescript.configs.recommended.rules,
      ...security.configs.recommended.rules,
      
      // TypeScript essentials
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-require-imports': 'error',
      
      // Security essentials
      'security/detect-object-injection': 'warn', // Reduced to warn as it's often false positive
      'security/detect-eval-with-expression': 'error',
      'security/detect-non-literal-fs-filename': 'warn',
      
      // Code quality essentials
      'no-console': 'warn',
      'no-debugger': 'error',
      'no-var': 'error',
      'prefer-const': 'error',
      'complexity': ['warn', 15],
    },
  },

  // Test files configuration
  {
    files: ['**/*.test.ts', '**/*.spec.ts', '**/__tests__/**/*.ts'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      'no-console': 'off',
    },
  },

  // React/Next.js configuration for web-console
  {
    files: ['web-console/**/*.{ts,tsx,js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      parser: typescriptParser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        ...globals.browser,
        ...globals.es2022,
        ...globals.node, // For Next.js server-side code
        // Add missing browser/Node.js globals
        NodeJS: 'readonly',
        RequestInit: 'readonly',
        Response: 'readonly',
        AbortController: 'readonly',
        HTMLElement: 'readonly',
        HTMLDivElement: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': typescript,
      react,
      'react-hooks': reactHooks,
      security,
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      ...js.configs.recommended.rules,
      ...typescript.configs.recommended.rules,
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...security.configs.recommended.rules,
      
      // React-specific rules
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'react/no-unescaped-entities': 'warn',
      
      // TypeScript essentials
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-require-imports': 'off', // Allow require in Next.js config files
      
      // Security essentials
      'security/detect-object-injection': 'warn',
      'security/detect-eval-with-expression': 'error',
      'security/detect-non-literal-fs-filename': 'warn',
      
      // Code quality essentials
      'no-console': 'warn',
      'no-debugger': 'error',
      'no-var': 'error',
      'prefer-const': 'error',
      'complexity': ['warn', 20], // Increased for React components
      'no-undef': 'off', // TypeScript handles this better
    },
  },

  // Node.js environment for infrastructure and scripts
  {
    files: ['infrastructure/**/*.{ts,js}', 'scripts/**/*.{js,ts}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      parser: typescriptParser,
      globals: {
        ...globals.node,
        ...globals.es2022,
        // Add missing Node.js globals
        NodeJS: 'readonly',
        RequestInit: 'readonly',
        Response: 'readonly',
        AbortController: 'readonly',
        TextEncoder: 'readonly',
        TextDecoder: 'readonly',
        atob: 'readonly',
        btoa: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': typescript,
      security,
    },
    rules: {
      '@typescript-eslint/no-require-imports': 'off', // Allow require in Node.js files
      'complexity': ['warn', 25], // Higher for infrastructure code
      'no-undef': 'off', // TypeScript handles this better
    },
  },

  // Lambda functions (CommonJS)
  {
    files: ['infrastructure/src/functions/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'commonjs',
      globals: {
        ...globals.node,
        ...globals.es2022,
      },
    },
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
    },
  },

  // Jest environment for test files
  {
    files: ['**/*.test.{ts,tsx,js}', '**/*.spec.{ts,tsx,js}', '**/__tests__/**/*.{ts,tsx,js}', '**/jest.setup.js', '**/test/setup.ts'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      parser: typescriptParser,
      globals: {
        ...globals.jest,
        ...globals.node,
        ...globals.es2022,
      },
    },
    plugins: {
      '@typescript-eslint': typescript,
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      'no-console': 'off',
      '@typescript-eslint/no-require-imports': 'off',
    },
  },

  // Jest config files
  {
    files: ['**/jest.config.js', '**/jest.setup.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'commonjs',
      globals: {
        ...globals.node,
        ...globals.jest,
      },
    },
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
      // Disable Next.js specific rules in Jest setup
      '@next/next/no-img-element': 'off',
    },
  },

  // Browser-specific files (web assets)
  {
    files: ['**/assets/**/*.js', '**/public/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {
        ...globals.browser,
        ...globals.es2022,
      },
    },
    rules: {
      'no-console': 'warn',
      'security/detect-object-injection': 'warn',
    },
  },

  // Prettier integration (must be last)
  prettier,
];