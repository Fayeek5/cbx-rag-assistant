# Widget API — Quick Reference

The Widget API lets you create, list, and delete widgets.

## Authentication
All requests require a Bearer token in the `Authorization` header. Tokens expire
after 30 minutes. A `401 Unauthorized` response means the token is missing or
expired — request a new one from `/auth/token`.

## Create a widget
`POST /api/widgets`

The `color` field must be one of: `red`, `green`, `blue`. Sending any other
value returns `400 Bad Request` with the message "invalid color". The `size`
field is an integer between 1 and 100.

## Rate limits
The API allows 100 requests per minute per token. Exceeding this returns
`429 Too Many Requests`. Wait 60 seconds before retrying.

## Common errors
A `500 Internal Server Error` on widget creation almost always means the `size`
field was sent as a string instead of an integer. Always send `size` as a JSON
number.
