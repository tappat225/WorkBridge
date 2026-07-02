<!-- SPDX-License-Identifier: Apache-2.0 -->

# Contributing to CapOwn

Thank you for considering a contribution to CapOwn. This project uses an
open-core licensing model, so contributions need to follow a few rules before
they can be accepted.

## Contributor License Agreement

By opening a pull request or otherwise submitting a contribution, you agree to
the CapOwn Contributor License Agreement in [CLA.md](CLA.md).

The CLA gives the project maintainer the rights needed to maintain the open
source project, offer hosted and commercial editions, and relicense or dual
license contributions when needed. Your contribution remains available under
the open source license that applies to the files you modify.

Do not submit a contribution if you cannot agree to the CLA.

## License Boundaries

CapOwn uses directory-level license boundaries:

- `master/` is the Community Master and is licensed under AGPL-3.0-only.
- `client/`, `worker/`, `shared/`, `docs/`, deployment tooling, tests, and
  root-level project files are licensed under Apache-2.0 unless a file says
  otherwise.
- Commercial Master management, hosted service, billing, tenant administration,
  regional relay operations, enterprise policy, and related cloud features are
  outside this repository unless they are explicitly committed here with an
  open source license notice.

Keep the existing license boundary intact. In particular, proprietary or
commercial components should not copy implementation code from `master/` unless
the maintainer has intentionally handled the AGPL licensing implications.
Shared protocol and utility code that needs to be used by both open source and
commercial components should live under `shared/` with Apache-2.0 licensing.

## SPDX Headers

New source and configuration files must include an SPDX license identifier.
Use the license that matches the directory:

```text
# SPDX-License-Identifier: Apache-2.0
# SPDX-License-Identifier: AGPL-3.0-only
```

For Markdown files, use an HTML comment:

```text
<!-- SPDX-License-Identifier: Apache-2.0 -->
```

## Security and Secrets

Never commit secrets or private deployment data. This includes real tokens,
API keys, private URLs, customer data, production configuration files, `.env`
files, logs containing sensitive data, and generated databases.

Configuration examples should use placeholder values such as
`<your-client-token>` or `<your-master-domain>`.

## Pull Request Checklist

Before opening a pull request:

- Confirm that you agree to the CLA.
- Keep changes focused and explain the user-facing behavior change.
- Add or update tests when changing behavior.
- Preserve the Master/Worker/Client separation. Cross-component shared code
  should go through `shared/`.
- Keep program output ASCII-only.
- Do not include real config files, tokens, credentials, or private data.
- Preserve or add SPDX license identifiers.

