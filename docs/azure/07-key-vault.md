# Azure Key Vault

Taxodactyl can use Azure Key Vault (AKV) to store per-user API credentials
(e.g. BOLD, NCBI keys) when running on Azure Batch. The vault is accessed
via the `AzureVaultBackend` in `scripts/src/utils/secrets.py`, which is
selected automatically when `AZURE_KEY_VAULT_URL` is provided. If this is not
available, you can omit to disable the vault, or pass `SECRET_KEY` to use an
encrypted local vault (this will be ephemeral on Batch nodes).

Secrets are keyed as `<secret-name>-<user-email>` (non-alphanumeric
characters replaced with `-`), so each user's credentials are isolated
within a single shared vault.

## Prerequisites

- Azure CLI installed and authenticated (`az login`)
- `RESOURCE_GROUP`, `KEY_VAULT_NAME` and `REGION` set in `.env.azure`
- `Owner` or `User Access Administrator` permission on the resource group
  (needed to assign RBAC roles on the vault)
- `Microsoft.KeyVault` resource provider registered on the subscription:
  ```sh
  az provider register --namespace Microsoft.KeyVault
  # Check status (wait for "Registered" before proceeding):
  az provider show --namespace Microsoft.KeyVault --query registrationState
  ```

>[!NOTE]
> Run `source deployment/azure/batch-helpers.sh` to load helper functions.

## Step 1: Add Key Vault variables to `.env.azure`

Add the following to your `.env.azure` file (see `.env.sample` for
the template):

```bash
KEY_VAULT_NAME=your-keyvault-name       # globally unique, 3-24 chars
AZURE_KEY_VAULT_URL=https://${KEY_VAULT_NAME}.vault.azure.net/
```

The vault name must be globally unique across all Azure customers and
between 3–24 alphanumeric characters or hyphens.

## Step 2: Create the Key Vault

```sh
# Load env vars first
az_load_env

# Create the vault (uses REGION and RESOURCE_GROUP from .env.azure)
az_kv_create
```

Or with the raw Azure CLI command:

```sh
az keyvault create \
  --name "$KEY_VAULT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$REGION" \
  --enable-rbac-authorization true \
  --retention-days 7
```

The vault is created with **Azure RBAC** as the access model (not legacy
vault access policies). The `--retention-days 7` setting retains deleted
secrets for 7 days before permanent erasure (soft-delete).

## Step 3: Grant Access

Access is controlled via two built-in RBAC roles:

| Role | Permissions | Who needs it |
|---|---|---|
| `Key Vault Secrets Officer` | read + write + delete | Developers / admins / Batch node managed identity |
| `Key Vault Secrets User` | read-only | Not used — nodes must write secrets to cache credentials |

### Grant access to your local user (for development)

```sh
# Grants the currently signed-in user read+write (officer) access
az_kv_grant_access --role officer
```

Or with the raw Azure CLI command:

```sh
PRINCIPAL=$(az ad signed-in-user show --query id -o tsv)
KV_ID=$(az keyvault show -n "$KEY_VAULT_NAME" -g "$RESOURCE_GROUP" --query id -o tsv)

az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee-object-id "$PRINCIPAL" \
  --assignee-principal-type User \
  --scope "$KV_ID"
```

> [!NOTE]
> The `--assignee-principal-type` flag suppresses an Azure CLI warning and avoids
> an AAD graph lookup. Use `User` for human accounts and `ServicePrincipal` for
> managed identities.

### Grant access to the Batch node managed identity

Batch nodes authenticate using a user-assigned managed identity attached to
the pool. See [02-pool-management.md](02-pool-management.md) for how to
create the identity and attach it to the pool.

Once the identity exists, retrieve its `principalId`:

```sh
az_identity_show
# or: az identity show -n "$MANAGED_IDENTITY_NAME" -g "$RESOURCE_GROUP" --query principalId -o tsv
```

Then grant read+write access to the vault:

```sh
az_kv_grant_access --principal <principalId> --role officer
```

Or with the raw Azure CLI command:

```sh
KV_ID=$(az keyvault show -n "$KEY_VAULT_NAME" -g "$RESOURCE_GROUP" --query id -o tsv)

az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee-object-id "<principalId>" \
  --assignee-principal-type ServicePrincipal \
  --scope "$KV_ID"
```

## Step 4: Configure the workflow

Add `AZURE_KEY_VAULT_URL` to the Batch pool's start task environment
variables so that every task can connect to the vault. See
[04-start-tasks.md](04-start-tasks.md) for where to wire this in.

In `.env.azure` (for local runs):

```bash
AZURE_KEY_VAULT_URL=https://${KEY_VAULT_NAME}.vault.azure.net/
```

The Python config layer reads this via `AZURE_KEY_VAULT_URL` and passes
the URL to `AzureVaultBackend`, which uses `DefaultAzureCredential` —
picking up `az login` locally or the managed identity on Batch nodes.

## Verifying the setup

```sh
# Show vault details and URL
az_kv_show

# List secrets currently stored (names only, not values)
az_kv_list_secrets
```

A quick end-to-end smoke test from a Python shell:

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import os

client = SecretClient(
    vault_url=os.environ["AZURE_KEY_VAULT_URL"],
    credential=DefaultAzureCredential(),
)

# Write a test secret
client.set_secret("smoke-test", "hello")

# Read it back
assert client.get_secret("smoke-test").value == "hello"

# Clean up
client.begin_delete_secret("smoke-test")
print("Key Vault OK")
```

## Maintenance

### Listing and auditing secrets

```sh
az_kv_list_secrets
```

Secrets are named `<secret-name>-<user-email>` with non-alphanumeric
characters replaced by `-`. For example, `bold-api-key` for user
`alice@example.com` is stored as `bold-api-key-alice-example-com`.

### Recovering or purging deleted secrets

Deleted secrets enter a soft-delete state for `--retention-days` (7 by
default) before permanent erasure.

```sh
# List deleted secrets
az keyvault secret list-deleted --vault-name "$KEY_VAULT_NAME" -o table

# Recover a deleted secret
az keyvault secret recover \
  --vault-name "$KEY_VAULT_NAME" \
  --name <secret-name>

# Permanently purge a deleted secret (cannot be undone)
az keyvault secret purge \
  --vault-name "$KEY_VAULT_NAME" \
  --name <secret-name>
```

### Rotating access / RBAC role assignments

Role assignments can be reviewed and revoked via the Azure portal
(**Key Vault → Access control (IAM)**) or CLI:

```sh
KV_ID=$(az keyvault show -n "$KEY_VAULT_NAME" -g "$RESOURCE_GROUP" --query id -o tsv)

# List all role assignments on the vault
az role assignment list --scope "$KV_ID" -o table

# Revoke a role assignment
az role assignment delete \
  --role "Key Vault Secrets User" \
  --assignee-object-id "<principalId>" \
  --scope "$KV_ID"
```
