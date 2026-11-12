import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default defineConfig([
  globalIgnores(['dist', 'coverage', 'src/api/generated']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      // Rules that use type information, e.g. a promise that's never awaited or handled
      tseslint.configs.strictTypeChecked,
      tseslint.configs.stylisticTypeChecked,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      jsxA11y.flatConfigs.recommended,
      // Last, so formatting is left to Prettier
      prettier,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    // shadcn/ui components export their variants (e.g. buttonVariants) next to the component
    files: ['src/components/ui/**/*.tsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
])
