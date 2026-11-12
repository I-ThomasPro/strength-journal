import { setupServer } from 'msw/node'

/** A stand-in for the API in tests. Give each test the responses it needs with
 * `server.use(http.get('/api/...', () => HttpResponse.json(...)))`; any request without a
 * handler fails the test */
export const server = setupServer()
