---
id: 25186
severity: "Medium"
---

# _crossTransfer(...) reverts for smart contracts that don't share the same address on different chains

## Description

_crossTransfer(...) has a beneficiary check such that the receiver of the funds in the destination chain must be the same as the previous beneficiary (most likely the msg.sender or the ConnextRouter).

If the address is a smart contract, the address will probably be different on the different chain, which will make the transaction revert.

## Proof of Concept

No PoC provided.

## Recommendation

Allow users to specify in a mapping the corresponding beneficiary in the destination chain, in a function addBeneficiaryToDestDomain(...), which would set beneficiary[msg.sender][destDomain] = newBeneficary;.
