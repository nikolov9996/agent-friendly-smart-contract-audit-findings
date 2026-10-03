---
id: 25531
severity: "Low/Info"
---

# Limitations for Users Employing Multi-sig or Account Abstraction Wallets in Setting Delegate Address

## Description

Within the Delegatable::setDelegate() function, [there](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradingCallbacks.sol#L274>) exists a check to determine if a contract is executing the function, restricting the action solely to Externally Owned Accounts (EOAs).

However, this approach may pose issues for users utilizing multi-sig or account abstraction wallets [(ERC-4337](<https://eips.ethereum.org/EIPS/eip-4337>)).

Additionally, in accordance with [EIP 3074](<https://eips.ethereum.org/EIPS/eip-3074#abstract>), which introduces the AUTH and AUTHCALL EVM instructions, the first one sets a context variable authorized based on an ECDSA signature and the second one sends a call as the authorized account, allowing for the delegation of control from an EOA to a smart contract.

As a result, relying on tx.origin to ensure msg.sender is an EOA may not remain valid if EIP 3074 is implemented.

## Proof of Concept

No PoC provided.

## Recommendation

Consider entirely removing this check, as there is a significant likelihood of users employing the mentioned wallets or new EIPs, potentially disrupting the introduced logic.
