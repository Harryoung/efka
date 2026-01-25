# Security Configuration Guide

## Network Security

### Firewall Rules (Production)
```yaml
# Ingress rules
ingress:
  - name: allow-https
    port: 443
    protocol: TCP
    source: 0.0.0.0/0

  - name: allow-api
    port: 8443
    protocol: TCP
    source: 10.0.0.0/8  # Internal only

  - name: allow-ssh-bastion
    port: 22
    protocol: TCP
    source: 10.100.0.0/24  # Bastion subnet only

# Egress rules
egress:
  - name: allow-all-internal
    destination: 10.0.0.0/8
    protocol: all

  - name: allow-https-external
    port: 443
    protocol: TCP
    destination: 0.0.0.0/0
```

### VPN Access
- Provider: WireGuard
- Config location: `/etc/wireguard/wg0.conf`
- Allowed IPs: See `access_control.md`

## Authentication

### SSO Configuration
```json
{
  "provider": "Okta",
  "domain": "techcorp.okta.com",
  "client_id": "0oa1234567890abcdef",
  "scopes": ["openid", "profile", "email", "groups"],
  "mfa_required": true,
  "session_timeout": 28800
}
```

### API Key Rotation
- Production keys: Rotate every 90 days
- Development keys: Rotate every 180 days
- Emergency rotation: Contact security@techcorp.com

## Encryption

### At Rest
- Algorithm: AES-256-GCM
- Key management: AWS KMS
- Key rotation: Automatic, yearly

### In Transit
- TLS 1.3 required (TLS 1.2 deprecated)
- Certificate provider: DigiCert
- Certificate renewal: Automated via cert-manager

## Compliance Checklist

### SOC 2 Requirements
- [ ] Access logs retained 1 year
- [ ] MFA enforced for all employees
- [ ] Quarterly access reviews
- [ ] Annual penetration testing

### HIPAA Requirements (DataVault only)
- [ ] PHI encryption verified
- [ ] Audit logs immutable
- [ ] BAA signed with all vendors
- [ ] Annual HIPAA training completed
