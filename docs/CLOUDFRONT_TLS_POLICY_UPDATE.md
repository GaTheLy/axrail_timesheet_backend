# CloudFront TLS Policy Update

## Security Remediation — TLS/SSL Hardening

**Project:** COLABS / TimeFlow  
**Severity:** Informational (CVSS 0.0)  
**Finding:** TLS/SSL Security Misconfiguration  
**Date:** March 2026

---

## Background

A penetration test identified that the CloudFront distribution accepts weak cipher suites (e.g., `TLS_RSA_WITH_3DES_EDE_CBC_SHA`) vulnerable to Sweet32 attacks, and permits TLS 1.0 connections with CBC cipher suites vulnerable to the BEAST attack. This is an infrastructure configuration change — no application code changes are required.

## Required Changes

### 1. Update CloudFront Minimum Security Policy

Update the CloudFront distribution's **Minimum Security Policy** to `TLSv1.2_2021`.

**Steps (AWS Console):**

1. Open the [CloudFront Console](https://console.aws.amazon.com/cloudfront/)
2. Select the distribution serving the TimeFlow application
3. Go to **General** → **Settings** → **Edit**
4. Under **Security policy**, change the value to **TLSv1.2_2021 (recommended)**
5. Save changes and wait for the distribution to deploy (status: **Deployed**)

**Steps (AWS CLI):**

```bash
# Get the current distribution config
aws cloudfront get-distribution-config --id <DISTRIBUTION_ID> --output json > dist-config.json

# Edit dist-config.json:
#   - Change "MinimumProtocolVersion" to "TLSv1.2_2021"
#   - Remove the top-level "ETag" field and note its value

# Update the distribution
aws cloudfront update-distribution \
  --id <DISTRIBUTION_ID> \
  --if-match <ETAG_VALUE> \
  --distribution-config file://dist-config.json
```

**What this disables:**
- TLS 1.0 and TLS 1.1 connections
- Weak cipher suites including 3DES (`TLS_RSA_WITH_3DES_EDE_CBC_SHA`)
- CBC-mode ciphers vulnerable to BEAST attacks

**What remains supported:**
- TLS 1.2 with strong cipher suites (AES-GCM, ChaCha20-Poly1305)
- All modern browsers and clients (Chrome, Firefox, Safari, Edge, curl, etc.)

### 2. SSL Certificate — ACM with Auto-Renewal

Ensure the SSL certificate is managed by AWS Certificate Manager (ACM) with auto-renewal enabled.

**Verify current certificate:**

1. In the CloudFront distribution settings, check the **Custom SSL certificate** field
2. Confirm it references an ACM certificate (ARN starts with `arn:aws:acm:us-east-1:...`)
3. In the [ACM Console](https://console.aws.amazon.com/acm/) (us-east-1 region), verify:
   - **Status:** Issued
   - **Renewal status:** Eligible for renewal / Pending automatic renewal
   - **In use by:** The CloudFront distribution

**If using a manually uploaded certificate**, migrate to ACM:

1. Request a new public certificate in ACM (must be in `us-east-1` for CloudFront)
2. Validate domain ownership via DNS (add the CNAME record ACM provides)
3. Once issued, update the CloudFront distribution to use the new ACM certificate
4. Remove the old manually uploaded certificate from IAM

**ACM auto-renewal requirements:**
- Certificate must be DNS-validated (not email-validated) for automatic renewal
- The DNS validation CNAME record must remain in place
- ACM automatically renews certificates ~60 days before expiration

## Verification

After applying the changes, verify the configuration:

```bash
# Test that TLS 1.2 works
curl -v --tlsv1.2 https://<your-domain>/ 2>&1 | grep "SSL connection"

# Confirm TLS 1.0 is rejected
curl -v --tlsv1.0 https://<your-domain>/ 2>&1 | grep -i "error\|alert"

# Confirm TLS 1.1 is rejected
curl -v --tlsv1.1 https://<your-domain>/ 2>&1 | grep -i "error\|alert"

# Check cipher suites (requires nmap)
nmap --script ssl-enum-ciphers -p 443 <your-domain>
```

Expected results:
- TLS 1.2 connection succeeds
- TLS 1.0 and 1.1 connections are refused
- No 3DES or CBC cipher suites listed in the nmap output

## Rollback

If the TLS policy update causes client compatibility issues:

1. Change the security policy back to the previous value (e.g., `TLSv1.1_2016`)
2. Investigate which clients require older TLS versions
3. Plan client upgrades before re-applying `TLSv1.2_2021`

> **Note:** All modern browsers have supported TLS 1.2 since 2013. Client compatibility issues are unlikely unless legacy systems or IoT devices access the distribution.
