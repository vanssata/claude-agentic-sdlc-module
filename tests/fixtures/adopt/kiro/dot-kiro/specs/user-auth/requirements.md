# Requirements: user authentication

## Requirement 1

**User story:** As a patient, I want to sign in with my email, so that I can see my bookings.

### Acceptance criteria

1. WHEN a patient submits a valid email and password THEN the system SHALL start a session.
2. WHEN the password is wrong three times THEN the system SHALL lock the account for 15 minutes.
