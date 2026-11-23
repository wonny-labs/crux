# Organisation root CA folder

You need this folder only on a network where a proxy inspects TLS: it re-signs every HTTPS connection with your organisation's root CA. The Dev Container image does not trust that CA, so downloads fail with:

~~~text
curl: (60) SSL certificate problem: unable to get local issuer certificate
~~~

The image build then installs no J-Link software, and pip, `west update`, `west sdk install` and the other downloads of `scripts/bootstrap.sh` can fail the same way.

To fix it, put your organisation's root CA file here, with the extension `.crt`, `.pem` or `.cer`, then run **Dev Containers: Rebuild Container**. The image build adds it to the system bundle `/etc/ssl/certs/ca-certificates.crt` before any download (see [`install-org-ca.sh`](../install-org-ca.sh)). With no certificate here, the build prints `skipping` and the image is the same as without this step. A CA file that you already use for another Dev Container with this layout can be copied here unchanged.

Each developer adds their own file, on their own machine. Never commit a certificate, in this repository or in any copy of it. Git ignores every file in this folder except `.gitkeep` and this README.

## Which CA

On a machine behind the proxy, ask a server who issued its certificate:

~~~sh
openssl s_client -connect <host>:443 -servername <host> </dev/null | openssl x509 -noout -issuer
~~~

Replace `<host>` with a host that fails, such as `github.com` or `pypi.org`. If the issuer is your organisation and not a public certificate authority, the proxy re-signs that host, and you need that issuer's root CA. The issuer can be an intermediate CA; export the root at the top of its chain (the **Certification Path** tab in Windows shows the chain).

## Getting the CA on Windows

1. Run `certmgr.msc`.
2. Open **Trusted Root Certification Authorities**, then **Certificates**, and find your organisation's root CA (the issuer from above).
3. Right-click it, **All Tasks**, **Export...**.
4. Choose **Base-64 encoded X.509 (.CER)** and save the file.
5. Rename the file from `.cer` to `.crt` and copy it into this folder (from WSL2, for example `cp /mnt/c/Users/<you>/Downloads/org-root.cer .devcontainer/certs/org-root.crt`). The build also accepts the `.cer` name; `.crt` makes the format plain.

## DER files

The **DER encoded binary X.509** export and many `.cer` files are DER, not PEM. A PEM file starts with the line `-----BEGIN CERTIFICATE-----`. The build converts a DER file with openssl, which the image has. To convert one yourself:

~~~sh
openssl x509 -inform der -in x.cer -out x.crt
~~~

One PEM file may hold several certificates, such as a root and an intermediate; each is installed.

## What the build checks

- A `.crt`, `.pem` or `.cer` file that contains a private key, is neither PEM nor DER, or does not parse as a certificate stops the image build with an error naming the file. Nothing is installed until every such file passes.
- Files with other extensions are skipped with a warning.
- The build prints the subject of each certificate it installs.

## What trusts the CA

The image sets these variables to the system bundle, at build time and at run time, so tools that keep their own CA list use it too. They change nothing when no extra CA is installed.

| Variable | Used by |
| --- | --- |
| `SSL_CERT_FILE` | OpenSSL-based clients, including Python's `ssl` module and `urllib` |
| `REQUESTS_CA_BUNDLE` | Python `requests`, which `west sdk install` uses to fetch the Zephyr SDK |
| `PIP_CERT` | `pip`, in the image build and in the virtual environment of `scripts/bootstrap.sh` |
| `CURL_CA_BUNDLE` | curl, which already reads the system bundle; set for tools that read the variable |
| `GIT_SSL_CAINFO` | Git, including `west update`; Git already reads the system bundle |
| `NODE_EXTRA_CA_CERTS` | Node.js, which the VS Code server in the container runs on |

wget reads the system bundle itself. The CMake version that `scripts/bootstrap.sh` installs does not check certificates when it fetches GoogleTest.

The Docker daemon pulls the base image on your machine, outside the container. If that pull fails with a certificate error, your machine's Docker set-up has to trust the CA; this folder does not change that.

No build behind a TLS-inspecting proxy has been run for this guide yet.
