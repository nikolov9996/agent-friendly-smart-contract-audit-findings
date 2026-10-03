---
id: 25402
severity: "Medium"
---

# BasicVault is incompatible with fee-on-transfer tokens

## Description

The deposit and redeem [functions](<https://github.com/hyperlane-xyz/hyperlane-monorepo/blob/0865c948c378253b462d7be4fa33cd6e3d504cf0/solidity/contracts/client/MailboxClient.sol#L95-L99>) of the vault take an amount parameter and mint/burn the corresponding amounts assuming a 1:1 ratio.

However, fee-on-transfer tokens charge a small fee on every transfer, disrupting the 1:1 ratio and causing issues with internal accounting.

## Proof of Concept

No PoC provided.

## Recommendation

Compute the balance before and after the transfer, then subtract them to get the actual amount transferred. Additionally, use the nonReentrant modifier to prevent reentrancy in ERC777 tokens.
