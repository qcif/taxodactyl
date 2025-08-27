# SFTP User Setup Ansible Playbook

This playbook creates a sandboxed SFTP user on the remote server.

## Usage

1. Activate the ansible virtual environment:
   ```bash
   venv ansible
   ```

2. Run the playbook:
   ```bash
   ansible-playbook -i inventory/hosts.yml setup-sftp-user.yml
   ```

3. To set a custom password:
   ```bash
   ansible-playbook -i inventory/hosts.yml setup-sftp-user.yml -e "sftp_user_password=YourSecurePassword123"
   ```

## What it does

- Creates an SFTP-only user with password authentication
- Restricts the user to their home directory (/mnt/data/user-data)
- Disables shell access and SSH tunneling
- Configures SSH daemon for secure chroot jail

## Security Features

- User cannot access any directory outside /mnt/data/user-data
- No shell access (shell set to /bin/false)
- No SSH key authentication (password only)
- No TCP forwarding or X11 forwarding
- Chroot jail prevents directory traversal

## Testing the Setup

After running the playbook, test SFTP access:
```bash
sftp sftpuser@cloudgene.qcif.edu.au
```