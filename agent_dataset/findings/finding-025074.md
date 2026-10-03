---
id: 25074
severity: "Medium"
---

# Tokens with callbacks may allow malicious attackers to steal the protocol

## Description

In Batch.sol, function withdraw() [burns](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L217-L218>) the receiptId after transferring the tokens to the user.

This means that if the token has a callback, the user may use it to sell the nft somewhere else, getting some extra value for it, and then the execution continues in withdraw(), burning the nft of the other new owner.

In BatchOut.sol, withdrawFulfill(), the withdrawStatus is set to [true](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/BatchOut.sol#L379-L381>) only after the tokens are transferred to the user. An attacker could use a callback to reenter the function and withdraw the shares until the contract is drained.

## Proof of Concept

No PoC provided.

## Recommendation

Follow the checks-effects-interactions pattern. In Batch.sol, burn the receipt and only then transfer the tokens to the receiptOwner. In BatchOut.sol, set the withdrawStatus to true before transferring tokens.
