---
id: 25263
severity: "Low/Info"
---

# KeyringCoreV2Base::collectFees() should use Address::sendValue() instead of address.transfer()

## Description

address.transfer() hardcodes 2300 gas to forward, which may not be enough if gas costs change in the future or to is a smart contract wallet that does some logic in its receive()/fallback() function.

## Proof of Concept

No PoC provided.

## Recommendation

Use address::sendValue() from [OpenZeppelin](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/Address.sol#L33>).
