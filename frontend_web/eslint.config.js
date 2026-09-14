import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import prettier from 'eslint-plugin-prettier';
import prettierConfig from 'eslint-config-prettier';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import betterTailwindcss from 'eslint-plugin-better-tailwindcss';

export default [
    { ignores: ['dist'] },
    js.configs.recommended,
    prettierConfig,
    jsxA11y.flatConfigs.recommended,
    {
        files: ['**/*.{ts,tsx}'],
        languageOptions: {
            ecmaVersion: 2020,
            globals: globals.browser,
            parser: tsParser,
            parserOptions: {
                ecmaFeatures: { jsx: true },
            },
        },
        plugins: {
            'react-hooks': reactHooks,
            'react-refresh': reactRefresh,
            prettier,
            'better-tailwindcss': betterTailwindcss,
            '@typescript-eslint': tsPlugin,
        },
        settings: {
            'better-tailwindcss': {
                entryPoint: 'src/theme/preset.css',
            },
        },
        rules: {
            ...reactHooks.configs.recommended.rules,
            'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
            'prettier/prettier': 'error',
            'no-unused-vars': 'off',
            // TypeScript's compiler already catches undefined variables; the plain
            // JS rule produces false-positives for TypeScript global types (React, etc.)
            'no-undef': 'off',
            // TypeScript allows `interface Foo {}` and `const Foo = ...` to coexist
            // (they live in separate type/value namespaces). Neither the JS nor the
            // TS-aware rule handle this correctly, and TypeScript itself enforces
            // real redeclarations at compile time.
            'no-redeclare': 'off',
            '@typescript-eslint/no-redeclare': 'off',
            '@typescript-eslint/no-unused-vars': 'error',
            ...betterTailwindcss.configs.recommended.rules,
            'better-tailwindcss/enforce-consistent-class-order': ['error', { order: 'official' }],
            'better-tailwindcss/no-deprecated-classes': 'error',
            'better-tailwindcss/enforce-shorthand-classes': 'error',
            'better-tailwindcss/no-unnecessary-whitespace': 'error',
            'better-tailwindcss/no-conflicting-classes': 'error',
            // The project uses Tailwind v4 with a custom DataRobot design-system config
            // that the plugin cannot fully resolve, causing hundreds of false positives
            // for both standard utility classes and custom semantic tokens.
            'better-tailwindcss/no-unregistered-classes': 'off',
            // enforce-consistent-line-wrapping conflicts with prettier's own line-
            // wrapping logic — ESLint adds newlines that prettier immediately removes.
            'better-tailwindcss/enforce-consistent-line-wrapping': 'off',
        },
    },
    {
        files: ['vite.config.ts', 'vite.config.*.ts'],
        languageOptions: {
            globals: { ...globals.node, ...globals.browser },
        },
    },
    {
        // Test fixtures deliberately attach handlers to bare elements to assert event
        // behaviour; they are not shipped UI. dr-ui and the design system relax the
        // interaction rules under their own test globs.
        files: ['tests/**/*.{ts,tsx}', 'tests/*.{ts,tsx}', '**/*.{test,spec}.{ts,tsx}'],
        languageOptions: {
            globals: { ...globals.vitest, ...globals.node },
        },
        rules: {
            'jsx-a11y/click-events-have-key-events': 'off',
            'jsx-a11y/no-static-element-interactions': 'off',
            'jsx-a11y/no-noninteractive-element-interactions': 'off',
        },
    },
];
