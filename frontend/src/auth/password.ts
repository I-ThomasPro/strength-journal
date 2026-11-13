/** The API's minimum (MIN_PASSWORD_LENGTH in backend/app/auth/security.py) */
export const MIN_PASSWORD_LENGTH = 10

/** The hint under a new password, and the message when it's too short */
export const PASSWORD_HINT = `At least ${String(MIN_PASSWORD_LENGTH)} characters`
