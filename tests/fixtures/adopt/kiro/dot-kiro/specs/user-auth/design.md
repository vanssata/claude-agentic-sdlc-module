# Design: user authentication

## Overview

Sessions are server-side, stored in PostgreSQL, referenced by an HTTP-only cookie.

## Components

- AuthRoute: POST /login, POST /logout.
- SessionStore: create, read, revoke.
