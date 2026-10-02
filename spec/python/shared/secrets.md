# Spec: Secrets vault (`src/utils/secrets.py`)

**Derived from:** `secrets.py` (201), `config.py` (`vault`,
`_resolve_ncbi_api_key`, `_resolve_facility_name`, `user_secrets_dir`),
`tests/test_secrets.py`. v1.5.0.

## 1. Purpose

Remember a user's NCBI API key and facility name between runs so they
need not be passed every time.

## 2. Requirements

| ID | Requirement |
|---|---|
| SEC-001 | Backend selection (once, `config.vault`): `AZURE_KEY_VAULT_URL` set ⇒ Azure Key Vault; else `SECRET_KEY` set ⇒ local encrypted file; else no-op. Initialisation failure ⇒ no-op with a warning. |
| SEC-002 | `get`/`put` MUST never raise: errors are logged (Azure `get` errors at DEBUG) and `get` returns `None`. |
| SEC-003 | Secret identity = `(name, USER_EMAIL)`. Only `NCBI_API_KEY` and `facility_name` are stored (CFG-036). Without `USER_EMAIL` nothing is stored or read. |
| SEC-004 | Resolution: a value supplied this run is stored (overwriting); otherwise the stored value is used. For facility, the default `"Not provided"` counts as not supplied. |
| SEC-005 | Local backend: file `<user_secrets_dir>/secrets.enc` (first writable of `/var/lib/taxodactyl/<email>` — the Nextflow `app_data_dir` bind — or `~/.local/share/taxodactyl/<email>`), containing a Fernet-encrypted JSON map `"<name>:<email>" → value`; Fernet key = base64url(SHA-256(`SECRET_KEY`)). Unreadable/undecryptable files are treated as empty. |
| SEC-006 | Azure backend: secret name = `"<name>-<email>"` with every character outside `[A-Za-z0-9-]` replaced by `-`; credential `DefaultAzureCredential`; debug logs mask all but the last 4 characters. |

## 3. Defects

| ID | Severity | Defect |
|---|---|---|
| SEC-D-001 | Medium (security) | Secrets are keyed by the **unauthenticated** `USER_EMAIL`. With the Azure backend, anyone who can run the pipeline under the pool identity can retrieve another user's NCBI API key by setting their email. |
| SEC-D-002 | Low (security) | Local key derivation is a single unsalted SHA-256 of the passphrase (no KDF); file permissions are not restricted. |
| SEC-D-003 | Low | Azure name sanitisation can map different emails to the same secret (`a.b@x` vs `a-b@x`). |
