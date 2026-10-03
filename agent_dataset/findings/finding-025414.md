---
id: 25414
severity: "Medium"
---

# Metadata is not set in Cap, which is required by the inherited Router to specify gas limit to the mailbox

## Description

The gas limit of messages must be set in the metadata [function](<https://github.com/hyperlane-xyz/hyperlane-monorepo/blob/0865c948c378253b462d7be4fa33cd6e3d504cf0/solidity/contracts/client/MailboxClient.sol#L95-L99>), as indicated by the [docs](<https://docs.hyperlane.xyz/docs/reference/hooks/interchain-gas#gas-limit>).

When it is not set, the gas limit defaults to 50_000, which may not be enough to handle the epoch increase on the destination.

## Proof of Concept

No PoC provided.

## Recommendation

Overwrite the function with the correct metadata. Additionally, the Hyperlane version used is old, consider using a more recent one. In the newer version, metadata is sent as an argument, which makes it more obvious that it must be set.
