---
id: 25226
severity: "Low/Info"
---

# When changing addresses, use 2 step transfer and/or address 0x0 checks

## Description

When changing important addresses, it's best to use additional safety measures to prevent wrong addresses from being set. One layer of protection is using 2 step address transfer, in which a pending role is set first and only then, from the pending role account, it accepts the new role.

Safety measures were added to several of the functions that set addresses (checking if it is a contract). But for example the function [setNetworkWalletAddress()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/GlacierAddressBook.sol#L79>) in GlacierAddressBook should have an extra security measure like 2 step transfer (since it can't use the isContract check).

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
