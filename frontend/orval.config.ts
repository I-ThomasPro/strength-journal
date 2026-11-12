import { defineConfig } from 'orval'

// Generates typed TanStack Query hooks from the API's schema (`make openapi` exports it from
// the backend): a file per tag in src/api/generated, with types in src/api/generated/model.
// Hooks are named after operation ids, so `exercises-index` becomes useExercisesIndex
export default defineConfig({
  api: {
    input: { target: './openapi.json' },
    output: {
      mode: 'tags',
      target: './src/api/generated/endpoints.ts',
      schemas: './src/api/generated/model',
      client: 'react-query',
      httpClient: 'fetch',
      clean: true,
      override: {
        // Every request goes through apiFetch: CSRF header, JSON, typed errors
        mutator: { path: './src/api/client.ts', name: 'apiFetch' },
        // Hooks return the response body; errors are thrown as ApiError or NetworkError
        fetch: { includeHttpResponseReturnType: false },
        query: { signal: true },
      },
    },
  },
})
