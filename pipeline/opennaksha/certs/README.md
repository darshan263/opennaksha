Intermediate CA certificates for government servers that send incomplete TLS chains.
They are loaded only for hosts listed in a scraper's `legacy_tls_hosts`, on top of certifi's
roots. Verification stays on.

| File | Needed by | Source | Valid until |
|---|---|---|---|
| `sectigo-public-server-auth-ca-ov-r36.pem` | ahmedabadcity.gov.in (AMC) | http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt (the AIA "CA Issuers" URL in the server certificate), chains to Sectigo Public Server Authentication Root R46 | 2036-03-21 |
