import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTypeScript from 'eslint-config-next/typescript';

const sdaAppRules = {
  files: ['app/**/*.{ts,tsx}'],
  rules: {
    // API payloads are intentionally narrowed at the boundary while the mock
    // provider evolves; keep this visible as a warning until contracts move to
    // packages/contracts.
    '@typescript-eslint/no-explicit-any': 'warn',
    // Async data loading is a deliberate client-side concern in this demo.
    'react-hooks/set-state-in-effect': 'warn',
  },
};

export default [...nextVitals, ...nextTypeScript, sdaAppRules];
